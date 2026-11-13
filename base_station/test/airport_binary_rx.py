
import serial
import struct
import zlib
import time

PORT = "COM5"
BAUD = 460800

SYNC = b"\xAA\x55\xAA\x55"
PACKET_SIZE = 40

EXPECTED = {
    1: (5, 75),
    2: (10, 150),
    3: (20, 300),
}

stats = {
    test_id: {
        "valid": 0,
        "first": None,
        "last": None,
        "crc_errors": 0,
        "sequences": set()
    }
    for test_id in EXPECTED
}

buffer = bytearray()
bad_frames = 0
discarded_bytes = 0


def process_buffer():
    global buffer, bad_frames, discarded_bytes

    while len(buffer) >= PACKET_SIZE:
        index = buffer.find(SYNC)

        if index == -1:
            discarded_bytes += max(0, len(buffer) - 3)
            buffer = buffer[-3:]
            return

        if index > 0:
            discarded_bytes += index
            del buffer[:index]

        if len(buffer) < PACKET_SIZE:
            return

        packet = bytes(buffer[:PACKET_SIZE])
        payload = packet[4:36]

        received_crc = struct.unpack("<I", packet[36:40])[0]
        calculated_crc = zlib.crc32(payload) & 0xFFFFFFFF

        if received_crc != calculated_crc:
            bad_frames += 1
            del buffer[0]
            continue

        sequence, test_id = struct.unpack("<IB", payload[:5])

        if test_id in stats:
            s = stats[test_id]
            s["valid"] += 1
            s["sequences"].add(sequence)

            if s["first"] is None:
                s["first"] = sequence

            s["last"] = sequence

        del buffer[:PACKET_SIZE]


def main():
    global buffer

    print("Listening for binary packets on COM5...")
    print("Start the Pi transmitter now.")
    print("Press Ctrl+C after all tests finish.\n")

    try:
        with serial.Serial(PORT, BAUD, timeout=0.1) as radio:
            while True:
                incoming = radio.read(radio.in_waiting or 1)

                if incoming:
                    buffer.extend(incoming)
                    process_buffer()

                time.sleep(0.001)

    except KeyboardInterrupt:
        pass

    print("\n========== RESULTS ==========")

    for test_id, (hz, expected) in EXPECTED.items():
        s = stats[test_id]
        received = len(s["sequences"])
        missing = expected - received
        success = 100 * received / expected

        print(f"\nTest {test_id}: {hz} Hz, 40 bytes")
        print(f"  Expected: {expected}")
        print(f"  Valid:    {received}")
        print(f"  Missing:  {missing}")
        print(f"  Success:  {success:.1f}%")

    print(f"\nBad CRC frames: {bad_frames}")
    print(f"Discarded bytes: {discarded_bytes}")


if __name__ == "__main__":
    main()
