"""#2517 Vault baseline thickness input must be validated by the public Engine."""
from __future__ import annotations

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import operator_endcap_blank_projection as owner
from gui_modules.application import cabinet_controller as gui


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


@pytest.mark.parametrize("bad", [
    True, False, None, "", "nan", "inf", float("nan"),
    0, "0", -1.0, "-2.5", "wrong", object(),
])
def test_baseline_engine_refuses_invalid_raw_thickness_before_geometry(monkeypatch, bad):
    entered = []
    monkeypatch.setattr(owner.ae, "get_stretched_end_cap_data",
                        lambda *args, **kw: entered.append((args, kw)))
    with pytest.raises(ValueError, match="包外尺寸"):
        api.read_operator_baseline_fold_defaults("金庫型", thickness=bad)
    assert entered == []
    assert api.read_operator_baseline_fold_defaults is owner.read_operator_baseline_fold_defaults


@pytest.mark.parametrize("raw", ["2.125", 2.125, "1", 1.0])
def test_baseline_public_engine_preserves_fractional_t_and_json_roundtrip(monkeypatch, raw):
    calls = []
    def read_part(model, *args, **kwargs):
        calls.append((model, args, kwargs))
        return SimpleNamespace(params={
            "yl1": 15, "yr1": 15, "ytop1": 16,
            "ybottom1": 15, "fw": 25,
        })
    monkeypatch.setattr(owner.ae, "get_stretched_end_cap_data", read_part)
    monkeypatch.setattr(owner.ae, "has_baseline_part", lambda *_: False)
    before = deepcopy(raw)
    value = api.read_operator_baseline_fold_defaults("金庫型", thickness=raw)
    assert value["endcap"]["fw"] == 25
    assert value["door"] is None
    assert calls[0][0] == "金庫型"
    assert calls[0][1][3] == api.normalize_operator_source_dimension(raw, field="t")
    assert json.loads(json.dumps({"thickness": raw}))["thickness"] == raw
    assert raw == before


@pytest.mark.parametrize("bad", [True, "nan", "", "0", "inf"])
def test_gui_vault_baseline_invalid_t_fails_before_any_corner_or_family_change(
    monkeypatch, bad,
):
    calls = []
    host = SimpleNamespace(
        baseline_var=Var("金庫型"),
        t_var=Var(bad),
        _fold_designer_baseline_commit_guard=False,
        _reset_manual_corner_parameter_locks=lambda: calls.append("corner-reset"),
    )
    monkeypatch.setattr(gui.messagebox, "showerror",
                        lambda *a: calls.append(("error", a)))
    monkeypatch.setattr(api, "read_operator_baseline_fold_defaults",
                        lambda *a, **kw: pytest.fail("invalid T reached baseline"))
    gui.on_baseline_changed(host)
    assert len(calls) == 1
    assert calls[0][0] == "error"


def test_gui_vault_baseline_forwards_raw_t_to_public_engine(monkeypatch):
    sent = []
    host = SimpleNamespace(
        baseline_var=Var("金庫型"),
        t_var=Var("2.125"),
        _fold_designer_baseline_commit_guard=False,
        _reset_manual_corner_parameter_locks=lambda: None,
        _derived_cache_owner=SimpleNamespace(invalidate=lambda *_: None),
        _apply_cabinet_family_for_current_model=lambda: None,
        _baseline_last_value="金庫型",
        _current_box_assembly_type=lambda: "INSERT_OVERLAY",
        box_assembly_type_var=None,
        cb_box_assembly=None,
        refresh_corner_type_panel=lambda: None,
        fold_designer_app=None,
        _current_cabinet_type_name=lambda: "金庫型",
        endcap_fw_state={
            "head": {"follow_box": False, "value": 25},
            "tail": {"follow_box": False, "value": 25},
        },
        _sync_endcap_fw_controls=lambda: None,
        _request_phase6_update=lambda reason: sent.append(("update", reason)),
    )
    for name in (
        "yl1_var", "yr1_var", "ytop1_var", "ybottom1_var", "fw_z_var",
        "door_fold_l_var", "door_fold_r_var", "door_fold_t_var", "door_fold_b_var",
    ):
        setattr(host, name, Var(""))
    def baseline(model, *, thickness):
        sent.append(("baseline", model, thickness))
        return {
            "endcap": {"yl1": 15, "yr1": 15, "ytop1": 16,
                       "ybottom1": 15, "fw": 25},
            "door": None,
        }
    monkeypatch.setattr(api, "read_operator_baseline_fold_defaults", baseline)
    monkeypatch.setattr(gui.messagebox, "showerror",
                        lambda *a: pytest.fail(f"unexpected baseline error: {a}"))
    gui.on_baseline_changed(host)
    assert sent == [
        ("baseline", "金庫型", "2.125"),
        ("update", "baseline"),
    ]
    assert host.yl1_var.get() == "15"
