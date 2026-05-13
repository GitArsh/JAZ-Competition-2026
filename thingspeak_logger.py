import serial # Read serial data from Arduino
import requests # Send data to ThingSpeak via HTTP requests

import time # For timing ThingSpeak updates

from dotenv import load_dotenv # Load environment variables from .env file
import os # For environment variables (ThingSpeak API key)

load_dotenv()

SERIAL_PORT = "COM3" # Match the port your Arduino is connected to (e.g., "COM3" on Windows or "/dev/ttyUSB0" on Linux)
BAUD_RATE = 9600 # Match the baud rate set in your Arduino sketch
THINGSPEAK_API_KEY = os.environ["THINGSPEAK_API_KEY"]
THINGSPEAK_URL = "https://api.thingspeak.com/update"
MIN_INTERVAL = 15  # ThingSpeak free tier limit: 1 update per 15 seconds

ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
print(f"Listening on {SERIAL_PORT}, logging to ThingSpeak...")

last_post = 0.0 # Non-blocking timing for ThingSpeak updates

while True:
    line = ser.readline().decode("utf-8", errors="replace").rstrip()
    if not line:
        continue

    print(line)

    parts = line.split()
    if len(parts) < 3:
        continue

    value = parts[2] # Assuming the serial message is "LED status X", where X is the value we need

    now = time.time()
    if now - last_post < MIN_INTERVAL: # Too soon to post again, skip this reading
        continue

    response = requests.get(f"{THINGSPEAK_URL}?api_key={THINGSPEAK_API_KEY}&field1={value}")
    if response.status_code == 200 and response.text != "0":
        print(f"  -> Posted field1={value} (entry {response.text})")
    else:
        print(f"  -> ThingSpeak error: {response.status_code} {response.text}")

    last_post = now
