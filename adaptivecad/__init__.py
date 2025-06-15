try:
    from .gcode_generator import (
        generate_gcode_from_shape,
        generate_gcode_from_ama_file,
        generate_gcode_from_ama_data,
    )
except ModuleNotFoundError:
    # Optional dependencies like pythonocc-core may be missing in some
    # environments. Allow importing submodules that don't require OCC.
    pass
