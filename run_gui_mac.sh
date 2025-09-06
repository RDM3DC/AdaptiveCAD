#!/usr/bin/env bash
# AdaptiveCAD macOS GUI launcher
# Usage:
#   1. Make sure conda (or mamba) is installed and environment created:
#        conda env create -f environment.yml   # (first time only)
#   2. Activate environment BEFORE running this script:
#        conda activate adaptivecad
#   3. Run:
#        ./run_gui_mac.sh
#
# This script will:
#   - Verify the active Python is from the 'adaptivecad' env
#   - Optionally set Qt plugin paths if Cocoa plugin not found
#   - Launch the AdaptiveCAD playground GUI
#
# Troubleshooting:
#   If you see: "Could not load the Qt platform plugin 'cocoa'" then re-run with:
#        QT_DEBUG_PLUGINS=1 ./run_gui_mac.sh
#   and inspect the printed plugin search paths.
#
set -euo pipefail

# Ensure we're in repository root (script's directory)
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Check conda env (best effort)
if command -v conda >/dev/null 2>&1; then
  ACTIVE_ENV="${CONDA_DEFAULT_ENV:-}" || true
  if [[ "$ACTIVE_ENV" != "adaptivecad" ]]; then
    echo "[WARN] Conda environment 'adaptivecad' not active (current: '${ACTIVE_ENV:-none}')." >&2
    echo "       Activate it first:  conda activate adaptivecad" >&2
  fi
else
  echo "[WARN] 'conda' command not found. Assuming correct Python already active." >&2
fi

PY_BIN="$(command -v python || true)"
if [[ -z "$PY_BIN" ]]; then
  echo "[ERROR] Python not found in PATH." >&2
  exit 1
fi

echo "Using Python: $PY_BIN"
python - <<'PYCHK' || {
print("[ERROR] Basic Python check failed.")
raise SystemExit(1)
PYCHK

echo "Checking GUI dependencies (PySide6, pythonocc-core)..."
python - <<'PYDEPS' || {
print("[ERROR] Missing required GUI dependencies. Install via: conda install -c conda-forge pyside6 pythonocc-core")
raise SystemExit(1)
}
try:
    import PySide6, OCC.Core  # noqa: F401
    from PySide6 import QtCore
    print("PySide6 version:", PySide6.__version__)
    import os
    plugin_dir = os.path.join(PySide6.__path__[0], 'plugins', 'platforms')
    print("Expected platform plugins directory:", plugin_dir)
except Exception as e:
    print("Dependency import error:", e)
    raise
PYDEPS

# Attempt to set QT_QPA_PLATFORM_PLUGIN_PATH only if cocoa plugin not on default path.
if [[ -z "${QT_QPA_PLATFORM_PLUGIN_PATH:-}" ]]; then
  COCOA_PATH=$(python - <<'PYF'
import os, PySide6, json
p = os.path.join(PySide6.__path__[0], 'plugins', 'platforms')
print(p)
PYF
  )
  if [[ -f "$COCOA_PATH/libqcocoa.dylib" || -f "$COCOA_PATH/libqcocoa.dylib" || -f "$COCOA_PATH/libqcocoa_debug.dylib" ]]; then
    export QT_QPA_PLATFORM_PLUGIN_PATH="$COCOA_PATH"
  fi
fi

# Encourage high-DPI scaling (optional)
export QT_ENABLE_HIGHDPI_SCALING=1
export QT_AUTO_SCREEN_SCALE_FACTOR=1

# Launch
echo "Launching AdaptiveCAD Playground GUI..."
exec python -m adaptivecad.gui.playground "$@"
