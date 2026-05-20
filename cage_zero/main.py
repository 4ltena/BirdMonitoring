import network, urequests, time
from machine import Pin, I2C, SPI

# ============ Settings ============
SSID               = "your-ssid"
PASSWORD           = "your-password"
YOLO_URL           = "http://192.168.1.134:8080/detect"
DOOR1_URL          = "http://192.168.1.xxx:8080"
DOOR2_URL          = "http://192.168.1.yyy:8080"
CAPTURE_INTERVAL_S = 10
HDC1080_ADDR       = 0x40

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

# ============ WiFi ============
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    for _ in range(20):
        if wlan.isconnected():
            return True
        time.sleep(0.5)
    return False

# ============ HDC1080 ============
def read_temp():
    i2c_env.writeto(HDC1080_ADDR, bytes([0x00]))
    time.sleep_ms(15)
    data = i2c_env.readfrom(HDC1080_ADDR, 4)
    return round(((data[0] << 8 | data[1]) / 65536) * 165 - 40, 1)

# ============ Health LEDs ============
def update_health_leds(temp):
    led_green.off(); led_yellow.off(); led_red.off()
    if TEMP_OK_MIN <= temp <= TEMP_OK_MAX:
        led_green.on()
    elif TEMP_WARN_MIN <= temp <= TEMP_WARN_MAX:
        led_yellow.on()
    else:
        led_red.on()

# ============ Capture ============
def capture_jpeg():
    raise NotImplementedError("Install the ArduCAM library first")

# ============ YOLO ============
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
        return result.get("bird_detected", False)
    except Exception:
        return False

# ============ Doors ============
def notify_doors(should_blink):
    path = "/blink_on" if should_blink else "/blink_off"
    for url in (DOOR1_URL, DOOR2_URL):
        try:
            r = urequests.get(url + path, timeout=3)
            r.close()
        except Exception:
            pass

# ============ Main ============
connect_wifi()

mode      = "INSIDE"
prev_mode = None
last_ms   = time.ticks_ms() - CAPTURE_INTERVAL_S * 1000

while True:
    now = time.ticks_ms()
    if time.ticks_diff(now, last_ms) >= CAPTURE_INTERVAL_S * 1000:
        last_ms = now
        try:
            jpeg = capture_jpeg()
            mode = "INSIDE" if detect_bird(jpeg) else "OUTSIDE"
        except Exception:
            pass
        try:
            update_health_leds(read_temp())
        except Exception:
            pass

    if mode != prev_mode:
        notify_doors(mode == "OUTSIDE")
        prev_mode = mode

    time.sleep_ms(50)
