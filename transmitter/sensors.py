import json
import math
import time
from pathlib import Path

# -----------------------------
# Hardware configuration
# -----------------------------

GPS_PORT = "/dev/serial0"
GPS_BAUD = 460800

IMU_ADDRESS = 0x6A
MAG_ADDRESS = 0x1C
BARO_ADDRESS = 0x77

# -----------------------------
# GPS functions
# -----------------------------

def convert_coordinate(value, direction):
    if not value:
        return None

    raw = float(value)
    degrees = int(raw // 100)
    minutes = raw - degrees * 100
    decimal = degrees + minutes / 60

    if direction in ("S", "W"):
        decimal = -decimal

    return decimal


def parse_rmc(line, data):
    fields = line.split(",")

    if len(fields) < 8:
        return

    if fields[1]:
        raw_time = fields[1]
        data["time"] = (
            f"{raw_time[0:2]}:"
            f"{raw_time[2:4]}:"
            f"{raw_time[4:6]} UTC"
        )

    if fields[2] != "A":
        data["fix"] = False
        return

    data["fix"] = True

    data["latitude"] = convert_coordinate(
        fields[3], fields[4]
    )
    data["longitude"] = convert_coordinate(
        fields[5], fields[6]
    )
    data["speed"] = (
        float(fields[7]) * 1.15078
        if fields[7] else 0.0
    )


def parse_gga(line, data):
    fields = line.split(",")

    if len(fields) < 11:
        return

    if fields[6] == "0":
        data["altitude"] = None
        return

    if fields[9]:
        data["altitude"] = float(fields[9])


# -----------------------------
# Sensor functions
# -----------------------------

def signed16(low, high):
    value = (high << 8) | low
    return value - 65536 if value >= 32768 else value


def read_xyz(bus, address, register):
    # Auto-increment is enabled on the LIS3MDL
    if address == MAG_ADDRESS:
        register |= 0x80

    raw = bus.read_i2c_block_data(
        address, register, 6
    )

    return [
        signed16(raw[i], raw[i + 1])
        for i in (0, 2, 4)
    ]


def initialize_sensors(bus):
    # LSM6DSL: accelerometer 104 Hz, +/-2g
    bus.write_byte_data(IMU_ADDRESS, 0x10, 0x40)

    # LSM6DSL: gyroscope 104 Hz, +/-245 dps
    bus.write_byte_data(IMU_ADDRESS, 0x11, 0x40)

    # LIS3MDL magnetometer
    bus.write_byte_data(MAG_ADDRESS, 0x20, 0x70)
    bus.write_byte_data(MAG_ADDRESS, 0x21, 0x00)
    bus.write_byte_data(MAG_ADDRESS, 0x22, 0x00)
    bus.write_byte_data(MAG_ADDRESS, 0x23, 0x0C)

    time.sleep(0.2)


def read_motion_sensors(bus, data, gyro_bias, accel_offset, accel_scale):
    accel_raw = read_xyz(
        bus, IMU_ADDRESS, 0x28
    )
    gyro_raw = read_xyz(
        bus, IMU_ADDRESS, 0x22
    )

    accel = [
        (value * 0.000061 * 9.80665 - accel_offset[i])*accel_scale[i]
        for i, value in enumerate(accel_raw)
    ]
    gyro = [
        value * 0.00875 - gyro_bias[i]
        for i, value in enumerate(gyro_raw)
    ]

    ax, ay, az = accel

    data["accel"] = accel
    data["gyro"] = gyro

    data["accel_total"] = math.sqrt(
        ax**2 + ay**2 + az**2
    )

    # Accelerometer-based orientation.
    # Accurate primarily when not accelerating.
    data["roll"] = math.degrees(
        math.atan2(ay, az)
    )
    data["pitch"] = math.degrees(
        math.atan2(
            -ax,
            math.sqrt(ay**2 + az**2)
        )
    )


def read_magnetometer(bus, data):
    raw = read_xyz(
        bus, MAG_ADDRESS, 0x28
    )

    field = [
        value * 100 / 6842
        for value in raw
    ]

    data["mag"] = field
    data["mag_total"] = math.sqrt(
        sum(value**2 for value in field)
    )


def read_barometer(bmp, data):
    data["temperature"] = bmp.temperature
    data["pressure"] = bmp.pressure


def load_accel_calibration():
    calibration_file = (
        Path(__file__).resolve().parent
        / "calibration"
        / "imu_calibration.json"
    )

    with open(calibration_file) as file:
        calibration = json.load(file)

    return (
        calibration["accel_offset_mps2"],
        calibration["accel_scale"]
    )