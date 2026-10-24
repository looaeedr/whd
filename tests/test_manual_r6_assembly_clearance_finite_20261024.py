"""R6 physical collision evidence: assembly clearance never accepts infinity."""
from types import SimpleNamespace

import pytest

from phase6_manufacturing_geometry import (
    _phase6_assembly_relief_clearance,
    _phase6_signature_canonical_value,
)


def _clearance(text):
    owner = SimpleNamespace(
        assembly_relief_clearance_var=SimpleNamespace(get=lambda: text),
    )
    return _phase6_assembly_relief_clearance(owner)


@pytest.mark.parametrize("text", [
    "inf", "+inf", "-inf", "Infinity", "nan", "NaN", "1e999",
    "invalid", "", "   ", None, True,
])
def test_r6_invalid_ui_clearance_never_becomes_unlimited_physical_tolerance(text):
    number = _clearance(text)
    assert number == 0.
    assert _phase6_signature_canonical_value(number) == 0.


@pytest.mark.parametrize("text, expected", [
    ("0", 0.), ("2.5", 2.5), ("0.01", 0.01), ("-0.01", 0.),
    ("-50", 0.), (15.0, 15.0),
])
def test_r6_valid_clearance_preserves_positive_and_negative_clamp(text, expected):
    assert _clearance(text) == pytest.approx(expected)


def test_r6_missing_clearance_variable_keeps_prior_zero_default():
    assert _phase6_assembly_relief_clearance(SimpleNamespace()) == 0.
