"""
APE entry point.
"""
from ape.core.app import APEApplication

def main() -> None:
    app = APEApplication()
    app.start()

    print("\n==============================================")
    print("APE - Adaptive Prediction Engine")
    print("Version:", app.summary()["version"])
    print("Build  :", app.summary()["build"])
    print("Status : Core Foundation OK")
    print("==============================================\n")

    for key, value in app.summary().items():
        print(f"{key}: {value}")

if __name__ == "__main__":
    main()
