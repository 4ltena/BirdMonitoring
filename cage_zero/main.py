import network, urequests, time, json
from machine import Pin, I2C, SPI

# ============ Settings ============
SSID               = "your-ssid"
PASSWORD           = "your-password"
YOLO_URL           = "http://192.168.1.134:8080/detect"
DOOR1_URL          = "http://192.168.1.xxx:8080"   # Door1 IP
DOOR2_URL          = "http://192.168.1.yyy:8080"   # Door2 IP
FLASK_URL          = "http://192.168.1.zzz:5000"   # Dashboard Server
CAPTURE_INTERVAL_S = 10
HDC1080_ADDR       = 0x40

# Parakeet health thresholds (C)
TEMP_OK_MIN   = 20.0
TEMP_OK_MAX   = 28.0
TEMP_WARN_MIN = 15.0
TEMP_WARN_MAX = 34.0

# ============ GPIO ============
spi_cam = SPI(0, baudrate=4_000_000, polarity=0, phase=0,
              sck=Pin(6), mosi=Pin(7), miso=Pin(4))
cam_cs  = Pin(5, Pin.OUT, value=1)

i2c_env = I2C(0, sda=Pin(2), scl=Pin(3), freq=400_000)

led_green  = Pin(18, Pin.OUT)
led_yellow = Pin(19, Pin.OUT)
led_red    = Pin(20, Pin.OUT)

# ============ Mode ============
MODE_INSIDE  = "INSIDE"
MODE_OUTSIDE = "OUTSIDE"

# ============ WiFi Connection ============
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    for _ in range(20):
        if wlan.isconnected():
            print("WiFi:", wlan.ifconfig()[0])
            return True
        time.sleep(0.5)
    print("WiFi connect failed")
    return False

# ============ HDC1080 Sensor ============
def read_hdc1080():
    i2c_env.writeto(HDC1080_ADDR, bytes([0x00]))
    time.sleep_ms(15)
    data = i2c_env.readfrom(HDC1080_ADDR, 4)
    temp = ((data[0] << 8 | data[1]) / 65536) * 165 - 40
    hum  = ((data[2] << 8 | data[3]) / 65536) * 100
    return round(temp, 1), round(hum, 1)

# ============ Update Health LEDs ============
def update_health_leds(temp):
    led_green.off(); led_yellow.off(); led_red.off()
    if TEMP_OK_MIN <= temp <= TEMP_OK_MAX:
        led_green.on()
    elif TEMP_WARN_MIN <= temp <= TEMP_WARN_MAX:
        led_yellow.on()
    else:
        led_red.on()

# ============ Capture (ArduCAM OV2640) ============
def capture_jpeg():
    # Requires ArduCAM MicroPython library:
    #   https://github.com/ArduCAM/PICO_SPI_CAM
    #
    # from ArduCAM import ArduCAM, OV2640
    # cam = ArduCAM(OV2640, spi_cam, cam_cs)
    # cam.capture_jpg()
    # return bytes(cam.read())
    raise NotImplementedError("Install the ArduCAM library first")

# ============ YOLO Inference Request ============
BOUNDARY = b"----PicoBoundary"

def detect_bird(jpeg_bytes):
    body = (b"--" + BOUNDARY + b"\r\n"
            b'Content-Disposition: form-data; name="file"; filename="cage.jpg"\r\n'
            b"Content-Type: image/jpeg\r\n\r\n"
            + jpeg_bytes + b"\r\n"
            b"--" + BOUNDARY + b"--\r\n")
    headers = {
        "Content-Type": "multipart/form-data; boundary=" + BOUNDARY.decode(),
        "Content-Length": str(len(body)),
    }
    try:
        r = urequests.post(YOLO_URL, data=body, headers=headers, timeout=10)
        result = r.json()
        r.close()
        return result.get("bird_detected", False), result.get("confidence", 0.0)
    except Exception as e:
        print("YOLO error:", e)
        return False, 0.0

# ============ Send Blink Command to Door Pico Ws ============
def notify_doors(should_blink):
    path = "/blink_on" if should_blink else "/blink_off"
    for url in (DOOR1_URL, DOOR2_URL):
        try:
            r = urequests.get(url + path, timeout=3)
            r.close()
        except Exception as e:
            print("Door notify error:", url, e)

# ============ Post Health Data to Dashboard ============
def post_health(temp, hum, current_mode):
    try:
        payload = json.dumps({"temperature": temp, "humidity": hum, "mode": current_mode})
        r = urequests.post(FLASK_URL + "/api/health",
                           data=payload,
                           headers={"Content-Type": "application/json"},
                           timeout=5)
        r.close()
    except Exception as e:
        print("Flask error:", e)

# ============ Main Loop ============
def main():
    global mode
    mode = MODE_INSIDE
    prev_mode = None

    connect_wifi()

    last_capture_ms = time.ticks_ms() - CAPTURE_INTERVAL_S * 1000
    last_health_ms  = time.ticks_ms() - 30_000  # post health data every 30 s

    while True:
        # --- periodic YOLO capture ---
        now = time.ticks_ms()
        if time.ticks_diff(now, last_capture_ms) >= CAPTURE_INTERVAL_S * 1000:
            last_capture_ms = now
            try:
                jpeg = capture_jpeg()
                detected, conf = detect_bird(jpeg)
                print(f"YOLO: bird={detected} conf={conf:.2f}")
                mode = MODE_INSIDE if detected else MODE_OUTSIDE
            except Exception as e:
                print("Capture/YOLO error:", e)

        # --- notify doors only on mode change ---
        if mode != prev_mode:
            notify_doors(mode == MODE_OUTSIDE)
            prev_mode = mode

        # --- temperature/humidity (every 30 s) ---
        if time.ticks_diff(time.ticks_ms(), last_health_ms) >= 30_000:
            last_health_ms = time.ticks_ms()
            try:
                temp, hum = read_hdc1080()
                update_health_leds(temp)
                post_health(temp, hum, mode)
                print(f"HDC1080: {temp}C {hum}%")
            except Exception as e:
                print("HDC1080 error:", e)

        time.sleep_ms(50)

main()
