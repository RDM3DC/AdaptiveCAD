from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

# --------- Macro schema ---------


@dataclass
class MacroParam:
    name: str
    type: str = "number"  # "number" | "int" | "string" | "bool"
    default: Any = None
    label: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None


@dataclass
class MacroStep:
    call: str
    args: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MacroDef:
    id: str
    name: str
    version: str = "1.0"
    author: str = "user"
    description: str = ""
    params: List[MacroParam] = field(default_factory=list)
    steps: List[MacroStep] = field(default_factory=list)
    ui: Dict[str, Any] = field(default_factory=dict)  # e.g. {"icon_text":"CH", "pinned": True}


# --------- Param substitution ---------

_VAR = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def _substitute(obj: Any, values: Dict[str, Any]) -> Any:
    """Recursively substitute ${param} in strings using provided values."""
    if isinstance(obj, str):

        def repl(m):
            key = m.group(1)
            return str(values.get(key, m.group(0)))

        return _VAR.sub(repl, obj)
    if isinstance(obj, list):
        return [_substitute(x, values) for x in obj]
    if isinstance(obj, dict):
        return {k: _substitute(v, values) for k, v in obj.items()}
    return obj


# --------- Simple parameter dialog ---------


class ParamDialog(QDialog):
    def __init__(self, params: List[MacroParam], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Tool Parameters")
        self._params = params
        self._widgets: Dict[str, QWidget] = {}

        form = QFormLayout()
        for p in params:
            label = p.label or p.name
            if p.type == "int":
                w = QSpinBox(self)
                w.setRange(-1_000_000, 1_000_000)
                if isinstance(p.default, int):
                    w.setValue(p.default)
            elif p.type == "bool":
                w = QCheckBox(self)
                w.setChecked(bool(p.default))
            elif p.type == "string":
                w = QLineEdit(self)
                if p.default is not None:
                    w.setText(str(p.default))
            else:  # number
                w = QDoubleSpinBox(self)
                w.setDecimals(6)
                w.setRange(-1e9, 1e9)
                if p.min is not None:
                    w.setMinimum(p.min)
                if p.max is not None:
                    w.setMaximum(p.max)
                if isinstance(p.default, (int, float)):
                    w.setValue(float(p.default))
            self._widgets[p.name] = w
            form.addRow(label + ":", w)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(btns)

    def values(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for p in self._params:
            w = self._widgets[p.name]
            if p.type == "int":
                out[p.name] = int(w.value())  # type: ignore
            elif p.type == "bool":
                out[p.name] = bool(w.isChecked())  # type: ignore
            elif p.type == "string":
                out[p.name] = str(w.text())  # type: ignore
            else:
                out[p.name] = float(w.value())  # type: ignore
        return out


# --------- Engine ---------


class MacroEngine:
    """
    Executes a MacroDef against a 'bus' (a CADActionBus-like object with .call(name, **kwargs)).
    """

    def __init__(self, bus):
        self.bus = bus

    def run(self, macro: MacroDef, *, parent_widget: Optional[QWidget] = None, params_values: Optional[Dict[str, Any]] = None) -> List[Any]:
        values: Dict[str, Any] = dict(params_values or {})
        missing = [p for p in macro.params if p.name not in values]
        if missing:
            dlg = ParamDialog(missing, parent=parent_widget)
            if dlg.exec() != QDialog.Accepted:
                return [{"ok": False, "error": "cancelled"}]
            values.update(dlg.values())

        results: List[Any] = []
        for step in macro.steps:
            args = _substitute(step.args, values)
            res = self.bus.call(step.call, **args)
            results.append(res)
        return results


