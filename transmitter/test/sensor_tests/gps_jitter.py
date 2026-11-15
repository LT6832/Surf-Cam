
import serial
import time
import math
import statistics

PORT = "/dev/serial0"
BAUD = 460800
DURATION = 30

positions = []


def nmea_to_decimal(value, direction):
    if not value:
        return None

    degrees = int(float(value) / 100)
    minutes = float(value) - degrees * 100
    decimal = degrees + minutes / 60

    if direction in ("S", "W"):
        decimal = -decimal

    return decimal


def distance_meters(lat1, lon1, lat2, lon2):
    radius = 6371000

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)
    dlat = lat2 - lat1
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    return 2 * radius * math.asin(math.sqrt(a))


print(f"Collecting GPS positions for {DURATION} seconds...")

with serial.Serial(PORT, BAUD, timeout=1) as gps:
    start = time.monotonic()

    while time.monotonic() - start < DURATION:
        line = gps.readline().decode("ascii", errors="ignore")

        if not line.startswith(("$GNRMC", "$GPRMC")):
            continue

        fields = line.strip().split(",")

        if len(fields) < 7 or fields[2] != "A":
            continue

        try:
            lat = nmea_to_decimal(fields[3], fields[4])
            lon = nmea_to_decimal(fields[5], fields[6])

            if lat is not None and lon is not None:
                positions.append((lat, lon))
        except (ValueError, IndexError):
            continue

if len(positions) < 2:
    print("Not enough valid GPS positions collected.")
    raise SystemExit

avg_lat = statistics.mean(p[0] for p in positions)
avg_lon = statistics.mean(p[1] for p in positions)

distances = [
    distance_meters(lat, lon, avg_lat, avg_lon)
    for lat, lon in positions
]

print("\nGPS JITTER RESULTS")
print("------------------")
print(f"Samples collected: {len(positions)}")
print(f"Average position: {avg_lat:.8f}, {avg_lon:.8f}")
print(f"Mean deviation: {statistics.mean(distances):.3f} m")
print(f"Standard deviation: {statistics.stdev(distances):.3f} m")
print(f"Maximum deviation: {max(distances):.3f} m")
print(f"Peak-to-peak spread: {max(distance_meters(a[0], a[1], b[0], b[1]) for a in positions for b in positions):.3f} m")
