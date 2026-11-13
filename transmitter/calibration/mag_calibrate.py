
import json
import math
import time
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from smbus2 import SMBus

from sensors import initialize_sensors, read_magnetometer


CALIBRATION_TIME = 60
SAMPLE_INTERVAL = 0.05

OUTPUT_FILE = (
    PROJECT_DIR/ "mag_calibration.json"
)


def main():
    print("Initializing magnetometer...")

    data = {"mag": [0.0, 0.0, 0.0], "mag_total": 0.0}

    minimum = [float("inf")] * 3
    maximum = [float("-inf")] * 3

    with SMBus(1) as bus:
        initialize_sensors(bus)

        print()
        print("MAGNETOMETER CALIBRATION")
        print("------------------------")
        print("Rotate the entire enclosure through all orientations.")
        print("Turn it upside down, sideways, and around.")
        print("Keep it away from large metal objects.")
        print()
        input("Press Enter when ready...")

        start = time.monotonic()
        samples = 0

        while time.monotonic() - start < CALIBRATION_TIME:
            read_magnetometer(bus, data)

            values = data["mag"]

            if all(math.isfinite(v) for v in values):
                for axis in range(3):
                    minimum[axis] = min(minimum[axis], values[axis])
                    maximum[axis] = max(maximum[axis], values[axis])

                samples += 1

            remaining = max(
                0,
                CALIBRATION_TIME - (time.monotonic() - start)
            )

            print(
                f"\rSamples: {samples:4d} | "
                f"Time remaining: {remaining:5.1f}s",
                end="",
                flush=True,
            )

            time.sleep(SAMPLE_INTERVAL)

    print("\n")

    if samples < 100:
        raise RuntimeError("Not enough magnetometer samples collected.")

    offsets = [
        (minimum[i] + maximum[i]) / 2
        for i in range(3)
    ]

    radii = [
        (maximum[i] - minimum[i]) / 2
        for i in range(3)
    ]

    if any(radius < 1.0 for radius in radii):
        raise RuntimeError(
            "Insufficient rotation detected on one or more axes."
        )

    average_radius = sum(radii) / 3

    scales = [
        average_radius / radius
        for radius in radii
    ]

    calibration = {
        "mag_offset_ut": offsets,
        "mag_scale": scales,
        "samples": samples,
        "axis_min_ut": minimum,
        "axis_max_ut": maximum,
    }

    OUTPUT_FILE.write_text(
        json.dumps(calibration, indent=2)
    )

    print("Calibration complete!")
    print()
    print("Offsets (uT):", offsets)
    print("Scales:", scales)
    print("Samples:", samples)
    print()
    print("Saved to:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
