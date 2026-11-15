
import time
from smbus2 import SMBus

ADDRESS = 0x6A

# LSM6DSL registers
CTRL1_XL = 0x10
CTRL2_G = 0x11
OUTX_L_G = 0x22
OUTX_L_XL = 0x28

def signed16(low, high):
    value = (high << 8) | low
    return value - 65536 if value >= 32768 else value

def read_xyz(bus, start_register):
    data = bus.read_i2c_block_data(ADDRESS, start_register, 6)
    return [
        signed16(data[i], data[i + 1])
        for i in (0, 2, 4)
    ]

with SMBus(1) as bus:
    # Accelerometer: 104 Hz, +/-2g
    bus.write_byte_data(ADDRESS, CTRL1_XL, 0x40)

    # Gyroscope: 104 Hz, +/-245 dps
    bus.write_byte_data(ADDRESS, CTRL2_G, 0x40)

    time.sleep(0.2)

    try:
        while True:
            accel_raw = read_xyz(bus, OUTX_L_XL)
            gyro_raw = read_xyz(bus, OUTX_L_G)

            # +/-2g sensitivity: 0.061 mg/LSB
            accel = [v * 0.000061 * 9.80665 for v in accel_raw]

            # +/-245 dps sensitivity: 8.75 mdps/LSB
            gyro = [v * 0.00875 for v in gyro_raw]

            print(
                f"Accel (m/s²): "
                f"X={accel[0]:7.3f} "
                f"Y={accel[1]:7.3f} "
                f"Z={accel[2]:7.3f} | "
                f"Gyro (°/s): "
                f"X={gyro[0]:7.2f} "
                f"Y={gyro[1]:7.2f} "
                f"Z={gyro[2]:7.2f}"
            )

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nStopped.")
