
import json
import math
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

import serial
from smbus2 import SMBus
import board
import adafruit_bmp3xx

from gps_dashboard import (
    GPS_PORT,
    GPS_BAUD,
    BARO_ADDRESS,
    parse_rmc,
    parse_gga,
    initialize_sensors,
    read_motion_sensors,
    read_magnetometer,
    read_barometer,
    load_accel_calibration,
)

from calibration.gyro_calibrate import calibrate_gyro


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent

RADIO_PORT = "/dev/ttyUSB0"
RADIO_BAUD = 460800

SEND_INTERVAL = 0.1
SENSOR_INTERVAL = 0.05
BARO_INTERVAL = 0.5

SYNC = b"\xAA\x55\xAA\x55"
PACKET_FORMAT = "<Iiih3h3h3hBB"

CALIBRATION_FILE = (
    PROJECT_DIR / "calibration" / "imu_calibration.json"
)

MAG_CALIBRATION_FILE = (
    PROJECT_DIR / "calibration" / "mag_calibration.json"
)

STATIONARY_SAMPLES = 30
STATIONARY_SAMPLE_INTERVAL = 0.05
STATIONARY_WAIT = 10.0

MAX_GYRO_RATE = 3.0
MAX_ACCEL_DEVIATION = 0.6
MAX_ACCEL_RANGE = 0.35

GRAVITY = 9.80665


# ============================================================
# GPS CONFIGURATION
# ============================================================

def configure_gps():
    for script in ["gps_baud.py", "gps_config.py"]:
        print(f"Running {script}...", flush=True)

        subprocess.run(
            [sys.executable, str(PROJECT_DIR / script)],
            cwd=PROJECT_DIR,
            check=True,
        )


# ============================================================
# CALIBRATION LOADING
# ============================================================

def load_saved_gyro_bias():
    try:
        with open(CALIBRATION_FILE, "r") as file:
            calibration = json.load(file)

        bias = calibration["gyro_bias_dps"]

        if len(bias) != 3:
            raise ValueError("Expected 3 gyro bias values")

        bias = [float(v) for v in bias]

        if not all(math.isfinite(v) for v in bias):
            raise ValueError("Invalid gyro bias")

        print(
            f"Loaded saved gyro bias: {bias}",
            flush=True,
        )

        return bias

    except (OSError, ValueError, KeyError, TypeError) as error:
        print(
            f"Unable to load gyro calibration: {error}",
            flush=True,
        )
        return None


def load_mag_calibration():
    """
    Load magnetometer offsets and scales from the
    existing calibration file.

    If the file is missing or invalid, use identity
    calibration and transmit uncorrected readings.
    """

    try:
        with open(MAG_CALIBRATION_FILE, "r") as file:
            calibration = json.load(file)

        # Accept either naming convention.
        offsets = calibration.get(
            "offsets",
            calibration.get("mag_offset_ut")
        )

        scales = calibration.get(
            "scales",
            calibration.get("mag_scale")
        )

        if offsets is None or scales is None:
            raise ValueError(
                "Magnetometer offsets/scales not found"
            )

        if len(offsets) != 3 or len(scales) != 3:
            raise ValueError(
                "Expected 3 magnetometer values per axis"
            )

        offsets = [float(v) for v in offsets]
        scales = [float(v) for v in scales]

        if not all(
            math.isfinite(v) for v in offsets + scales
        ):
            raise ValueError(
                "Non-finite magnetometer calibration"
            )

        if any(v <= 0 for v in scales):
            raise ValueError(
                "Magnetometer scales must be positive"
            )

        print(
            "Loaded magnetometer calibration.",
            flush=True,
        )
        print(
            f"Mag offsets: {offsets}",
            flush=True,
        )
        print(
            f"Mag scales: {scales}",
            flush=True,
        )

        return offsets, scales

    except (OSError, ValueError, KeyError, TypeError) as error:
        print(
            f"WARNING: Magnetometer calibration "
            f"not loaded: {error}",
            flush=True,
        )
        return [0.0, 0.0, 0.0], [1.0, 1.0, 1.0]


def calibrate_magnetometer(mag, offsets, scales):
    return [
        (mag[i] - offsets[i]) * scales[i]
        for i in range(3)
    ]


# ============================================================
# STATIONARY DETECTION
# ============================================================

def is_stationary(
    bus,
    accel_offset,
    accel_scale,
    saved_bias,
):
    samples = []

    data = {
        "accel": [0.0, 0.0, 0.0],
        "gyro": [0.0, 0.0, 0.0],
        "accel_total": 0.0,
        "pitch": 0.0,
        "roll": 0.0,
    }

    # Use the saved bias only for checking movement.
    # The actual calibration is performed separately.

    check_bias = (
        saved_bias
        if saved_bias is not None
        else [0.0, 0.0, 0.0]
    )

    for _ in range(STATIONARY_SAMPLES):
        read_motion_sensors(
            bus,
            data,
            check_bias,
            accel_offset,
            accel_scale,
        )

        samples.append(
            (
                list(data["accel"]),
                list(data["gyro"]),
            )
        )

        time.sleep(STATIONARY_SAMPLE_INTERVAL)

    accelerations = [sample[0] for sample in samples]
    gyroscopes = [sample[1] for sample in samples]

    # Check gyro rotation rate.

    for gyro in gyroscopes:
        rotation_rate = math.sqrt(
            sum(value * value for value in gyro)
        )

        if rotation_rate > MAX_GYRO_RATE:
            print(
                f"Movement detected: "
                f"gyro {rotation_rate:.2f} °/s",
                flush=True,
            )
            return False

    # Check acceleration magnitude.

    for accel in accelerations:
        total = math.sqrt(
            sum(value * value for value in accel)
        )

        if abs(total - GRAVITY) > MAX_ACCEL_DEVIATION:
            print(
                f"Movement detected: "
                f"accel {total:.2f} m/s²",
                flush=True,
            )
            return False

    # Check acceleration variation on each axis.

    for axis in range(3):
        values = [
            accel[axis]
            for accel in accelerations
        ]

        axis_range = max(values) - min(values)

        if axis_range > MAX_ACCEL_RANGE:
            print(
                f"Movement detected on axis {axis}: "
                f"{axis_range:.2f} m/s²",
                flush=True,
            )
            return False

    return True


# ============================================================
# STARTUP CALIBRATION
# ============================================================

def startup_calibration(
    bus,
    accel_offset,
    accel_scale,
):
    print(
        "\nStarting automatic calibration...",
        flush=True,
    )

    saved_bias = load_saved_gyro_bias()

    start = time.monotonic()

    while time.monotonic() - start < STATIONARY_WAIT:
        print(
            "Checking whether Pi is stationary...",
            flush=True,
        )

        if is_stationary(
            bus,
            accel_offset,
            accel_scale,
            saved_bias,
        ):
            print(
                "Pi is stationary. Calibrating gyro...",
                flush=True,
            )

            try:
                gyro_bias = calibrate_gyro()

                if (
                    gyro_bias is not None
                    and len(gyro_bias) == 3
                    and all(
                        math.isfinite(float(v))
                        for v in gyro_bias
                    )
                ):
                    gyro_bias = [
                        float(v) for v in gyro_bias
                    ]

                    print(
                        "Gyroscope calibration complete.",
                        flush=True,
                    )

                    return gyro_bias

                print(
                    "Gyro calibration returned invalid data.",
                    flush=True,
                )

            except Exception as error:
                print(
                    f"Gyro calibration failed: {error}",
                    flush=True,
                )

            break

        time.sleep(0.5)

    if saved_bias is not None:
        print(
            "Using previously saved gyro calibration.",
            flush=True,
        )
        return saved_bias

    print(
        "WARNING: No saved gyro bias. "
        "Using zero bias.",
        flush=True,
    )

    return [0.0, 0.0, 0.0]


# ============================================================
# PACKET ENCODING
# ============================================================

def scaled(value, scale, low=-32768, high=32767):
    return max(
        low,
        min(high, int(round(value * scale))),
    )


def make_packet(sequence, data):
    latitude = data["latitude"]
    longitude = data["longitude"]

    lat = (
        int(round(latitude * 1e7))
        if latitude is not None else 0
    )

    lon = (
        int(round(longitude * 1e7))
        if longitude is not None else 0
    )

    speed = scaled(data["speed"], 100)

    accel = [
        scaled(v, 100)
        for v in data["accel"]
    ]

    gyro = [
        scaled(v, 100)
        for v in data["gyro"]
    ]

    mag = [
        scaled(v, 10)
        for v in data["mag"]
    ]

    payload = struct.pack(
        PACKET_FORMAT,
        sequence,
        lat,
        lon,
        speed,
        *accel,
        *gyro,
        *mag,
        int(bool(data["fix"])),
        0,
    )

    checksum = zlib.crc32(payload) & 0xFFFFFFFF

    return (
        SYNC
        + payload
        + struct.pack("<I", checksum)
    )


# ============================================================
# MAIN
# ============================================================

def main():
    print(
        "Starting Surf Tracker Sensor Transmitter V3",
        flush=True,
    )

    with SMBus(1) as bus:
        initialize_sensors(bus)

        # Load accelerometer calibration.

        accel_offset, accel_scale = (
            load_accel_calibration()
        )

        print(
            "Loaded accelerometer calibration.",
            flush=True,
        )

        # Automatically calibrate gyro when stationary.

        gyro_bias = startup_calibration(
            bus,
            accel_offset,
            accel_scale,
        )

        # Load magnetometer calibration.

        mag_offsets, mag_scales = (
            load_mag_calibration()
        )

        # Configure GPS.

        configure_gps()

        data = {
            "fix": False,
            "latitude": None,
            "longitude": None,
            "speed": 0.0,
            "altitude": None,
            "time": None,
            "accel": [0.0, 0.0, 0.0],
            "gyro": [0.0, 0.0, 0.0],
            "accel_total": 0.0,
            "pitch": 0.0,
            "roll": 0.0,
            "mag": [0.0, 0.0, 0.0],
            "mag_total": 0.0,
            "temperature": 0.0,
            "pressure": 0.0,
        }

        i2c = board.I2C()

        bmp = adafruit_bmp3xx.BMP3XX_I2C(
            i2c,
            address=BARO_ADDRESS,
        )

        sequence = 0

        last_sensor_read = 0.0
        last_baro_read = 0.0
        last_send = time.monotonic()

        with serial.Serial(
            GPS_PORT,
            GPS_BAUD,
            timeout=0.02,
        ) as gps:

            with serial.Serial(
                RADIO_PORT,
                RADIO_BAUD,
                timeout=0.1,
                write_timeout=1,
            ) as radio:

                print(
                    f"GPS: {GPS_PORT}",
                    flush=True,
                )
                print(
                    f"Radio: {RADIO_PORT}",
                    flush=True,
                )
                print(
                    "Sending calibrated telemetry "
                    "at 10 Hz.",
                    flush=True,
                )

                try:
                    while True:
                        now = time.monotonic()

                        # ------------------------------
                        # GPS
                        # ------------------------------

                        line = gps.readline().decode(
                            "ascii",
                            errors="replace",
                        ).strip()

                        if line.startswith(
                            ("$GNRMC", "$GPRMC")
                        ):
                            parse_rmc(line, data)

                        elif line.startswith(
                            ("$GNGGA", "$GPGGA")
                        ):
                            parse_gga(line, data)

                        # ------------------------------
                        # IMU AND MAGNETOMETER
                        # ------------------------------

                        if (
                            now - last_sensor_read
                            >= SENSOR_INTERVAL
                        ):
                            read_motion_sensors(
                                bus,
                                data,
                                gyro_bias,
                                accel_offset,
                                accel_scale,
                            )

                            read_magnetometer(
                                bus, data
                            )

                            # Apply saved magnetometer
                            # calibration before sending.

                            data["mag"] = (
                                calibrate_magnetometer(
                                    data["mag"],
                                    mag_offsets,
                                    mag_scales,
                                )
                            )

                            data["mag_total"] = (
                                math.sqrt(
                                    sum(
                                        v * v
                                        for v in data["mag"]
                                    )
                                )
                            )

                            last_sensor_read = now

                        # ------------------------------
                        # BAROMETER
                        # ------------------------------

                        if (
                            now - last_baro_read
                            >= BARO_INTERVAL
                        ):
                            read_barometer(
                                bmp, data
                            )

                            last_baro_read = now

                        # ------------------------------
                        # TRANSMIT
                        # ------------------------------

                        if (
                            now - last_send
                            >= SEND_INTERVAL
                        ):
                            packet = make_packet(
                                sequence, data
                            )

                            radio.write(packet)

                            if sequence % 10 == 0:
                                print(
                                    f"Sent #{sequence} "
                                    f"({len(packet)} bytes) "
                                    f"GPS fix: {data['fix']}",
                                    flush=True,
                                )

                            sequence += 1
                            last_send = now

                except KeyboardInterrupt:
                    print(
                        "\nTransmitter stopped.",
                        flush=True,
                    )


if __name__ == "__main__":
    main()
