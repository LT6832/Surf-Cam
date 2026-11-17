"""Stationary ELRS range test at a manually measured distance."""

from range_common import run_receiver, RADIO_PORT, RADIO_BAUD


def run(port=RADIO_PORT, baud=RADIO_BAUD, hz=10, seconds=60, distance= 0.0, note=""):
    """Runs a stationary range test at a manually measured distance.

    Args:
        port: Serial port connected to the receiver.
        baud: Serial baud rate.
        hz: Requested telemetry frequency sent to the Pi over ELRS.
        seconds: Test duration in seconds, or zero to run until interrupted.
        distance: Measured distance from the receiver in feet.
        note: Optional text included in each CSV row.

    Returns:
        Path to the CSV results file.
    """
    return run_receiver(
        "stationary", port, baud, hz, seconds, note=note, distance=distance
    )
