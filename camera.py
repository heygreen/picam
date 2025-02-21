import RPi.GPIO as GPIO
import time
from picamera2 import Picamera2
import os
import immich_upload

# Setup
GPIO.setmode(GPIO.BCM)
BUTTON_PIN = 17
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Ensure the photos directory exists
PHOTO_DIR = "./photos"
os.makedirs(PHOTO_DIR, exist_ok=True)

# Initialize Camera
camera = Picamera2()
camera.configure(camera.create_still_configuration(main={"size": (2592, 1944)}))
camera.start(show_preview=False)
time.sleep(1)  # Give the camera time to initialize

def get_next_filename():
    """Find the next available filename."""
    i = 1
    while True:
        filename = os.path.join(PHOTO_DIR, f"photo_{i}.jpg")
        if not os.path.exists(filename):
            return filename
        i += 1

def take_photo():
    """Capture a photo and save it with a unique name."""
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
    """Callback for when the button is pressed."""
    print("📸 Button Pressed! Taking a photo...")
    take_photo()
    time.sleep(0.2)  # Short debounce delay

print("🔴 Ready! Press the button to take a photo...")

# Detect button press
GPIO.add_event_detect(BUTTON_PIN, GPIO.FALLING, callback=button_callback, bouncetime=300)

try:
    while True:
        time.sleep(1)  # Keep the script running
except KeyboardInterrupt:
    print("\n🛑 Exiting program...")
finally:
    GPIO.cleanup()
    camera.stop()
    print("✅ Cleanup done.")
