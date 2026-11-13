
import json
import time
import statistics
from pathlib import Path
from smbus2 import SMBus

ADDRESS = 0x6A
GRAVITY = 9.80665
SAMPLES = 200

OUTPUT_FILE = Path(__file__).resolve().parent / "imu_calibration.json"


def signed16(low, high):
    value = (high << 8) | low
    return value - 65536 if value >= 32768 else value


def read_accel(bus):
    raw = bus.read_i2c_block_data(ADDRESS, 0x28, 6)

    values = [
        signed16(raw[i], raw[i + 1])
        for i in (0, 2, 4)
    ]

    return [value * 0.000061 * GRAVITY for value in values]


def collect_samples(bus, label):
    input(f"\nPlace the Pi with {label} pointing UP, then press Enter...")
    print("Keep the Pi stationary. Collecting samples...")

    time.sleep(1)

    samples = []
    for _ in range(SAMPLES):
        samples.append(read_accel(bus))
        time.sleep(0.01)

    averages = [
        statistics.mean(sample[axis] for sample in samples)
        for axis in range(3)
    ]

    print(
        f"Average: X={averages[0]:+.3f}, "
        f"Y={averages[1]:+.3f}, "
        f"Z={averages[2]:+.3f} m/s²"
    )

    return averages


def calibrate_accel():
    print("ACCELEROMETER CALIBRATION")
    print("-------------------------")
    print("We will measure all six orientations.")
    print("Keep the Pi stationary during each measurement.")

    orientations = [
        ("+X", 0),
        ("-X", 0),
        ("+Y", 1),
        ("-Y", 1),
        ("+Z", 2),
        ("-Z", 2),
    ]

    results = {}

    with SMBus(1) as bus:
        # Block data update + auto increment
        bus.write_byte_data(ADDRESS, 0x12, 0x44)

        # Accelerometer: 104 Hz, +/-2g
        bus.write_byte_data(ADDRESS, 0x10, 0x40)

        time.sleep(0.5)

        for label, axis in orientations:
            results[label] = collect_samples(bus, label)

    offsets = []
    scales = []

    for axis, name in enumerate("XYZ"):
        positive = results[f"+{name}"][axis]
        negative = results[f"-{name}"][axis]

        offset = (positive + negative) / 2
        half_range = (positive - negative) / 2

        if half_range <= 0:
            raise ValueError(
                f"Invalid {name} calibration range. "
                "Check the sensor orientations."
            )

        scale = GRAVITY / half_range

        offsets.append(offset)
        scales.append(scale)

    calibration = {}

    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE) as file:
            calibration = json.load(file)

    calibration["accel_offset_mps2"] = offsets
    calibration["accel_scale"] = scales

    with open(OUTPUT_FILE, "w") as file:
        json.dump(calibration, file, indent=4)

    print("\nCALIBRATION RESULTS")
    print("-------------------")

    for axis, offset, scale in zip("XYZ", offsets, scales):
        print(
            f"{axis}: offset={offset:+.4f} m/s², "
            f"scale={scale:.6f}"
        )

    print(f"\nSaved to: {OUTPUT_FILE}")

    return offsets, scales


if __name__ == "__main__":
    calibrate_accel()
