"""Control temporary telemetry transmission rates."""

import time

DEFAULT_HZ = 10
ALLOWED_RATES_HZ = frozenset({1, 5, 10, 20, 50})
RATE_TIMEOUT_SECONDS = 30.0


class RateController:
    """Track a requested transmission rate and its expiration."""

    def __init__(self) -> None:
        self.hz = DEFAULT_HZ
        self._deadline: float | None = None

    @property
    def interval_seconds(self) -> float:
        """Return the time between telemetry packets."""
        return 1.0 / self.hz

    def set_rate(self, hz: int) -> bool:
        """Apply a supported rate and return whether it was accepted."""
        if hz not in ALLOWED_RATES_HZ:
            return False
        self.hz = hz
        self._deadline = (
            time.monotonic() + RATE_TIMEOUT_SECONDS
            if hz != DEFAULT_HZ else None
        )
        return True

    def keepalive(self) -> None:
        """Extend a temporary rate's expiration."""
        if self._deadline is not None:
            self._deadline = time.monotonic() + RATE_TIMEOUT_SECONDS

    def check_timeout(self) -> bool:
        """Restore the default rate if expired; return whether it changed."""
        if self._deadline is None or time.monotonic() < self._deadline:
            return False
        self.hz = DEFAULT_HZ
        self._deadline = None
        return True
