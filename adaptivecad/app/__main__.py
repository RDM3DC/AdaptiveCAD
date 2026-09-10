"""Run the existing SDF application with the metric workbench installed."""
from adaptivecad.gui.metric_launch import main

if __name__ == "__main__":
    raise SystemExit(main(["--ui", "sdf"]))
