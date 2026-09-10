#!/usr/bin/env python
"""Launch the existing triangle-free SDF application with metric tools."""
import sys

from adaptivecad.gui.metric_launch import main

if __name__ == "__main__":
    raise SystemExit(main(["--ui", "sdf", *sys.argv[1:]]))
