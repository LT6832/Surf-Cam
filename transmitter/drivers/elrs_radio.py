"""Bidirectional ELRS AirPort serial transport and command handling."""

import serial

from drivers.rate_controller import RateController

DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUD = 460800
MAX_COMMAND_BYTES = 64
MAX_PENDING_BYTES = 256


class ElrsRadio:
    """Wrap the ELRS serial port and parse ASCII control commands."""

    def __init__(
        self,
        port: str = DEFAULT_PORT,
        baud_rate: int = DEFAULT_BAUD,
    ) -> None:
        self._port = serial.Serial(
            port, baud_rate, timeout=0, write_timeout=1
        )
        self._pending = bytearray()

    def __enter__(self) -> "ElrsRadio":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._port.close()

    def send_packet(self, packet: bytes) -> None:
        """Write an encoded binary telemetry packet."""
        self._port.write(packet)

    def _process_command(
        self, command: bytes, controller: RateController
    ) -> None:
        """Handle one complete ASCII command."""
        try:
            message = command.decode("ascii").strip()
        except UnicodeDecodeError:
            return

        if message == "SC_KEEPALIVE":
            controller.keepalive()
            return

        if not message.startswith("SC_RATE "):
            return

        rate_text = message.removeprefix("SC_RATE ")
        if not rate_text.isdecimal():
            return

        requested_rate = int(rate_text)
        if controller.set_rate(requested_rate):
            self._port.write(
                f"SC_ACK {controller.hz}\n".encode("ascii")
            )
            print(f"Telemetry rate: {controller.hz} Hz", flush=True)

    def poll_commands(self, controller: RateController) -> None:
        """Read pending commands without blocking the sensor loop."""
        available = self._port.in_waiting
        if available:
            self._pending.extend(
                self._port.read(min(available, MAX_PENDING_BYTES))
            )

        while b"\n" in self._pending:
            command, _, remainder = self._pending.partition(b"\n")
            self._pending = bytearray(remainder)
            if len(command) <= MAX_COMMAND_BYTES:
                self._process_command(bytes(command), controller)

        if len(self._pending) > MAX_COMMAND_BYTES:
            self._pending.clear()

        if controller.check_timeout():
            print("Rate timeout: restored 10 Hz", flush=True)
