# Surf-Cam

An open-source automated camera tracking system designed to record surfers using GPS telemetry, wireless communication, and computer vision.

## Project Overview

Surf-Cam aims to automatically track and record a specific surfer from a shore-based camera. The system combines real-time positional and motion data from a wearable transmitter with AI-powered image recognition to identify and follow the surfer.

Unlike systems that rely exclusively on computer vision, Surf-Cam uses GPS and motion sensors to help maintain tracking when a surfer is temporarily obscured by waves or other obstacles.

The project is being developed as a Computer Science Capstone Project at Pacific University.

## System Components

The project consists of four primary components:

### 1. Telemetry Transmitter
A Raspberry Pi Zero 2 W collects sensor data from a BerryGPS-IMU v4 module, including:
- GPS position, speed, and altitude
- Accelerometer and gyroscope measurements
- Magnetometer orientation data
- Barometric pressure and temperature

This information is transmitted wirelessly to the base station using ExpressLRS (ELRS).

### 2. Base Station
A shore-based computer receives telemetry data through an ELRS receiver connection and processes it for use by the tracking system.

A Python dashboard displays incoming sensor data and provides tools for monitoring wireless communication performance.

### 3. Computer Vision
The computer vision system uses Ultralytics YOLO26 to detect surfers in video footage.

The goal is to combine visual detection with telemetry data to identify the correct surfer and maintain tracking during temporary visual obstructions.

### 4. Camera Control
The planned camera control system will use telemetry and computer vision data to automatically adjust the camera's pan and tilt, keeping the selected surfer in frame.

## Project Goals

- Automatically identify and track a specific surfer.
- Capture surf sessions without requiring a dedicated camera operator.
- Maintain reliable long-range communication between the surfer and shore.
- Combine GPS telemetry with computer vision to improve tracking reliability.
- Develop a portable, affordable, and adaptable system.
- Make the software available for others to study, modify, and improve.

## Why Surf-Cam?

Existing automated camera systems, such as SOLOSHOT, rely on proprietary hardware and software ecosystems.

Surf-Cam aims to provide a more flexible, open-source alternative that allows developers to access telemetry data, modify tracking algorithms, and integrate their own hardware.

Although initially designed for surfing, the technology could eventually be adapted for other activities, including rowing, water skiing, motorsports, and skateboarding.

## Repository Structure

| Directory | Description |
|---|---|
| [`transmitter/`](transmitter/) | Raspberry Pi sensor collection and ELRS telemetry transmission |
| [`base_station/`](base_station/) | Telemetry receiver, processing, and monitoring dashboard |
| [`computer_vision/`](computer_vision/) | AI-powered surfer detection and tracking |
| [`docs/`](docs/) | Hardware documentation, diagrams, and setup guides |

## Development Status

**Active Development — Capstone Project**

Current development includes:
- Raspberry Pi sensor integration and calibration
- GPS and IMU data collection
- Long-range ELRS telemetry communication
- Base station telemetry dashboard
- Computer vision model development

Future development will focus on integrating telemetry with computer vision and implementing automated camera control.

## Documentation

Detailed setup instructions and technical documentation are available in the following directories:

- [Transmitter Setup](transmitter/README.md)
- [Base Station Setup](base_station/README.md)
- [Computer Vision Setup](computer_vision/README.md)
- [Technical Documentation](docs/README.md)

## License

Surf-Cam is released under the [GNU Affero General Public License v3.0](LICENSE).

See [COPYRIGHT.md](COPYRIGHT.md) for copyright information.
