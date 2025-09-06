# AdaptiveCAD GUI Quick Start

This repository also contains the AdaptiveCAD experimental GUI environment alongside the compression suite.

## Install (Editable Dev Mode)
```bash
conda env create -f environment.yml   # first time
conda activate adaptivecad
pip install -e .[gui]
```
(If extras fail due to resolver conflicts, fall back to conda installing `pyside6 pythonocc-core`.)

## Launch
Using the new console script after install:
```bash
adaptivecad-gui
```
Or direct:
```bash
python -m adaptivecad.gui.playground
```
Or macOS helper script:
```bash
./run_gui_mac.sh
```

## Headless / CI Import Test
To validate import without real display:
```bash
QT_QPA_PLATFORM=offscreen python -c "from adaptivecad.gui import playground; print(playground.HAS_GUI)"
```

## Troubleshooting Summary
| Symptom | Fix |
|---------|-----|
| `Could not load the Qt platform plugin "cocoa"` | Ensure `QT_QPA_PLATFORM_PLUGIN_PATH` points to `PySide6/plugins/platforms`; reinstall `pyside6`. |
| Segfault on import of OCC | Match architecture (arm64 vs x86_64) for pythonocc-core & Python. |
| Black window | Try `QT_OPENGL=software` or update GPU drivers (Linux); on macOS use software fallback. |
| High-DPI scaling weird | `QT_AUTO_SCREEN_SCALE_FACTOR=1` or set explicit `QT_SCALE_FACTOR=1.0`. |

## Intended Scope
The GUI is experimental: modeling primitives, parametric Pi geometry shapes, simple operations (boolean ops, fillets, patterns), and G-code export. Expect rapid iteration.

## Contributing
1. Branch: `git checkout -b feature/short-description`
2. Make changes + add tests (`tests/test_playground*.py`)
3. Run `pytest -k playground` before PR.

---
_Last updated: macOS integration pass._
