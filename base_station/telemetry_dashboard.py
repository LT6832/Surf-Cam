import math
import struct
import time
import zlib
from datetime import datetime

import serial
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# ============================================================
# SERIAL SETTINGS
# ============================================================

PORT = "COM5"
BAUD = 460800
REFRESH_RATE = 10

SYNC = b"\xaa\x55\xaa\x55"
PACKET_FORMAT = "<Iiih3h3h3hBB"

PAYLOAD_SIZE = struct.calcsize(PACKET_FORMAT)
PACKET_SIZE = 4 + PAYLOAD_SIZE + 4


# ============================================================
# COMPASS SETTINGS
# ============================================================

# Calibration from your 1155-sample rotation test.

MAG_OFFSETS = [
    -12.817889505992401,
    21.952645425314238,
    -20.564162525577316,
]

MAG_SCALES = [
    1.0355003811390613,
    1.0328011295753232,
    0.938048732366578,
]

# Do not adjust this until we verify axis alignment.
HEADING_OFFSET = 0.0

# True = vector-based tilt compensation
# False = level-only compass
USE_TILT_COMPENSATION = True

# Physical orientation:
# +X = forward, along north arrow
# +Y = right
# +Z = upward
#
# These settings allow us to correct sensor-axis signs
# if the physical tests reveal a mismatch.

MAG_X_SIGN = 1
MAG_Y_SIGN = 1
MAG_Z_SIGN = 1

ACCEL_X_SIGN = 1
ACCEL_Y_SIGN = 1
ACCEL_Z_SIGN = 1

DIRECTIONS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

ARROWS = ["↑", "↗", "→", "↘", "↓", "↙", "←", "↖"]

console = Console()


# ============================================================
# VECTOR MATH
# ============================================================


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def magnitude(values):
    if values is None:
        return None

    return math.sqrt(dot(values, values))


def normalize(values):
    length = magnitude(values)

    if length is None or length < 1e-9:
        return None

    return [value / length for value in values]


def subtract(a, b):
    return [x - y for x, y in zip(a, b)]


def scale(values, factor):
    return [value * factor for value in values]


# ============================================================
# SENSOR CALCULATIONS
# ============================================================


def calibrate_magnetometer(mag):
    # if mag is None:
    #     return None

    # return [
    #     (mag[i] - MAG_OFFSETS[i]) * MAG_SCALES[i]
    #     for i in range(3)
    # ]
    # Already calibrated by sensor_transmitterV3.py
    return mag


def orientation(accel):
    if accel is None:
        return None, None

    ax, ay, az = accel

    pitch = math.degrees(math.atan2(-ax, math.hypot(ay, az)))

    roll = math.degrees(math.atan2(ay, az))

    return pitch, roll


def compass(mag, accel):
    corrected = calibrate_magnetometer(mag)

    if corrected is None:
        return None, "--", "·"

    magnetic = [
        corrected[0] * MAG_X_SIGN,
        corrected[1] * MAG_Y_SIGN,
        corrected[2] * MAG_Z_SIGN,
    ]

    mx, my, mz = magnetic

    if USE_TILT_COMPENSATION:
        if accel is None:
            return None, "--", "·"

        acceleration = [
            accel[0] * ACCEL_X_SIGN,
            accel[1] * ACCEL_Y_SIGN,
            accel[2] * ACCEL_Z_SIGN,
        ]

        # At rest, the accelerometer measures upward
        # specific force. Normalize to get the local
        # upward direction in the device frame.

        up = normalize(acceleration)

        if up is None:
            return None, "--", "·"

        # Remove the vertical magnetic component.

        magnetic_vertical = scale(up, dot(magnetic, up))

        magnetic_horizontal = subtract(magnetic, magnetic_vertical)

        # Project the device's forward (+X) axis
        # onto the horizontal plane.

        forward_axis = [1.0, 0.0, 0.0]

        forward_horizontal = subtract(forward_axis, scale(up, dot(forward_axis, up)))

        forward = normalize(forward_horizontal)

        if forward is None:
            return None, "--", "·"

        # Construct a horizontal right axis.
        # For +X forward, +Y right, +Z up:
        # right = up cross forward.

        right = normalize(cross(up, forward))

        if right is None:
            return None, "--", "·"

        north_forward = dot(magnetic_horizontal, forward)

        north_right = dot(magnetic_horizontal, right)

    else:
        north_forward = mx
        north_right = my

    if math.hypot(north_forward, north_right) < 0.01:
        return None, "--", "·"

    # The magnetic field points toward magnetic north.
    #
    # With +Y pointing right, a device facing east
    # sees magnetic north toward its left (-Y).
    # Therefore clockwise heading uses -north_right.

    heading = (
        math.degrees(math.atan2(north_right, north_forward)) + HEADING_OFFSET
    ) % 360

    index = int((heading + 22.5) // 45) % 8

    return heading, DIRECTIONS[index], ARROWS[index]


def number(value, digits=2, suffix=""):
    if value is None:
        return "--"

    return f"{value:.{digits}f}{suffix}"


def vector(values, unit):
    if values is None:
        return "--"

    return (
        "  ".join(f"{axis}: {value:+.2f}" for axis, value in zip("XYZ", values))
        + f" {unit}"
    )


# ============================================================
# BINARY PACKET DECODING
# ============================================================


def decode_packet(packet):
    payload = packet[4:-4]

    received_crc = struct.unpack("<I", packet[-4:])[0]

    calculated_crc = zlib.crc32(payload) & 0xFFFFFFFF

    if received_crc != calculated_crc:
        return None

    values = struct.unpack(PACKET_FORMAT, payload)

    return {
        "n": values[0],
        "lat": values[1] / 1e7,
        "lon": values[2] / 1e7,
        "spd": values[3] / 100,
        "a": [v / 100 for v in values[4:7]],
        "g": [v / 100 for v in values[7:10]],
        "m": [v / 10 for v in values[10:13]],
        "fix": bool(values[13]),
    }


def process_buffer(buffer, state):
    while True:
        index = buffer.find(SYNC)

        if index == -1:
            if len(buffer) > 3:
                del buffer[:-3]
            return

        if index > 0:
            del buffer[:index]

        if len(buffer) < PACKET_SIZE:
            return

        packet = bytes(buffer[:PACKET_SIZE])
        decoded = decode_packet(packet)

        if decoded is None:
            state["invalid"] += 1
            del buffer[0]
            continue

        sequence = decoded["n"]
        previous = state["last_sequence"]

        if previous is not None and sequence > previous + 1:
            state["missing"] += sequence - previous - 1

        if previous is None or sequence > previous:
            state["last_sequence"] = sequence

        old = state["packet"]

        if old and old["fix"] and not decoded["fix"]:
            state["gps_outages"] += 1

        state["packet"] = decoded
        state["last_received"] = time.monotonic()
        state["last_clock"] = datetime.now().strftime("%H:%M:%S")
        state["received"] += 1

        del buffer[:PACKET_SIZE]


# ============================================================
# COMPASS DISPLAY
# ============================================================


def render_compass(mag, accel):
    heading, direction, arrow = compass(mag, accel)

    heading_text = f"{heading:06.2f}°" if heading is not None else "--"

    mode = "Vector tilt compensation" if USE_TILT_COMPENSATION else "Level-only compass"

    table = Table.grid(expand=True)
    table.add_column(justify="center")

    table.add_row("[bold]N[/bold]")
    table.add_row(f"[bold bright_cyan]{arrow}[/bold bright_cyan]")
    table.add_row(f"[bold yellow]{heading_text}  " f"{direction}[/bold yellow]")
    table.add_row(f"[dim]{mode} | Magnetic north[/dim]")

    return Panel(
        table,
        title="Digital Compass",
        border_style="yellow",
    )


# ============================================================
# DASHBOARD
# ============================================================


def render(state):
    packet = state["packet"]

    age = (
        None
        if state["last_received"] is None
        else time.monotonic() - state["last_received"]
    )

    link_ok = age is not None and age < 2.0
    fix = packet["fix"] if packet else None

    summary = Table.grid(expand=True)
    summary.add_column(ratio=1)
    summary.add_column(ratio=1)
    summary.add_column(ratio=1)

    radio_status = (
        "[green]RECEIVING[/green]" if link_ok else "[red]NO RECENT DATA[/red]"
    )

    gps_status = (
        "[green]FIX[/green]"
        if fix
        else "[yellow]NO FIX[/yellow]" if packet else "[dim]WAITING[/dim]"
    )

    summary.add_row(
        f"Radio: {radio_status}",
        f"GPS: {gps_status}",
        f"Packet age: {number(age, 2, ' s')}",
    )

    gps = Table.grid(padding=(0, 2))
    gps.add_column(style="cyan", width=16)
    gps.add_column()

    gps.add_row(
        "Latitude",
        number(packet["lat"] if packet else None, 7),
    )
    gps.add_row(
        "Longitude",
        number(packet["lon"] if packet else None, 7),
    )
    gps.add_row(
        "Speed",
        number(packet["spd"] if packet else None, 2, " mph"),
    )

    if packet and not fix:
        gps.add_row(
            "Notice",
            "[yellow]No GPS fix; position may be stale[/yellow]",
        )

    accel = packet["a"] if packet else None
    gyro = packet["g"] if packet else None
    mag = packet["m"] if packet else None

    corrected_mag = calibrate_magnetometer(mag)
    pitch, roll = orientation(accel)

    sensors = Table.grid(padding=(0, 2))
    sensors.add_column(style="cyan", width=22)
    sensors.add_column()

    sensors.add_row(
        "Accelerometer",
        vector(accel, "m/s²"),
    )
    sensors.add_row(
        "Gyroscope",
        vector(gyro, "°/s"),
    )
    sensors.add_row(
        "Magnetometer (raw)",
        vector(mag, "µT"),
    )
    sensors.add_row(
        "Magnetometer (cal)",
        vector(corrected_mag, "µT"),
    )
    sensors.add_row(
        "Accel magnitude",
        number(magnitude(accel), 2, " m/s²"),
    )
    sensors.add_row(
        "Raw mag magnitude",
        number(magnitude(mag), 2, " µT"),
    )
    sensors.add_row(
        "Cal mag magnitude",
        number(magnitude(corrected_mag), 2, " µT"),
    )
    sensors.add_row(
        "Pitch (accel)",
        number(pitch, 2, "°"),
    )
    sensors.add_row(
        "Roll (accel)",
        number(roll, 2, "°"),
    )

    stats = Table.grid(padding=(0, 2))
    stats.add_column(style="cyan", width=18)
    stats.add_column()

    elapsed = time.monotonic() - state["start"]

    average_rate = state["received"] / elapsed if elapsed > 0 else 0

    total = state["received"] + state["missing"]

    success = 100 * state["received"] / total if total else 0

    stats.add_row("Valid packets", str(state["received"]))
    stats.add_row("Missing packets", str(state["missing"]))
    stats.add_row("CRC errors", str(state["invalid"]))
    stats.add_row(
        "Last sequence",
        str(state["last_sequence"]) if state["last_sequence"] is not None else "--",
    )
    stats.add_row("GPS outages", str(state["gps_outages"]))
    stats.add_row("Average rate", f"{average_rate:.2f} Hz")
    stats.add_row("Reception", f"{success:.2f}%")
    stats.add_row("Packet size", f"{PACKET_SIZE} bytes")
    stats.add_row(
        "Last reception",
        state["last_clock"] or "--",
    )

    return Group(
        Panel(
            summary,
            title="Surf Tracker | Binary Telemetry V6",
            border_style="blue",
        ),
        Panel(
            gps,
            title="GNSS",
            border_style="cyan",
        ),
        render_compass(mag, accel),
        Panel(
            sensors,
            title="IMU and Magnetometer",
            border_style="green",
        ),
        Panel(
            stats,
            title="Radio and GPS Statistics",
            border_style="magenta",
        ),
        Text(
            "Ctrl+C to stop",
            style="dim",
        ),
    )


# ============================================================
# MAIN
# ============================================================


def main():
    state = {
        "packet": None,
        "last_received": None,
        "last_clock": None,
        "last_sequence": None,
        "received": 0,
        "missing": 0,
        "invalid": 0,
        "gps_outages": 0,
        "start": time.monotonic(),
    }

    buffer = bytearray()

    print(f"Listening on {PORT} at {BAUD} baud...")
    print(f"Packet size: {PACKET_SIZE} bytes")

    try:
        with serial.Serial(PORT, BAUD, timeout=0.02) as radio:

            with Live(
                render(state),
                console=console,
                refresh_per_second=REFRESH_RATE,
                screen=True,
            ) as live:

                while True:
                    incoming = radio.read(min(radio.in_waiting or 1, 4096))

                    if incoming:
                        buffer.extend(incoming)
                        process_buffer(buffer, state)

                    live.update(render(state))
                    time.sleep(0.02)

    except KeyboardInterrupt:
        pass

    except serial.SerialException as exc:
        console.print(f"[red]Serial error:[/red] {exc}")

    finally:
        console.print(
            f"Valid: {state['received']} | "
            f"Missing: {state['missing']} | "
            f"CRC errors: {state['invalid']} | "
            f"GPS outages: {state['gps_outages']}"
        )


if __name__ == "__main__":
    main()
