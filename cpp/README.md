# AdaptiveCAD C++ Implementation

This directory contains an experimental C++ port of the core `linalg` module
from the Python version of AdaptiveCAD. The goal is to gradually refactor the
project into C++ while preserving the existing Python API.

The layout follows a typical `src`/`include` structure and uses CMake to produce
a static library called `adaptivecad_cpp`.

## Build Instructions

```bash
mkdir build
cd build
cmake ..
make
```

This will build the library which can then be linked against other C++ code or
wrapped for Python bindings.
