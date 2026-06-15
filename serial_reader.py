import serial

SERIAL_PORT = "/dev/cu.usbmodem2201" # Match the port your Arduino is connected to (e.g., "COM3" on Windows or "/dev/ttyUSB0" on Linux)
BAUD_RATE = 115200

ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
print(f"Listening on {SERIAL_PORT}...")

while True:
    line = ser.readline().decode("utf-8", errors="replace").rstrip()
    if line:
        print(line)
