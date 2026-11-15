"""Shared packet decoding and logging for Surf-Cam range tests."""

import csv
import datetime as dt
import math
import struct
import time
import zlib
from pathlib import Path

SYNC = b"\xaa\x55\xaa\x55"
PAYLOAD = struct.Struct("<Iiih3h3h3hBB")
CRC = struct.Struct("<I")
FRAME_LEN = len(SYNC) + PAYLOAD.size + CRC.size
FIELDS = [
    "utc_time",
    "elapsed_s",
    "mode",
    "requested_hz",
    "distance_ft",
    "event",
    "sequence",
    "missing_since_last",
    "valid_total",
    "missing_total",
    "crc_fail_total",
    "duplicate_or_reordered_total",
    "bytes_received_total",
    "latitude",
    "longitude",
    "speed_mph",
    "gps_fix",
    "gap_since_last_valid_s",
    "note",
]


def distance_feet(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Calculates the distance between two GPS coordinates in feet.

    Args:
        lat1: Starting latitude in decimal degrees.
        lon1: Starting longitude in decimal degrees.
        lat2: Ending latitude in decimal degrees.
        lon2: Ending longitude in decimal degrees.

    Returns:
        Great-circle distance in feet.
    """
    earth_radius_feet = 20_902_260.85

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = lat2_rad - lat1_rad
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )

    return 2 * earth_radius_feet * math.asin(min(1.0, math.sqrt(a)))


def valid_position(lat, lon, fix):
    """Checks whether coordinates have a GPS fix and pass basic validity checks.

    Args:
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees.
        fix: GPS fix flag; a truthy value indicates a fix.

    Returns:
        True if a fix exists, coordinates are in range, and they are not both zero.
    """
    return (
        bool(fix) and -90 <= lat <= 90 and -180 <= lon <= 180 and (lat != 0 or lon != 0)
    )


class Receiver:
    def __init__(self, port):
        """Initializes packet buffering, reception counters, and test timing.

        Args:
            port: Open serial connection used to read telemetry bytes.
        """
        self.port = port
        self.buffer = bytearray()
        self.valid = self.missing = self.crc_fail = self.reordered = (
            self.bytes_received
        ) = 0
        self.last_seq = self.last_valid_time = None
        self.start = time.monotonic()

    def poll(self):
        """Reads telemetry bytes and decodes complete frames from the buffer.

        Updates reception counters and retains partial frames for later polls.

        Returns:
            A list of event dictionaries for CRC failures and decoded packets.
            Packet events include sequence, inferred missing count, GPS data,
            speed in mph, and the gap in seconds since the last decoded packet.
            Duplicate or reordered packets receive a distinct event label.
        """
        data = self.port.read(self.port.in_waiting or 1)
        self.bytes_received += len(data)
        self.buffer.extend(data)
        events = []
        while len(self.buffer) >= len(SYNC):
            i = self.buffer.find(SYNC)
            if i < 0:
                del self.buffer[: -(len(SYNC) - 1)]
                break
            if i:
                del self.buffer[:i]
            if len(self.buffer) < FRAME_LEN:
                break
            frame = bytes(self.buffer[:FRAME_LEN])
            payload = frame[len(SYNC) : -CRC.size]
            if zlib.crc32(payload) & 0xFFFFFFFF != CRC.unpack(frame[-CRC.size :])[0]:
                self.crc_fail += 1
                events.append({"event": "crc_fail"})
                del self.buffer[0]
                continue
            del self.buffer[:FRAME_LEN]
            v = PAYLOAD.unpack(payload)
            seq, lat, lon, speed = v[:4]
            fix = v[-2]
            missing_now = 0
            event = "valid"
            if self.last_seq is not None:
                delta = (seq - self.last_seq) & 0xFFFFFFFF
                if delta == 0 or delta > 0x7FFFFFFF:
                    self.reordered += 1
                    event = "duplicate_or_reordered"
                else:
                    missing_now = delta - 1
                    self.missing += missing_now
                    self.last_seq = seq
            else:
                self.last_seq = seq
            now = time.monotonic()
            gap = None if self.last_valid_time is None else now - self.last_valid_time
            self.last_valid_time = now
            self.valid += 1
            events.append(
                {
                    "event": event,
                    "sequence": seq,
                    "missing_since_last": missing_now,
                    "latitude": lat / 1e7,
                    "longitude": lon / 1e7,
                    "speed_mph": speed / 100,
                    "gps_fix": fix,
                    "gap_since_last_valid_s": gap,
                }
            )
        return events

    def loss_pct(self):
        """Returns inferred missing packets as a percentage of valid plus missing."""
        total = self.valid + self.missing
        return 100 * self.missing / total if total else 0.0


def output_path(mode):
    """Creates the results directory and builds a timestamped CSV path.

    Args:
        mode: Test mode used as the filename prefix.

    Returns:
        Path for the results file; the file itself is not created here.
    """
    directory = Path(__file__).resolve().parent / "results"
    directory.mkdir(exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    return directory / f"{mode}_{stamp}.csv"


def log_event(writer, receiver, mode, hz, distance, event, note):
    """Writes one event and the current receiver totals to the CSV log.

    Args:
        writer: CSV writer that receives the row in FIELDS order.
        receiver: Receiver supplying cumulative counters and the start time.
        mode: Test mode recorded in the row.
        hz: Requested packet frequency recorded in the row.
        distance: Distance in meters, or None if unavailable.
        event: Dictionary describing a decoded packet or CRC failure.
        note: User-provided text included in the row.
    """
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")
    writer.writerow(
        [
            now,
            round(time.monotonic() - receiver.start, 3),
            mode,
            hz,
            round(distance, 2) if distance is not None else "",
            event["event"],
            event.get("sequence", ""),
            event.get("missing_since_last", ""),
            receiver.valid,
            receiver.missing,
            receiver.crc_fail,
            receiver.reordered,
            receiver.bytes_received,
            event.get("latitude", ""),
            event.get("longitude", ""),
            event.get("speed_mph", ""),
            event.get("gps_fix", ""),
            (
                round(event["gap_since_last_valid_s"], 3)
                if event.get("gap_since_last_valid_s") is not None
                else ""
            ),
            note,
        ]
    )


def run_receiver(
    mode, port_name, baud, hz, seconds, note="", distance=None, baseline_samples=100
):
    """Receives telemetry, logs events, and prints periodic range-test status.

    Continuous mode averages initial valid GPS positions to establish a baseline
    and then measures distance from it. Stationary mode logs the supplied
    distance. Reception stops after the duration or a keyboard interrupt.

    Args:
        mode: Test mode, either 'continuous' or 'stationary'.
        port_name: Serial port connected to the receiver.
        baud: Serial baud rate.
        hz: Requested packet frequency recorded in the log; does not set Pi rate.
        seconds: Test duration in seconds, or zero to run until interrupted.
        note: Optional text included in each CSV row.
        distance: Initial distance in meters, or None if unavailable.
        baseline_samples: Number of valid GPS positions averaged for the
            continuous-mode baseline.

    Returns:
        Path to the CSV results file.
    """
    import serial

    positions = []
    baseline = None
    last_distance = distance
    output = output_path(mode)
    with serial.Serial(port_name, baud, timeout=0.1) as port, output.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.writer(file)
        writer.writerow(FIELDS)
        rx = Receiver(port)
        last_print = rx.start
        print(
            f"\nMode: {mode} | Receiver: {port_name} | Pi rate: 10 Hz (currently fixed)"
        )
        print(f"Output: {output}\nPress Ctrl+C to stop.\n")
        try:
            while not seconds or time.monotonic() - rx.start < seconds:
                for event in rx.poll():
                    if "latitude" in event and valid_position(
                        event["latitude"], event["longitude"], event["gps_fix"]
                    ):
                        if mode == "continuous":
                            if baseline is None:
                                positions.append(
                                    (event["latitude"], event["longitude"])
                                )
                                if len(positions) >= baseline_samples:
                                    baseline = (
                                        sum(p[0] for p in positions) / len(positions),
                                        sum(p[1] for p in positions) / len(positions),
                                    )
                                    print(
                                        f"GPS baseline locked: {baseline}. You can move now."
                                    )
                            if baseline:
                                last_distance = distance_feet(
                                    *baseline, event["latitude"], event["longitude"]
                                )
                    log_event(writer, rx, mode, hz, last_distance, event, note)
                now = time.monotonic()
                if now - last_print >= 2:
                    elapsed = now - rx.start
                    actual = rx.valid / elapsed if elapsed else 0
                    d = (
                        f"{last_distance:.1f} ft"
                        if last_distance is not None
                        else "GPS calibrating / unavailable"
                    )
                    print(
                        f"{elapsed:6.1f}s | {d} | Valid {rx.valid} | Missing {rx.missing} | "
                        f"CRC {rx.crc_fail} | Loss {rx.loss_pct():.2f}% | Avg RX {actual:.2f} Hz"
                    )
                    file.flush()
                    last_print = now
        except KeyboardInterrupt:
            pass
        finally:
            file.flush()
            print(
                f"\nFinished: {rx.valid} received, {rx.missing} missing, "
                f"{rx.crc_fail} CRC failures, {rx.loss_pct():.2f}% inferred loss."
            )
            print(f"Saved: {output}")
    return output
