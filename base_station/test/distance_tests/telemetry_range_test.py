#!/usr/bin/env python3
"""
SurfTracker - ELRS Telemetry Range Test

Receives binary telemetry from the Raspberry Pi over ELRS.

Features:
- CRC32 corruption detection
- Missing packet detection using sequence numbers
- Duplicate/reordered packet detection
- Automatic GPS starting position calibration
- Distance calculation in meters and feet
- Maximum distance tracking
- CSV logging for later analysis
"""

import argparse
import csv
import datetime as dt
import math
import struct
import time
import zlib
from pathlib import Path

import serial

# --------------------------------------------------
# Configuration
# --------------------------------------------------

SERIAL_PORT = "COM5"
BAUD_RATE = 460800
GPS_CALIBRATION_SAMPLES = 100


# --------------------------------------------------
# Binary packet configuration
# --------------------------------------------------

SYNC = b"\xaa\x55\xaa\x55"

PAYLOAD = struct.Struct("<Iiih3h3h3hBB")
CRC = struct.Struct("<I")

FRAME_LEN = len(SYNC) + PAYLOAD.size + CRC.size


# --------------------------------------------------
# GPS distance calculation
# --------------------------------------------------


def distance_meters(lat1, lon1, lat2, lon2):
    """
    Calculate straight-line distance between two
    GPS coordinates using the Haversine formula.
    """

    earth_radius = 6371008.8

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    delta_lat = lat2 - lat1
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )

    return 2 * earth_radius * math.asin(min(1.0, math.sqrt(a)))


def valid_position(lat, lon, fix):
    """
    Check whether telemetry contains a usable GPS fix.
    """

    return (
        bool(fix) and -90 <= lat <= 90 and -180 <= lon <= 180 and (lat != 0 or lon != 0)
    )


# --------------------------------------------------
# Main program
# --------------------------------------------------


def main():

    parser = argparse.ArgumentParser(
        description="SurfTracker ELRS telemetry range tester"
    )

    parser.add_argument("--csv", default="telemetry_range_results.csv")

    parser.add_argument(
        "--distance",
        type=float,
        default=None,
        help="Optional manual distance in meters",
    )

    parser.add_argument("--note", default="")

    parser.add_argument("--seconds", type=float, default=0)

    args = parser.parse_args()

    if GPS_CALIBRATION_SAMPLES < 1:
        parser.error("GPS_CALIBRATION_SAMPLES must be at least 1")

    # --------------------------------------------------
    # Statistics
    # --------------------------------------------------

    valid = 0
    crc_fail = 0
    missing = 0
    reordered = 0
    byte_count = 0

    last_seq = None
    last_valid_time = None

    buffer = bytearray()

    baseline_positions = []
    baseline = None
    current_distance = None
    max_distance = 0.0

    start = time.monotonic()
    last_print = start

    # Save CSV alongside the Python script.
    # Generate a unique filename using the current date and time

    if args.csv == "telemetry_range_results.csv":
        timestamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"telemetry_range_{timestamp}.csv"
    else:
        filename = args.csv

    output = Path(__file__).resolve().parent / filename

    counter = 1
    while output.exists():
        output = Path(__file__).resolve().parent / (
            f"{Path(filename).stem}_{counter}{Path(filename).suffix}"
        )
        counter += 1

    # --------------------------------------------------
    # CSV columns
    # --------------------------------------------------

    fields = [
        "utc_time",
        "elapsed_s",
        "distance_m",
        "distance_ft",
        "baseline_lat",
        "baseline_lon",
        "note",
        "event",
        "sequence",
        "missing_since_last",
        "valid_total",
        "crc_fail_total",
        "missing_total",
        "duplicate_or_reordered_total",
        "bytes_received_total",
        "lat",
        "lon",
        "speed_mph_raw",
        "fix",
        "gap_since_last_valid_s",
    ]

    # --------------------------------------------------
    # CSV logging
    # --------------------------------------------------

    def log(writer, event, seq="", gap=0, lat="", lon="", speed="", fix="", pause=""):

        distance = args.distance if args.distance is not None else current_distance

        writer.writerow(
            [
                dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds"),
                round(time.monotonic() - start, 3),
                round(distance, 2) if distance is not None else "",
                round(distance * 3.28084, 2) if distance is not None else "",
                baseline[0] if baseline else "",
                baseline[1] if baseline else "",
                args.note,
                event,
                seq,
                gap,
                valid,
                crc_fail,
                missing,
                reordered,
                byte_count,
                lat,
                lon,
                speed,
                fix,
                pause,
            ]
        )

    # --------------------------------------------------
    # Startup information
    # --------------------------------------------------

    print()
    print("======================================")
    print("     SurfTracker ELRS Range Test")
    print("======================================")

    print(f"Port: {SERIAL_PORT}")
    print(f"Baud: {BAUD_RATE}")
    print(f"Packet size: {FRAME_LEN} bytes")
    print(f"CSV output: {output.resolve()}")

    print()

    if args.distance is None:
        print("GPS baseline calibration enabled.")
        print(f"Waiting for {GPS_CALIBRATION_SAMPLES} " "valid GPS packets.")
        print("Keep the Raspberry Pi stationary.")
    else:
        print(f"Manual distance: {args.distance} meters")

    print()
    print("Press Ctrl+C to stop.")
    print()

    # --------------------------------------------------
    # Open serial port and CSV
    # --------------------------------------------------

    with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.2) as port, output.open(
        "w", newline="", encoding="utf-8"
    ) as file:

        writer = csv.writer(file)
        writer.writerow(fields)

        try:

            while not args.seconds or time.monotonic() - start < args.seconds:

                data = port.read(port.in_waiting or 1)

                byte_count += len(data)
                buffer.extend(data)

                # --------------------------------------
                # Find and validate binary packets
                # --------------------------------------

                while len(buffer) >= len(SYNC):

                    index = buffer.find(SYNC)

                    if index == -1:
                        del buffer[:-3]
                        break

                    if index:
                        del buffer[:index]

                    if len(buffer) < FRAME_LEN:
                        break

                    frame = bytes(buffer[:FRAME_LEN])

                    payload = frame[4:-4]

                    crc_expected = CRC.unpack(frame[-4:])[0]

                    crc_actual = zlib.crc32(payload) & 0xFFFFFFFF

                    # ----------------------------------
                    # CRC validation
                    # ----------------------------------

                    if crc_actual != crc_expected:

                        crc_fail += 1

                        log(writer, "crc_fail")

                        # Move one byte forward to
                        # search for the next sync.
                        del buffer[0]

                        continue

                    del buffer[:FRAME_LEN]

                    # ----------------------------------
                    # Decode telemetry
                    # ----------------------------------

                    unpacked = PAYLOAD.unpack(payload)

                    seq = unpacked[0]
                    lat_i = unpacked[1]
                    lon_i = unpacked[2]
                    speed_i = unpacked[3]

                    fix = unpacked[-2]

                    lat = lat_i / 1e7
                    lon = lon_i / 1e7

                    # ----------------------------------
                    # GPS baseline calibration
                    # ----------------------------------

                    if valid_position(lat, lon, fix):

                        if baseline is None:

                            baseline_positions.append((lat, lon))

                            if len(baseline_positions) == GPS_CALIBRATION_SAMPLES:

                                avg_lat = sum(x for x, y in baseline_positions) / len(
                                    baseline_positions
                                )

                                avg_lon = sum(y for x, y in baseline_positions) / len(
                                    baseline_positions
                                )

                                baseline = (avg_lat, avg_lon)

                                print()
                                print("GPS baseline locked:")
                                print(f"Latitude: {avg_lat:.7f}")
                                print(f"Longitude: {avg_lon:.7f}")
                                print("You can move now!")
                                print()

                        if baseline is not None:

                            current_distance = distance_meters(
                                baseline[0], baseline[1], lat, lon
                            )

                            # Track the farthest position
                            # successfully received.
                            max_distance = max(max_distance, current_distance)

                    else:
                        current_distance = None

                    # ----------------------------------
                    # Packet sequence validation
                    # ----------------------------------

                    gap = 0

                    if last_seq is not None:

                        delta = (seq - last_seq) & 0xFFFFFFFF

                        if delta == 0 or delta > 0x7FFFFFFF:

                            reordered += 1

                        else:

                            gap = delta - 1
                            missing += gap

                            last_seq = seq

                    else:

                        last_seq = seq

                    # ----------------------------------
                    # Timing statistics
                    # ----------------------------------

                    now = time.monotonic()

                    if last_valid_time is not None:
                        pause = round(now - last_valid_time, 3)
                    else:
                        pause = ""

                    last_valid_time = now

                    valid += 1

                    # ----------------------------------
                    # Log valid packet
                    # ----------------------------------

                    log(writer, "valid", seq, gap, lat, lon, speed_i / 100, fix, pause)

                # --------------------------------------
                # Print statistics every 2 seconds
                # --------------------------------------

                now = time.monotonic()

                if now - last_print >= 2:

                    total = valid + missing

                    loss_pct = 100 * missing / total if total else 0

                    if args.distance is not None:

                        distance_display = f"{args.distance:.1f} m"

                    elif baseline is None:

                        distance_display = (
                            "Calibrating GPS "
                            f"({len(baseline_positions)}/"
                            f"{GPS_CALIBRATION_SAMPLES})"
                        )

                    elif current_distance is None:

                        distance_display = "GPS fix unavailable"

                    else:

                        feet = current_distance * 3.28084

                        distance_display = (
                            f"{current_distance:.1f} m " f"/ {feet:.1f} ft"
                        )

                    print(
                        f"{now-start:7.1f}s | "
                        f"Distance: {distance_display} | "
                        f"Valid: {valid} | "
                        f"CRC errors: {crc_fail} | "
                        f"Missing: {missing} | "
                        f"Loss: {loss_pct:.2f}%"
                    )

                    file.flush()

                    last_print = now

        except KeyboardInterrupt:
            pass

        finally:

            file.flush()

            total = valid + missing

            loss_pct = 100 * missing / total if total else 0

            print()
            print("======================================")
            print("           FINAL RESULTS")
            print("======================================")

            print(f"Valid packets: {valid}")
            print(f"CRC failures: {crc_fail}")
            print(f"Missing packets: {missing}")
            print(f"Duplicate/reordered: {reordered}")
            print(f"Packet loss: {loss_pct:.2f}%")
            print(f"Bytes received: {byte_count}")

            print()
            print(f"Maximum distance: " f"{max_distance:.2f} meters")
            print(f"Maximum distance: " f"{max_distance * 3.28084:.2f} feet")
            print(f"Maximum distance: " f"{max_distance / 1609.344:.3f} miles")

            print()
            print(f"Results saved to: {output.resolve()}")

            print()
            print(
                "Note: packet loss excludes packets "
                "before the first and after the last "
                "valid packet."
            )


if __name__ == "__main__":
    main()
