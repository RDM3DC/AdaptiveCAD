"""Top-level helpers for AdaptiveCAD."""

__all__ = [
    "generate_gcode_from_shape",
    "generate_gcode_from_ama_file",
    "generate_gcode_from_ama_data",
    "ParamEnv",
]

from .params import ParamEnv


def generate_gcode_from_shape(*args, **kwargs):
    from .gcode_generator import generate_gcode_from_shape
    return generate_gcode_from_shape(*args, **kwargs)


def generate_gcode_from_ama_file(*args, **kwargs):
    from .gcode_generator import generate_gcode_from_ama_file
    return generate_gcode_from_ama_file(*args, **kwargs)


def generate_gcode_from_ama_data(*args, **kwargs):
    from .gcode_generator import generate_gcode_from_ama_data
    return generate_gcode_from_ama_data(*args, **kwargs)
