
import serial
import struct
import time

GPS_PORT = "/dev/serial0"
GPS_BAUD = 460800
#GPS_Rate is in hz
GPS_RATE = 10


def create_ubx_message(msg_class, msg_id, payload):
    # UBX message header
    message = bytes([msg_class, msg_id])
    message += struct.pack("<H", len(payload))
    message += payload

    # Calculate UBX checksum
    ck_a = 0
    ck_b = 0

    for byte in message:
        ck_a = (ck_a + byte) & 0xFF
        ck_b = (ck_b + ck_a) & 0xFF

    return b"\xb5\x62" + message + bytes([ck_a, ck_b])


def set_update_rate(gps, hz):
    # Time between GPS measurements in milliseconds
    measurement_rate = 1000 // hz

    # UBX-CFG-RATE payload
    payload = struct.pack(
        "<HHH",
        measurement_rate,
        1,  # Navigation rate
        1   # GPS time reference
    )

    message = create_ubx_message(
        0x06,  # CFG class
        0x08,  # RATE message
        payload
    )

    gps.write(message)
    gps.flush()

    print(f"Requested GPS update rate: {hz} Hz")


def main():
    with serial.Serial(GPS_PORT, GPS_BAUD, timeout=1) as gps:
        print("Connected to GPS receiver")

        set_update_rate(gps, GPS_RATE)

        time.sleep(1)

        print("Configuration command sent.")


if __name__ == "__main__":
    main()
