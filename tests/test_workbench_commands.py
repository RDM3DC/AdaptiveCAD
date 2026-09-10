"""Headless safety contracts for the form-to-command adapter."""

import copy
import math

import pytest

from adaptivecad.geom.tool_document import ToolDocument, ToolSession
from adaptivecad.gui.meshfree_workbench import PRESETS
from adaptivecad.gui.workbench_commands import (
    GROUPS,
    command_defaults,
    field_kind,
    field_text,
    parse_field,
    unique_name,
    validate_command,
)


def model():
    session = ToolSession()
    session.execute_many(
        [
            {"op": "line", "name": "profile", "start": [0, 0, 0], "end": [1, 0, 0]},
            {"op": "line", "name": "guide", "start": [0, 0, 0], "end": [0, 1, 1]},
        ]
    )
    return session.document


@pytest.mark.parametrize("label", [label for labels in GROUPS.values() for label in labels])
def test_every_ribbon_preset_roundtrips_and_validates_without_mutation(label):
    document = model()
    before = document.to_json()
    presets = copy.deepcopy(PRESETS)
    defaults = command_defaults(label, document, "profile")
    command = {"op": defaults["op"]}
    for key, value in defaults.items():
        if key != "op":
            kind = field_kind(key, value)
            command[key] = parse_field(kind, field_text(kind, value))
    candidate = validate_command(document, command)
    assert candidate is not document
    assert document.to_json() == before
    assert PRESETS == presets


@pytest.mark.parametrize(
    "kind,text",
    [
        ("number", "NaN"),
        ("number", "inf"),
        ("number", "1e999"),
        ("integer", "1.5"),
        ("integer", "1e3"),
        ("integer", "True"),
        ("vector", "1, 2"),
        ("vector", "1, 2, inf"),
        ("points", "[[0, true, 0]]"),
        ("points", '[["0", 1, 2]]'),
        ("points", "[]"),
        ("points", "[[0, 1]]"),
        ("points", "0,0,0\n" * 33),
        ("points", "[[0, NaN, 0]]"),
        ("unit", "feet"),
        ("number", "__import__('os').system('echo bad')"),
    ],
)
def test_bad_fields_are_rejected(kind, text):
    with pytest.raises((ValueError, TypeError)):
        parse_field(kind, text)


def test_ft_us_is_not_international_feet():
    assert parse_field("unit", "ft_us") != parse_field("unit", "ft")
    original = model()
    us = validate_command(original, {"op": "convert_units", "unit": "ft_us"})
    international = validate_command(original, {"op": "convert_units", "unit": "ft"})
    assert us.get("profile").points != international.get("profile").points


def test_unique_array_prefix_avoids_generated_collision():
    s = ToolSession()
    s.execute({"op": "line", "name": "array_1", "start": [0, 0, 0], "end": [1, 0, 0]})
    name = unique_name(s.document, "array")
    assert name != "array" and name != "array_1"


def test_source_is_selected_explicitly_and_missing_source_is_not_invented():
    assert command_defaults("Copy", model(), "guide")["source"] == "guide"
    assert command_defaults("Copy", ToolDocument())["source"] == ""
    with pytest.raises(ValueError):
        validate_command(ToolDocument(), command_defaults("Copy", ToolDocument()))


def test_validation_cannot_overwrite_or_append_to_original_history():
    s = ToolSession(model())
    before = (s.document, list(s._undo), list(s._redo))
    command = {"op": "line", "name": "profile", "start": [0, 0, 0], "end": [2, 0, 0]}
    with pytest.raises(ValueError):
        validate_command(s.document, command)
    assert (s.document, s._undo, s._redo) == before


def test_native_angle_and_point_values_are_not_rounded():
    assert parse_field("number", repr(math.pi)) == math.pi
    assert parse_field("points", "1e-14, 2.123456789012345, -3e14") == [
        [1e-14, 2.123456789012345, -3e14]
    ]
