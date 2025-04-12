import RPi.GPIO as GPIO
from flask import Flask, render_template, send_from_directory, url_for
import time
import threading
from picamera2 import Picamera2
import smbus
import os
import requests
from datetime import datetime
import logging
from PIL import Image

# Logging Setup
logging.basicConfig(
    filename='picam.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)

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

LOW_BATTERY_THRESHOLD = 10  # Shutdown if battery drops below 10%

def read_battery_status():
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

        if percent < LOW_BATTERY_THRESHOLD:
            logging.warning("Battery too low. Initiating shutdown.")
            os.system("sudo shutdown -h now")

    except Exception as e:
        battery_status = {"error": f"Battery read error: {e}"}
        logging.error(f"Battery read failed: {e}")

def battery_monitor():
    while True:
        read_battery_status()
        time.sleep(5)

battery_thread = threading.Thread(target=battery_monitor, daemon=True)
battery_thread.start()

# Ensure directories exist
PHOTO_DIR = "./photos"
THUMB_DIR = os.path.join(PHOTO_DIR, "thumbs")
os.makedirs(PHOTO_DIR, exist_ok=True)
os.makedirs(THUMB_DIR, exist_ok=True)

def create_thumbnail(photo_path, thumbnail_path, size=(320, 240)):
    try:
        with Image.open(photo_path) as img:
            img.thumbnail(size)
            img.save(thumbnail_path)
    except Exception as e:
        logging.error(f"Thumbnail creation failed: {e}")

def check_internet():
    try:
        requests.get("https://www.google.com", timeout=3)
        return True
    except requests.RequestException:
        return False

# Initialize Camera
camera = Picamera2()
camera.configure(camera.create_still_configuration(main={"size": (2592, 1944)}))
camera.start(show_preview=False)
time.sleep(1)

def get_timestamp_filename():
    return datetime.now().strftime("%Y%m%d_%H%M%S") + ".jpg"

def take_photo():
    filename = get_timestamp_filename()
    photo_path = os.path.join(PHOTO_DIR, filename)
    thumb_path = os.path.join(THUMB_DIR, filename)
    try:
        camera.capture_file(photo_path)
        logging.info(f"Photo taken and saved: {photo_path}")
        create_thumbnail(photo_path, thumb_path)
    except Exception as e:
        logging.error(f"Photo capture failed: {e}")

def button_callback(channel):
    start_time = time.time()
    while GPIO.input(BUTTON_PIN) == 0:
        time.sleep(0.1)
        if time.time() - start_time > 3:
            logging.info("Long press detected, shutting down.")
            os.system("sudo shutdown -h now")
            return
    logging.info("Button press detected, taking photo.")
    take_photo()
    time.sleep(0.2)

GPIO.add_event_detect(BUTTON_PIN, GPIO.FALLING, callback=button_callback, bouncetime=300)

@app.route('/')
def index():
    image_filenames = sorted(os.listdir(PHOTO_DIR))
    image_filenames = [f for f in image_filenames if f.endswith('.jpg') and not f.startswith("thumbs")]
    return render_template('index.html', battery=battery_status, images=image_filenames)

@app.route('/photos/<path:filename>')
def serve_photo(filename):
    return send_from_directory(PHOTO_DIR, filename)

@app.route('/thumbs/<path:filename>')
def serve_thumbnail(filename):
    return send_from_directory(THUMB_DIR, filename)

@app.route('/shutdown', methods=['POST'])
def shutdown():
    os.system('sudo shutdown -h now')
    return "Shutting down...", 200

def run_flask():
    app.run(host='0.0.0.0', port=8080, debug=False)

if check_internet():
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logging.info("Internet connected. Flask server started on port 80.")
else:
    logging.warning("No internet connection. Flask server not started.")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    logging.info("Keyboard interrupt received. Exiting program.")
finally:
    GPIO.cleanup()
    camera.stop()
    logging.info("Cleanup completed. Program exited.")
