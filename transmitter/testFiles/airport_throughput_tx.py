import json
import time
import serial

PORT = "/dev/ttyUSB0"
BAUD = 460800
DURATION = 15
PAUSE = 3

TESTS = [
    (2, 135),
    (5, 135),
    (10, 135),
    (10, 55),
    (20, 55),
]

def make_packet(seq, phase, size):
    packet = {"n": seq, "p": phase, "d": ""}
    base = len((json.dumps(packet, separators=(",", ":")) + "\n").encode())
    packet["d"] = "X" * (size - base)
    return (json.dumps(packet, separators=(",", ":")) + "\n").encode()

with serial.Serial(PORT, BAUD, timeout=0, write_timeout=2) as radio:
    seq = 0
    print("Starting AirPort throughput test...", flush=True)

    for phase, (hz, size) in enumerate(TESTS, 1):
        print(f"\nTest {phase}: {hz} Hz, {size} bytes", flush=True)
        start = time.monotonic()
        count = 0

        while True:
            delay = start + count / hz - time.monotonic()
            if delay > 0:
                time.sleep(delay)

            if time.monotonic() - start >= DURATION:
                break

            radio.write(make_packet(seq, phase, size))
            seq += 1
            count += 1

        print(f"Sent {count} packets", flush=True)

        if phase < len(TESTS):
            time.sleep(PAUSE)

    radio.flush()
    print("\nAll tests finished.", flush=True)
