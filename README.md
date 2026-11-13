# Surf-Cam

Surf-Cam is an open-source automated camera tracking system designed to track and record surfers using GPS telemetry, wireless communication, and computer vision.

The system uses a Raspberry Pi Zero 2 W equipped with GPS and motion sensors to collect positional and orientation data from a surfer. This information is transmitted wirelessly to a shore-based computer using ExpressLRS (ELRS). The base station combines this telemetry with computer vision to identify and track a specific surfer.

The goal is to automatically control a camera's pan and tilt to keep the surfer in frame, even when temporarily obscured by waves.

# Project Components

The project is divided into three main software components:

1. **Transmitter:** Collects GPS, accelerometer, gyroscope, magnetometer, and barometer data using a Raspberry Pi Zero 2 W and BerryGPS-IMU v4. Transmits sensor data to the base station over ELRS.

2. **Base Station:** Receives and processes telemetry data from the transmitter. Includes a Python dashboard for monitoring sensor readings and wireless communication performance.

3. **Computer Vision:** Uses Ultralytics YOLO26 to detect and track surfers in video footage. Future development will integrate telemetry data to improve target identification and tracking.

# Documentation

Setup instructions and technical documentation are available in the following directories:

- [Transmitter Documentation](transmitter/README.md)
- [Base Station Documentation](base_station/README.md)
- [Computer Vision Documentation](computer_vision/README.md)
- [Hardware and System Documentation](docs/README.md)

# Installation

Clone the repository:

```bash
git clone https://github.com/OWNER/Surf-Cam.git
cd Surf-Cam
```

Replace `OWNER` with the repository owner's GitHub username.

Each component has its own dependencies and setup instructions. Refer to the documentation linked above.

# Running Surf-Cam

The transmitter, base station, and computer vision software are currently developed and tested separately.

**Transmitter (Raspberry Pi):**

```bash
# TODO: Add transmitter startup command
```

**Base Station (Windows/Linux):**

```bash
# TODO: Add dashboard startup command
```

**Computer Vision:**

```bash
# TODO: Add computer vision startup command
```

These commands will be updated as the software is integrated.

# Development Status

Surf-Cam is currently under active development.

The following components have been developed and tested:

- GPS and IMU sensor integration and calibration
- Raspberry Pi sensor data collection
- ExpressLRS wireless telemetry communication
- Base station telemetry dashboard

Ongoing development includes computer vision, integration of telemetry with visual tracking, and automated camera control.

# License

Surf-Cam is licensed under the [GNU Affero General Public License v3.0](LICENSE.txt).

Copyright information is available in [COPYRIGHT.md](COPYRIGHT.md).
