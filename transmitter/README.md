# Raspberry Pi Transmitter

This directory contains the software for the Raspberry Pi Zero 2 W telemetry
transmitter. The transmitter reads GPS, accelerometer, gyroscope, magnetometer,
and barometer data from the BerryGPS-IMU v4 module, then sends telemetry to the
base station through an ExpressLRS (ELRS) serial radio.

## Hardware

- Raspberry Pi Zero 2 W
- BerryGPS-IMU v4
- HappyModel ES900RX or compatible ELRS serial radio

The software expects the following Linux device paths:

- GPS: `/dev/serial0`
- ELRS radio: `/dev/ttyUSB0`
- Motion and barometer sensors: I2C

## Installation

These instructions assume a Raspberry Pi running Raspberry Pi OS with network
access.

### 1. Install system packages

Update the operating system and install Python, pip, and I²C support:

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv i2c-tools
```

Enable the interfaces used by the transmitter:

```bash
sudo raspi-config
```

In `Interface Options`, enable `I2C` and `Serial Port`. The serial login shell
should be disabled, while the serial hardware should remain enabled. Reboot when
prompted.

Confirm that the I2C bus is visible:

```bash
sudo i2cdetect -y 1
```

The BerryGPS-IMU sensor addresses should appear in the resulting table when the
module is connected correctly.

### 2. Clone the transmitter code

From the repository root, clone the project onto the Raspberry Pi and
change into this directory:

```bash
cd Surf-Cam/transmitter
```

### 3. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Install the Python packages used by the transmitter:

```bash
python -m pip install pyserial smbus2 adafruit-blinka adafruit-circuitpython-bmp3xx
```

If the current user cannot access the serial device or I²C bus, add the user to
the relevant groups and log in again:

```bash
sudo usermod -aG dialout,i2c "$USER"
```

## GPS configuration

The transmitter expects the GPS to communicate at `460800` baud. Run the setup
scripts with the GPS connected to `/dev/serial0`:

```bash
python gps_baud.py
python gps_config.py
```

`gps_baud.py` changes the GPS baud rate from `9600` to `460800`. Run it only
when the receiver is still using the original baud rate. `gps_config.py` then
requests a 10 Hz GPS update rate.

## Calibration

Calibration scripts are in the `calibration` directory. Keep the IMU stationary
when prompted and run the relevant script from the transmitter directory:

```bash
python calibration/accel_calibrate.py
python calibration/gyro_calibrate.py
python calibration/mag_calibrate.py
```

Calibration output is written as JSON files under `calibration/` and is ignored
by Git. Recalibrate after changing the sensor mounting or wiring.

## Running the transmitter

Connect the ELRS radio so that it is available as `/dev/ttyUSB0`, connect the
BerryGPS-IMU module, activate the virtual environment, and run:

```bash
source .venv/bin/activate
python sensor_transmitter.py
```

Stop the program with `Ctrl+C`. The transmitter uses the configured serial
ports and sensor addresses defined near the top of `sensor_transmitter.py`.

## Hardware and diagnostic tests

The `testFiles` directory contains small checks for individual components and
radio links. Run them from the transmitter directory with the virtual
environment active:

```bash
python testFiles/imu_test.py
python testFiles/mag_test.py
python testFiles/baro_test.py
python testFiles/gps_jitter.py
python testFiles/telemetry_test.py
```

The airport test scripts use `/dev/ttyUSB0` and should only be run when the ELRS
radio is connected. Stop any other transmitter process before running a serial
test so that two programs do not open the same device.

## Troubleshooting

- If `/dev/serial0` is missing, verify that the serial hardware is enabled and
  the serial console is disabled in `raspi-config`.
- If `/dev/ttyUSB0` is missing, check the radio connection with `ls /dev/ttyUSB*`
  and confirm the user is in the `dialout` group.
- If no I2C devices are detected, check the BerryGPS-IMU wiring, power, SDA/SCL
  connections, and that I²C is enabled.
- If a script reports a missing Python module, activate `.venv` and reinstall
  the packages from the installation step.

> This documentation is still for development and will be updated as the
> project progresses.
