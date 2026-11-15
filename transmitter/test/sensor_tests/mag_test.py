
import time
from smbus2 import SMBus

ADDRESS = 0x1C

WHO_AM_I = 0x0F
CTRL_REG1 = 0x20
CTRL_REG2 = 0x21
CTRL_REG3 = 0x22
CTRL_REG4 = 0x23
OUT_X_L = 0x28


def signed16(low, high):
    value = (high << 8) | low
    return value - 65536 if value >= 32768 else value


with SMBus(1) as bus:
    chip_id = bus.read_byte_data(ADDRESS, WHO_AM_I)
    print(f"Magnetometer ID: 0x{chip_id:02X}")

    if chip_id != 0x3D:
        raise RuntimeError("Unexpected magnetometer ID")

    # Ultra-high-performance XY, 10 Hz output
    bus.write_byte_data(ADDRESS, CTRL_REG1, 0x70)

    # +/-4 gauss full scale
    bus.write_byte_data(ADDRESS, CTRL_REG2, 0x00)

    # Continuous-conversion mode
    bus.write_byte_data(ADDRESS, CTRL_REG3, 0x00)

    # Ultra-high-performance Z axis
    bus.write_byte_data(ADDRESS, CTRL_REG4, 0x0C)

    time.sleep(0.2)

    try:
        while True:
            # Read X, Y, Z together with register auto-increment
            data = bus.read_i2c_block_data(
                ADDRESS, OUT_X_L | 0x80, 6
            )

            raw = [
                signed16(data[i], data[i + 1])
                for i in (0, 2, 4)
            ]

            # LIS3MDL +/-4 gauss sensitivity: 6842 LSB/gauss
            # 1 gauss = 100 microtesla
            field = [value * 100 / 6842 for value in raw]

            print(
                f"Magnetic field (µT): "
                f"X={field[0]:8.2f} "
                f"Y={field[1]:8.2f} "
                f"Z={field[2]:8.2f}"
            )

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nStopped.")
