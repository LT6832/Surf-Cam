
import serial
import json
import time

# ExpressLRS AirPort serial connection
PORT = "/dev/ttyUSB0"
BAUD = 460800

with serial.Serial(PORT, BAUD, timeout=1) as radio:
    count = 0

    print(f"Transmitting telemetry on {PORT}")

    while True:
        telemetry = {
            "sequence": count,
            "latitude": 45.5266,
            "longitude": -123.0998,
            "speed_mph": 0.0,
            "accel": [0.0, 0.0, 9.81],
            "gyro": [0.0, 0.0, 0.0]
        }

        message = json.dumps(telemetry) + "\n"
        radio.write(message.encode("utf-8"))

        print(f"Sent #{count}: {message.strip()}")

        count += 1
        time.sleep(0.5)
