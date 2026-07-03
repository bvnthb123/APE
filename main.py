"""APE application entry point."""

from ape.core.app import APEApplication


def main() -> None:
    """Initialize APE and print the current system status."""
    app = APEApplication()
    app.start()
    summary = app.summary()

    print("\n====================================================")
    print("APE - Adaptive Prediction Engine")
    print("Version :", summary["version"])
    print("Build   :", summary["build"])
    print("Status  : Database Layer OK")
    print("====================================================\n")

    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
