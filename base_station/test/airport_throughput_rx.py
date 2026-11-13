import json
import serial

PORT = "COM5"
BAUD = 460800

stats = {}
previous = None
buffer = bytearray()

try:
    with serial.Serial(PORT, BAUD, timeout=0.1) as radio:
        print("Listening for test packets. Press Ctrl+C to finish.")

        while True:
            data = radio.read(radio.in_waiting or 1)
            if not data:
                continue

            buffer.extend(data)

            while b"\n" in buffer:
                raw, _, remaining = buffer.partition(b"\n")
                buffer = bytearray(remaining)

                try:
                    packet = json.loads(raw)
                    phase = int(packet["p"])
                    seq = int(packet["n"])

                    s = stats.setdefault(phase, {
                        "valid": 0,
                        "missing": 0,
                        "invalid": 0
                    })

                    s["valid"] += 1

                    if previous is not None and seq > previous + 1:
                        s["missing"] += seq - previous - 1

                    previous = seq

                except (ValueError, KeyError, TypeError, UnicodeDecodeError):
                    s = stats.setdefault("unknown", {
                        "valid": 0,
                        "missing": 0,
                        "invalid": 0
                    })
                    s["invalid"] += 1

            if len(buffer) > 65536:
                buffer.clear()

except KeyboardInterrupt:
    pass

print("\n=== RESULTS ===")
for phase, s in stats.items():
    print(
        f"Test {phase}: "
        f"Valid={s['valid']} | "
        f"Missing={s['missing']} | "
        f"Invalid={s['invalid']}"
    )