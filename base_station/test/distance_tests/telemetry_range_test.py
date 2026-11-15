"""Interactive launcher for Surf-Cam ELRS range tests."""

import argparse
import continuous_test
import stationary_test


def choose(message, choices):
    """Prompts for a choice using a menu or a numbered text fallback.

    Args:
        message: Prompt displayed above the choices.
        choices: Nonempty sequence of selectable strings.

    Returns:
        The selected choice string.

    Raises:
        KeyboardInterrupt: If the user cancels the menu or interrupts input.
    """
    try:
        import questionary

        result = questionary.select(message, choices=choices).ask()
        if result is None:
            raise KeyboardInterrupt
        return result
    except ImportError:
        print("\n" + message)
        for i, item in enumerate(choices, 1):
            print(f" {i}. {item}")
        while True:
            answer = input("Select number: ").strip()
            if answer.isdigit() and 1 <= int(answer) <= len(choices):
                return choices[int(answer) - 1]


def main():
    """Parses serial options and prompts the user to configure and run a test."""
    parser = argparse.ArgumentParser(description="Surf-Cam range testing menu")
    parser.add_argument("--port", default="COM5")
    parser.add_argument("--baud", type=int, default=460800)
    args = parser.parse_args()
    print("\n=== SURF-CAM RANGE TESTER ===")
    mode = choose("Test mode", ["Stationary", "Continuous"])
    hz = int(choose("Requested frequency (Pi currently fixed at 10 Hz)", ["10 Hz"]))
    duration = choose(
        "Duration",
        ["30 seconds", "60 seconds", "120 seconds", "300 seconds", "Until stopped"],
    )
    seconds = {
        "30 seconds": 30,
        "60 seconds": 60,
        "120 seconds": 120,
        "300 seconds": 300,
        "Until stopped": 0,
    }[duration]
    note = input("Test note (optional): ").strip()
    if mode == "Stationary":
        while True:
            try:
                distance = float(input("Measured distance from receiver (feet): "))
                if distance < 0:
                    raise ValueError
                break
            except ValueError:
                print("Enter a nonnegative number.")
        print(f"\nStarting {mode} at {distance} m, {hz} Hz, {duration}.")
        if input("Continue? [Y/n]: ").strip().lower() not in ("", "y", "yes"):
            return
        stationary_test.run(
            port=args.port,
            baud=args.baud,
            hz=hz,
            seconds=seconds,
            distance=distance,
            note=note,
        )
    else:
        print(
            f"\nStarting {mode} at {hz} Hz, {duration}. Keep Pi stationary until GPS baseline locks."
        )
        if input("Continue? [Y/n]: ").strip().lower() not in ("", "y", "yes"):
            return
        continuous_test.run(
            port=args.port, baud=args.baud, hz=hz, seconds=seconds, note=note
        )


if __name__ == "__main__":
    main()
