"""Continuous ELRS range test using a GPS-calibrated starting position."""

from range_common import run_receiver, RADIO_PORT, RADIO_BAUD


def run(port=RADIO_PORT, baud=RADIO_BAUD, hz=10, seconds=0, note="", baseline_samples=100):
    """Runs a continuous range test using an averaged GPS starting position.

    Args:
        port: Serial port connected to the receiver. defined in telemetry_dashboard
        baud: Serial baud rate. defined in telemetry_dashboard
        hz: Requested telemetry frequency sent to the Pi over ELRS.
        seconds: Test duration in seconds, or zero to run until interrupted.
        note: Optional text included in each CSV row.
        baseline_samples: Number of valid GPS positions to average before moving.

    Returns:
        Path to the CSV results file.
    """
    return run_receiver(
        "continuous",
        port,
        baud,
        hz,
        seconds,
        note=note,
        baseline_samples=baseline_samples,
    )
