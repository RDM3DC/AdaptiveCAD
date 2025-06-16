"""I/O helpers with optional heavy dependencies."""

__all__ = [
    "write_ama",
    "read_ama",
    "AMAFile",
    "AMAPart",
    "ama_to_gcode",
    "GCodeGenerator",
    "SimpleMilling",
    "WaterlineMilling",
]


def write_ama(*args, **kwargs):
    from .ama_writer import write_ama
    return write_ama(*args, **kwargs)


def read_ama(*args, **kwargs):
    from .ama_reader import read_ama
    return read_ama(*args, **kwargs)


def AMAFile(*args, **kwargs):  # type: ignore
    from .ama_reader import AMAFile
    return AMAFile(*args, **kwargs)


def AMAPart(*args, **kwargs):  # type: ignore
    from .ama_reader import AMAPart
    return AMAPart(*args, **kwargs)


def ama_to_gcode(*args, **kwargs):
    from .gcode_generator import ama_to_gcode
    return ama_to_gcode(*args, **kwargs)


def GCodeGenerator(*args, **kwargs):  # type: ignore
    from .gcode_generator import GCodeGenerator
    return GCodeGenerator(*args, **kwargs)


def SimpleMilling(*args, **kwargs):  # type: ignore
    from .gcode_generator import SimpleMilling
    return SimpleMilling(*args, **kwargs)


def WaterlineMilling(*args, **kwargs):  # type: ignore
    from .gcode_generator import WaterlineMilling
    return WaterlineMilling(*args, **kwargs)
