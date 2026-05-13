import serial

SERIAL_PORT = "COM3"
BAUD_RATE = 9600

ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
print(f"Listening on {SERIAL_PORT}...")

while True:
    line = ser.readline().decode("utf-8", errors="replace").rstrip()
    if line:
        print(line)
