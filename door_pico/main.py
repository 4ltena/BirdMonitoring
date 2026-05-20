import network, time, socket
from machine import Pin, Timer

# ============ Settings ============
SSID     = "your-ssid"
PASSWORD = "your-password"
PORT     = 8080

# ============ GPIO ============
led_warn = Pin(15, Pin.OUT)

# ============ Status ============
blinking    = False
blink_state = False

def blink_cb(t):
    global blink_state
    if blinking:
        blink_state = not blink_state
        led_warn.value(blink_state)
    else:
        led_warn.off()
        blink_state = False

blink_timer = Timer()
blink_timer.init(period=500, mode=Timer.PERIODIC, callback=blink_cb)

# ============ WiFi Connection ============
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    for _ in range(20):
        if wlan.isconnected():
            ip = wlan.ifconfig()[0]
            print("WiFi:", ip)
            return ip
        time.sleep(0.5)
    print("WiFi connect failed")
    return None

# ============ HTTP Request Process ============
def handle_request(conn):
    global blinking
    try:
        req = conn.recv(512).decode("utf-8", "ignore")
        first_line = req.split("\r\n")[0]

        if "GET /blink_on" in first_line:
            blinking = True
            body = b"OK"
        elif "GET /blink_off" in first_line:
            blinking = False
            body = b"OK"
        elif "GET /status" in first_line:
            body = b"blinking" if blinking else b"idle"
        else:
            conn.send(b"HTTP/1.1 404 Not Found\r\n\r\nNot Found")
            return

        resp = (b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/plain\r\n"
                b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                b"\r\n" + body)
        conn.send(resp)
    except Exception as e:
        print("Request error:", e)
    finally:
        conn.close()

# ============ Main Loop ============
def main():
    connect_wifi()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", PORT))
    s.listen(3)
    s.settimeout(0.1)
    print(f"Door server listening on port {PORT}")

    while True:
        try:
            conn, addr = s.accept()
            handle_request(conn)
        except OSError:
            pass

main()
