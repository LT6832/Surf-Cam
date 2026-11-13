
import json
import time
import statistics
from pathlib import Path
from smbus2 import SMBus

# -----------------------------
# Configuration
# -----------------------------

ADDRESS = 0x6A
SAMPLES = 500

OUTPUT_FILE = (
    Path(__file__).resolve().parent
    / "imu_calibration.json"
)


# -----------------------------
# Helper functions
# -----------------------------

def signed16(low, high):
    value = (high << 8) | low
    return value - 65536 if value >= 32768 else value


def read_gyro(bus):
    raw = bus.read_i2c_block_data(
        ADDRESS, 0x22, 6
    )

    values = [
        signed16(raw[i], raw[i + 1])
        for i in (0, 2, 4)
    ]

    # Convert raw values to degrees/second
    return [
        value * 0.00875
        for value in values
    ]


# -----------------------------
# Calibration function
# -----------------------------

def calibrate_gyro():
    print("Calibrating gyroscope...")
    print("Keep the Raspberry Pi completely stationary.")

    with SMBus(1) as bus:

        # Enable block data update
        bus.write_byte_data(ADDRESS, 0x12, 0x44)

        # Gyroscope: 104 Hz, +/-245 degrees/second
        bus.write_byte_data(ADDRESS, 0x11, 0x40)

        # Allow sensor to stabilize
        time.sleep(0.5)

        samples = []

        for _ in range(SAMPLES):
            samples.append(read_gyro(bus))
            time.sleep(0.01)

    # Calculate average offset for each axis
    bias = [
        statistics.mean(
            sample[axis] for sample in samples
        )
        for axis in range(3)
    ]

    # Calculate noise for each axis
    noise = [
        statistics.stdev(
            sample[axis] for sample in samples
        )
        for axis in range(3)
    ]

    # Store calibration results
    calibration = {}
    
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, "r") as file:
            calibration = json.load(file)


    calibration["gyro_bias_dps"] = bias

    with open(OUTPUT_FILE, "w") as file:
        json.dump(calibration, file, indent=4)

    print("\nGYROSCOPE CALIBRATION")
    print("---------------------")

    for axis, offset, std in zip("XYZ", bias, noise):
        print(
            f"{axis}: "
            f"bias={offset:+.4f} °/s, "
            f"noise={std:.4f} °/s"
        )

    print(f"\nCalibration saved to: {OUTPUT_FILE}")

    return bias


# -----------------------------
# Standalone execution
# -----------------------------

if __name__ == "__main__":
    calibrate_gyro()
