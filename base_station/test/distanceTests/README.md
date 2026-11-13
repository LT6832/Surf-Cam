# SurfTracker — Telemetry Range Testing

## Overview

The Telemetry Range Test evaluates the reliability and effective transmission range of the ExpressLRS (ELRS) communication system used in the SurfTracker capstone project.

The program receives binary telemetry packets transmitted by a Raspberry Pi Zero 2 W and analyzes packet loss, data corruption, and transmission distance. The results are saved to a CSV file for further analysis.

The purpose of this test is to determine the distance at which the wireless connection begins to degrade and evaluate whether the communication system can reliably support real-time surfer tracking.

## System Configuration

The test uses the existing SurfTracker hardware and telemetry transmission software.

**Transmitting Device**
- Raspberry Pi Zero 2 W
- BerryGPS-IMU v4
- HappyModel ES900RX
- Existing binary telemetry transmitter

**Receiving Device**
- Windows PC
- HappyModel ES900TX
- Python telemetry range testing program

**Communication Settings**

| Parameter | Value |
|---|---|
| Communication protocol | ExpressLRS Airport |
| Radio frequency band | 900 MHz |
| Serial port | COM5 |
| Baud rate | 460800 |
| Packet format | Binary |
| Data validation | CRC32 |

The serial port and baud rate are defined as constants at the beginning of `telemetry_range_test.py` and can be modified if necessary.

## Setup

### 1. Install Dependencies

Python 3 and the PySerial library are required on the receiving computer.

Install PySerial using:

```powershell
python -m pip install pyserial
```

### 2. Configure the Program

Open `telemetry_range_test.py` and locate the serial configuration variables:

```python
SERIAL_PORT = "COM5"
BAUD_RATE = 460800
```

Modify these values only if the receiving computer uses a different serial port or baud rate.

### 3. Start Telemetry Transmission

The Raspberry Pi must be running the existing SurfTracker binary telemetry transmitter.

If the transmitter is configured to start automatically through systemd, no additional action is required.

## Running the Test

### 1. Start the Receiver

Open PowerShell in the directory containing `telemetry_range_test.py` and execute:

```powershell
python telemetry_range_test.py
```

The program immediately begins receiving and analyzing telemetry packets.

### 2. Establish the Starting Position

Keep the Raspberry Pi near the stationary receiving computer while the program collects its initial GPS measurements.

By default, the program averages 30 valid GPS positions to establish the starting coordinates.

Once calibration is complete, the terminal displays:

```text
GPS baseline locked:
Latitude: ...
Longitude: ...
You can move now!
```

This position serves as the reference point for all subsequent distance calculations.

### 3. Perform the Range Test

Move the Raspberry Pi away from the receiving computer while keeping the range testing program running.

The terminal continuously displays:

- Distance from the starting position
- Successfully received packets
- CRC validation failures
- Missing packets
- Cumulative packet loss percentage

Continue increasing the distance until the connection becomes unreliable or the desired testing range has been reached.

### 4. End the Test

Press `Ctrl+C` to stop the program.

A summary of the transmission statistics is displayed, and the collected data is saved to:

`telemetry_range_results.csv`

## How the Test Works

### Binary Packet Validation

The Raspberry Pi transmits sensor measurements in a compact binary format. Each packet contains a sequence number, telemetry measurements, and a CRC32 checksum.

The receiving program recalculates the checksum and compares it with the transmitted value.

Packets that pass validation are accepted. Packets that fail validation are recorded as CRC errors.

### Packet Loss Detection

Each transmitted packet includes an incrementing sequence number.

The receiver compares consecutive sequence numbers to identify missing packets.

For example, receiving packets 100, 101, and 104 indicates that packets 102 and 103 were not received.

Packet loss is estimated using:

\[
\text{Packet Loss (\%)} =
\frac{\text{Missing Packets}}
{\text{Valid Packets}+\text{Missing Packets}}
\times 100
\]

This measurement provides an indication of communication reliability as distance increases.

### Distance Calculation

The program uses the GPS coordinates transmitted by the Raspberry Pi to calculate its distance from the starting location.

The initial GPS measurements are averaged to reduce positional noise and establish a fixed reference point.

Subsequent positions are compared against this reference using the Haversine formula, which calculates the straight-line distance between two geographic coordinates.

Distance is displayed in both meters and feet.

Because the calculation relies on received GPS telemetry, distance cannot be updated while the wireless connection is completely interrupted.

### Data Logging

The program records received telemetry and communication statistics in a CSV file.

The recorded information includes timestamps, GPS coordinates, calculated distance, packet sequence numbers, CRC failures, missing packets, and communication interruptions.

These measurements can be used to graph packet loss against distance and identify where the communication system begins to lose reliability.

## Testing Considerations

For the most accurate results, testing should be performed outdoors with clear GPS reception and minimal obstructions between the transmitting and receiving devices.

GPS measurements may fluctuate slightly while stationary, causing small variations in the calculated distance.

Additionally, packet loss statistics represent cumulative measurements over the test. Temporary communication problems may therefore be less apparent in the overall packet loss percentage.

## Expected Results

The test is intended to establish the practical operating range of the SurfTracker telemetry communication system.

By comparing packet loss, data corruption, and communication interruptions at increasing distances, the results will help determine whether the current ELRS configuration provides sufficient reliability for real-time surfer tracking and camera control.