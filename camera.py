import RPi.GPIO as GPIO
from flask import Flask, render_template, send_from_directory
import time
import threading
from picamera2 import Picamera2
import smbus
import os
import immich_upload

# Setup GPIO
GPIO.setmode(GPIO.BCM)
BUTTON_PIN = 17
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Flask App Setup
app = Flask(__name__)

# Battery Monitoring Setup
class INA219:
    def __init__(self, i2c_bus=1, addr=0x43):
        self.bus = smbus.SMBus(i2c_bus)
        self.addr = addr
        self._current_lsb = 0.1524  # Current LSB = 100uA per bit
        self._power_lsb = 0.003048  # Power LSB = 2mW per bit
        self._cal_value = 26868
        self.write(0x05, self._cal_value)

    def read(self, address):
        data = self.bus.read_i2c_block_data(self.addr, address, 2)
        return ((data[0] * 256) + data[1])

    def write(self, address, data):
        temp = [(data & 0xFF00) >> 8, data & 0xFF]
        self.bus.write_i2c_block_data(self.addr, address, temp)

    def get_bus_voltage(self):
        self.write(0x05, self._cal_value)
        return (self.read(0x02) >> 3) * 0.004

    def get_current_mA(self):
        value = self.read(0x04)
        if value > 32767:
            value -= 65535
        return value * self._current_lsb

    def get_power_W(self):
        self.write(0x05, self._cal_value)
        value = self.read(0x03)
        if value > 32767:
            value -= 65535
        return value * self._power_lsb

# Global Battery Status
battery_status = {"voltage": 0, "current": 0, "power": 0, "capacity": 0}

def read_battery_status():
    """Reads battery status and updates global variable."""
    global battery_status
    try:
        ina219 = INA219()
        bus_voltage = ina219.get_bus_voltage()
        current_mA = ina219.get_current_mA()
        power_W = ina219.get_power_W()
        percent = (bus_voltage - 3) / 1.2 * 100
        percent = max(0, min(100, percent))

        battery_status = {
            "voltage": round(bus_voltage, 2),
            "current": round(current_mA / 1000, 3),
            "power": round(power_W, 3),
            "capacity": round(percent, 1)
        }
    except Exception as e:
        battery_status = {"error": f"Battery read error: {e}"}

def battery_monitor():
    """Runs battery readings in a background thread."""
    while True:
        read_battery_status()
        time.sleep(5)  # Update every 5 seconds

# Start Battery Monitoring Thread
battery_thread = threading.Thread(target=battery_monitor, daemon=True)
battery_thread.start()

# Ensure the photos directory exists
PHOTO_DIR = "./photos"
os.makedirs(PHOTO_DIR, exist_ok=True)

# Initialize Camera
camera = Picamera2()
camera.configure(camera.create_still_configuration(main={"size": (2592, 1944)}))
camera.start(show_preview=False)
time.sleep(1)  # Allow camera to initialize

def get_next_filename():
    """Finds the next available filename."""
    i = 1
    while True:
        filename = os.path.join(PHOTO_DIR, f"photo_{i}.jpg")
        if not os.path.exists(filename):
            return filename
        i += 1

def take_photo():
    """Captures a photo and uploads it."""
    filename = get_next_filename()
    try:
        camera.capture_file(filename)
        print(f"📸 Photo saved as: {filename}")

        # Upload to Immich
        immich_upload.upload(filename)
        print("✅ Upload successful")
    except Exception as e:
        print(f"❌ Error capturing or uploading image: {e}")

def button_callback(channel):
    """Handles button press event."""
    print("📸 Button Pressed! Taking a photo...")
    take_photo()
    time.sleep(0.2)  # Short debounce delay

print("🔴 Ready! Press the button to take a photo...")

# Detect button press
GPIO.add_event_detect(BUTTON_PIN, GPIO.FALLING, callback=button_callback, bouncetime=300)

@app.route('/')
def index():
    return render_template('index.html', battery=battery_status)

@app.route('/shutdown', methods=['POST'])
def shutdown():
    os.system('sudo shutdown -h now')
    return "Shutting down...", 200

def run_flask():
    """Runs the Flask web server in a separate thread."""
    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=False)

# Start Flask in a Separate Thread
flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()

# Keep the script running
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n🛑 Exiting program...")
finally:
    GPIO.cleanup()
    camera.stop()
    print("✅ Cleanup done.")
