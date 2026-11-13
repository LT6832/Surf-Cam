
import serial
import struct
import time

GPS_PORT = "/dev/serial0"
OLD_BAUD = 9600
NEW_BAUD = 460800


def create_ubx_message(msg_class, msg_id, payload):
    """Create a UBX packet with a checksum."""

    body = bytes([msg_class, msg_id])
    body += struct.pack("<H", len(payload))
    body += payload

    ck_a = 0
    ck_b = 0

    for byte in body:
        ck_a = (ck_a + byte) & 0xFF
        ck_b = (ck_b + ck_a) & 0xFF

    return b"\xb5\x62" + body + bytes([ck_a, ck_b])


def change_baud_rate():
    # UBX-CFG-PRT configuration for UART1
    payload = struct.pack(
        "<BBHIIHHHH",
        1,          # portID: UART1
        0,          # reserved
        0,          # txReady disabled
        0x000008D0, # 8 data bits, no parity, 1 stop bit
        NEW_BAUD,   # Requested baud rate
        0x0007,     # Input protocols: UBX, NMEA, RTCM
        0x0003,     # Output protocols: UBX, NMEA
        0,          # flags
        0           # reserved
    )

    message = create_ubx_message(0x06, 0x00, payload)

    print(f"Opening GPS at {OLD_BAUD} baud...")

    with serial.Serial(GPS_PORT, OLD_BAUD, timeout=1) as gps:
        gps.write(message)
        gps.flush()

        print(f"Requested baud change to {NEW_BAUD}")

    # Give the receiver time to switch
    time.sleep(0.5)

    print(f"Reopening GPS at {NEW_BAUD} baud...")

    with serial.Serial(GPS_PORT, NEW_BAUD, timeout=2) as gps:
        start = time.monotonic()

        while time.monotonic() - start < 10:
            line = gps.readline().decode(
                "ascii", errors="replace"
            ).strip()

            if line.startswith(("$GNRMC", "$GPRMC",
                                "$GNGGA", "$GPGGA")):
                print("SUCCESS! Received:", line)
                return

    print("No valid NMEA messages detected at the new baud rate.")
    print("The receiver may not have accepted the setting.")


if __name__ == "__main__":
    change_baud_rate()
