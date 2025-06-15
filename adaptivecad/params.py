import math
import numpy as np

class ParamEnv:
    """Registry for named parameters and math constants."""

    def __init__(self):
        self.vars = {}
        self.constants = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
        # Common math shorthands
        self.constants.update({
            'pi': math.pi,
            'e': math.e,
            'sin': math.sin,
            'cos': math.cos,
            'tan': math.tan,
            'sqrt': math.sqrt,
        })
        self.constants.update({'np': np})

    def set(self, name, value):
        self.vars[name] = value

    def get(self, name):
        return self.vars.get(name, self.constants.get(name))

    def eval(self, expr):
        env = {**self.constants, **self.vars}
        return eval(expr, {"__builtins__": {}}, env)
