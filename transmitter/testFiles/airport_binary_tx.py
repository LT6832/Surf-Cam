
import serial
import struct
import time
import zlib

PORT = "/dev/ttyUSB0"
BAUD = 460800

DURATION = 15
PAUSE = 5

# Test number, frequency, packet size
TESTS = [
    (1, 5, 40),
    (2, 10, 40),
    (3, 20, 40),
]

SYNC = b"\xAA\x55\xAA\x55"


def make_packet(sequence, test_id):
    # 4 sync + 4 sequence + 1 test + 27 data + 4 CRC = 40 bytes
    payload = struct.pack("<IB", sequence, test_id)
    payload += bytes(range(27))

    checksum = zlib.crc32(payload) & 0xFFFFFFFF

    return (
        SYNC
        + payload
        + struct.pack("<I", checksum)
    )


def main():
    total = 0

    with serial.Serial(
        PORT,
        BAUD,
        timeout=0,
        write_timeout=2
    ) as radio:

        print("Starting binary AirPort test...")

        for test_id, hz, size in TESTS:
            print(
                f"\nTest {test_id}: {hz} Hz, {size} bytes",
                flush=True
            )

            start = time.monotonic()
            count = 0

            while True:
                target = start + count / hz
                delay = target - time.monotonic()

                if delay > 0:
                    time.sleep(delay)

                if time.monotonic() - start >= DURATION:
                    break

                packet = make_packet(total, test_id)
                radio.write(packet)

                total += 1
                count += 1

            print(f"Sent {count} packets", flush=True)
            time.sleep(PAUSE)

        radio.flush()

    print(f"\nFinished. Total sent: {total}")


if __name__ == "__main__":
    main()
