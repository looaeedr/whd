# -*- coding: utf-8 -*-
import math
import pytest

from ae_engine.certified_relief_registry import (
    CertifiedReliefRegistryError,
    evaluate_relief_formula_expression,
    evaluate_relief_formula_record,
)


def test_safe_formula_evaluator_accepts_whitelisted_dimensions():
    variables = {"T": 2.0, "FW": 25.0, "side_fold": 15.0, "ytop1": 16.0, "mating_width": 50.0}
    assert evaluate_relief_formula_expression("side_fold + FW", variables) == pytest.approx(40.0)
    assert evaluate_relief_formula_expression("ytop1 + FW - T", variables) == pytest.approx(39.0)


def test_safe_formula_evaluator_rejects_python_execution_and_unknown_names():
    with pytest.raises(CertifiedReliefRegistryError):
        evaluate_relief_formula_expression("__import__('os').system('echo bad')", {"T": 2.0})
    with pytest.raises(CertifiedReliefRegistryError):
        evaluate_relief_formula_expression("secret + T", {"T": 2.0})


def test_formula_record_rejects_negative_nan_and_topology_mismatch():
    with pytest.raises(CertifiedReliefRegistryError, match="negative"):
        evaluate_relief_formula_record(
            {"topology_levels": 1, "formula": {"primary_u": "-T", "primary_v": "FW"}},
            {"T": 2.0, "FW": 25.0},
        )
    with pytest.raises(CertifiedReliefRegistryError, match="secondary"):
        evaluate_relief_formula_record(
            {"topology_levels": 1, "formula": {"primary_u": "FW", "primary_v": "FW", "secondary_u": "T", "secondary_depth": "T"}},
            {"T": 2.0, "FW": 25.0},
        )
