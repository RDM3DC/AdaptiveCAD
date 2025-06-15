import adsk.core, adsk.fusion, traceback
from typing import Dict, Any


def build_sliders(cmd_inputs: adsk.core.CommandInputs, spec: Dict[str, Any]):
    """Walk spec["parameters"] and create FloatSliderCommandInput objects."""
    map_id = {}
    for key, val in spec.get("parameters", {}).items():
        if isinstance(val, (int, float)):
            cfg = {"value": float(val)}
        elif isinstance(val, dict) and "value" in val:
            cfg = val
        else:
            continue

        id_ = f"slider_{key}"
        slider = cmd_inputs.addFloatSliderCommandInput(
            id_, f"{key.capitalize()}",
            "mm",
            adsk.core.ValueInput.createByReal(cfg.get("min", cfg["value"] * 0.1)),
            adsk.core.ValueInput.createByReal(cfg.get("max", cfg["value"] * 10)),
        )
        slider.valueOne = cfg["value"]
        if "step" in cfg:
            slider.setSliderDelta(cfg["step"])
        map_id[id_] = (["parameters", key], cfg["value"])
    return map_id
