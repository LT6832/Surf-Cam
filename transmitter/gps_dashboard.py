
import math
import time
import serial
import json
from smbus2 import SMBus

import board
import adafruit_bmp3xx

from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from rich.console import Group
from calibration.gyro_calibrate import calibrate_gyro
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


# -----------------------------
# Dashboard functions
# -----------------------------

def make_table(rows):
    table = Table.grid(padding=(0, 2))
    table.add_column(style="cyan", width=15)
    table.add_column(justify="right", width=20)

    for label, value in rows:
        table.add_row(label, str(value))

    return table


def format_xyz(values, unit, decimals=2):
    if values is None:
        return "Waiting..."

    return [
        f"{value:.{decimals}f} {unit}"
        for value in values
    ]


def create_dashboard(data):
    gps_panel = Panel(
        make_table([
            ("Status", "FIX" if data["fix"] else "NO FIX"),
            ("Latitude", data["latitude"]),
            ("Longitude", data["longitude"]),
            ("Speed", f'{data["speed"]:.2f} mph'),
            ("GPS Time", data["time"] or "Waiting..."),
            (
                "Altitude",
                f'{data["altitude"]:.1f} m'
                if data["altitude"] is not None
                else "Waiting..."
            ),
        ]),
        title="GPS",
        border_style="cyan",
        width=42,
    )

    accel = format_xyz(data["accel"], "m/s²")
    gyro = format_xyz(data["gyro"], "°/s")
    mag = format_xyz(data["mag"], "µT")

    motion_panel = Panel(
        make_table([
            ("Accel X", accel[0] if isinstance(accel, list) else accel),
            ("Accel Y", accel[1] if isinstance(accel, list) else accel),
            ("Accel Z", accel[2] if isinstance(accel, list) else accel),
            ("Total", f'{data["accel_total"]:.2f} m/s²'),
            ("Pitch", f'{data["pitch"]:.1f}°'),
            ("Roll", f'{data["roll"]:.1f}°'),
            ("Gyro X", gyro[0] if isinstance(gyro, list) else gyro),
            ("Gyro Y", gyro[1] if isinstance(gyro, list) else gyro),
            ("Gyro Z", gyro[2] if isinstance(gyro, list) else gyro),
        ]),
        title="ACCELEROMETER + GYROSCOPE",
        border_style="green",
        width=42,
    )

    mag_panel = Panel(
        make_table([
            ("Mag X", mag[0] if isinstance(mag, list) else mag),
            ("Mag Y", mag[1] if isinstance(mag, list) else mag),
            ("Mag Z", mag[2] if isinstance(mag, list) else mag),
            ("Total", f'{data["mag_total"]:.2f} µT'),
        ]),
        title="MAGNETOMETER",
        border_style="magenta",
        width=42,
    )

    baro_panel = Panel(
        make_table([
            (
                "Temperature",
                f'{data["temperature"] * 9/5 + 32:.2f} °F'
            ),
            ("Pressure", f'{data["pressure"]:.2f} hPa'),
        ]),
        title="BAROMETER",
        border_style="yellow",
        width=42,
    )

    return Group(
        Columns([gps_panel, motion_panel], equal=False),
        Columns([mag_panel, baro_panel], equal=False),
    )


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


# -----------------------------
# Main
# -----------------------------

def main():
    gyro_bias = calibrate_gyro()
    accel_offset, accel_scale = load_accel_calibration()


    data = {
        "fix": False,
        "latitude": None,
        "longitude": None,
        "speed": 0.0,
        "altitude": None,
        "time": None,
        "accel": [0, 0, 0],
        "gyro": [0, 0, 0],
        "accel_total": 0.0,
        "pitch": 0.0,
        "roll": 0.0,
        "mag": [0, 0, 0],
        "mag_total": 0.0,
        "temperature": 0.0,
        "pressure": 0.0,
    }

    i2c = board.I2C()
    bmp = adafruit_bmp3xx.BMP3XX_I2C(
        i2c, address=BARO_ADDRESS
    )

    with SMBus(1) as bus:
        initialize_sensors(bus)

        with serial.Serial(
            GPS_PORT, GPS_BAUD, timeout=0.05
        ) as gps:

            with Live(
                create_dashboard(data),
                refresh_per_second=4,
                screen=True,
            ) as live:

                last_sensor_read = 0
                last_baro_read = 0

                while True:
                    now = time.monotonic()

                    # Read GPS continuously
                    line = gps.readline().decode(
                        "ascii", errors="replace"
                    ).strip()

                    if line.startswith(("$GNRMC", "$GPRMC")):
                        parse_rmc(line, data)

                    elif line.startswith(("$GNGGA", "$GPGGA")):
                        parse_gga(line, data)

                    # Motion and magnetic sensors: ~20 Hz
                    if now - last_sensor_read >= 0.05:
                        read_motion_sensors(bus, data, gyro_bias, accel_offset, accel_scale)
                        read_magnetometer(bus, data)
                        last_sensor_read = now

                    # Pressure and temperature: ~2 Hz
                    if now - last_baro_read >= 0.5:
                        read_barometer(bmp, data)
                        last_baro_read = now

                    live.update(create_dashboard(data))


if __name__ == "__main__":
    main()
