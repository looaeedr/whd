"""#2517: EndCap operator legacy summary and baseline Fold default ownership."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import (
    ae, manufacturing_api, project_operator_endcap_blank_dimensions,
    read_operator_baseline_fold_defaults,
)
from gui_modules.application.calculation_controller import update_calculations
from gui_modules.application import cabinet_controller

ROOT = Path(__file__).resolve().parents[1]


def _values():
    return dict(w=800.0, h=1600.0, d=500.0, t=2.0, fw=25.0,
                yl1=15.0, yr1=15.0, ytop1=40.0, ybottom1=15.0)


def test_formula_fallback_uses_existing_ae_owner_without_mutating_input():
    values = _values()
    before = deepcopy(values)
    assert manufacturing_api.project_operator_endcap_blank_dimensions is project_operator_endcap_blank_dimensions
    assert project_operator_endcap_blank_dimensions(values) == pytest.approx((
        ae.calculate_y_width(15, 15, 800, 2),
        ae.calculate_y_depth(40, 15, 500, 2, 25),
    ))
    assert values == before


def test_baseline_summary_precedence_and_fail_closed(monkeypatch):
    calls = []
    def baseline(model, *args, **kwargs):
        calls.append((model, args, kwargs))
        return SimpleNamespace(params={"total_width": 701.0, "total_depth": 503.0})
    monkeypatch.setattr(ae, "get_stretched_end_cap_data", baseline)
    assert project_operator_endcap_blank_dimensions(
        _values(), baseline_model="金庫型"
    ) == (701.0, 503.0)
    assert calls == [("金庫型", (800.0, 1600.0, 500.0, 2.0),
                      {"FW_val": 25.0, "is_tail": False})]
    def broken(*args, **kwargs):
        raise FileNotFoundError("source missing")
    monkeypatch.setattr(ae, "get_stretched_end_cap_data", broken)
    with pytest.raises(FileNotFoundError):
        project_operator_endcap_blank_dimensions(_values(), baseline_model="金庫型")


@pytest.mark.parametrize("source_present", [True, False])
def test_known_baseline_fold_defaults_and_absent_door(monkeypatch, source_present):
    def endcap(*args, **kwargs):
        return SimpleNamespace(params={
            "yl1": 17, "yr1": 19, "ytop1": 40,
            "ybottom1": 15, "fw": 25,
        })
    monkeypatch.setattr(ae, "get_stretched_end_cap_data", endcap)
    monkeypatch.setattr(ae, "has_baseline_part",
                        lambda model, filename: source_present)
    if source_present:
        monkeypatch.setattr(ae, "get_stretched_door_data", lambda *a, **k:
            SimpleNamespace(params={
                "door_fold_l": 21, "door_fold_r": 16,
                "door_fold_t": 14, "door_fold_b": 13,
            }))
    output = read_operator_baseline_fold_defaults("金庫型", thickness=2)
    assert manufacturing_api.read_operator_baseline_fold_defaults is read_operator_baseline_fold_defaults
    assert output["endcap"] == {
        "yl1": 17.0, "yr1": 19.0, "ytop1": 40.0,
        "ybottom1": 15.0, "fw": 25.0,
    }
    assert output["door"] == ({
        "door_fold_l": 21.0, "door_fold_r": 16.0,
        "door_fold_t": 14.0, "door_fold_b": 13.0,
    } if source_present else None)


def test_door_load_failure_uses_legacy_operator_fallback(monkeypatch):
    monkeypatch.setattr(ae, "get_stretched_end_cap_data", lambda *a, **k:
        SimpleNamespace(params={
            "yl1": 10, "yr1": 11, "ytop1": 12, "ybottom1": 13, "fw": 25,
        }))
    monkeypatch.setattr(ae, "has_baseline_part", lambda *a: True)
    def failed(*args, **kwargs):
        raise ValueError("invalid baseline")
    monkeypatch.setattr(ae, "get_stretched_door_data", failed)
    data = read_operator_baseline_fold_defaults("金庫型", thickness=2)
    assert data["door"] == {
        "door_fold_l": 19.0, "door_fold_r": 15.0,
        "door_fold_t": 15.0, "door_fold_b": 15.0,
    }


def test_gui_delegates_both_operator_decisions_to_public_api():
    summary = (ROOT / "gui_modules/application/calculation_controller.py").read_text(encoding="utf-8")
    baseline = (ROOT / "gui_modules/application/cabinet_controller.py").read_text(encoding="utf-8")
    assert "manufacturing_api.project_operator_endcap_blank_dimensions(" in summary
    assert "ae.get_stretched_end_cap_data(" not in summary
    assert "ae.calculate_y_width(" not in summary
    assert "ae.calculate_y_depth(" not in summary
    assert "manufacturing_api.read_operator_baseline_fold_defaults(" in baseline
    assert "ae.get_stretched_end_cap_data(" not in baseline
    assert "ae.get_stretched_door_data(" not in baseline
    assert "ae.has_baseline_part(" not in baseline
