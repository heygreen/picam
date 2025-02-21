import RPi.GPIO as GPIO
import time
from picamera2 import Picamera2
import os
import immich_upload

# Setup
GPIO.setmode(GPIO.BCM)
BUTTON_PIN = 17
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

camera = Picamera2()
camera.configure(camera.create_still_configuration())
camera.start()

def get_next_filename():
    """Findet den nächsten verfügbaren Dateinamen."""
    i = 1
    while True:
        filename = f"./photos/photo_{i}.jpg"
        if not os.path.exists(filename):
            return filename
        i += 1

def take_photo():
    """Macht ein Foto und speichert es mit einem eindeutigen Namen."""
    filename = get_next_filename()
    camera.capture_file(filename)
    print(f"Foto gespeichert als {filename}")
    try:
        immich_upload.upload(filename)
    except:
        print('Error while trying to upload image to immich.')

print("Drücke den Button, um ein Foto zu machen...")
try:
    while True:
        if GPIO.input(BUTTON_PIN) == GPIO.LOW:
            take_photo()
            time.sleep(0.5)  # Entprellung
except KeyboardInterrupt:
    print("Beende Programm...")
finally:
    GPIO.cleanup()
    camera.stop()
