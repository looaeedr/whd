"""#2517 main GUI EndCap PartSpec must never fabricate 25mm physical FW."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application import manufacturing_adapter as gui


def _host(monkeypatch, *, state=None):
    calls = []
    body = state or api.normalize_endcap_fw_state({"fw": 29.125})
    def profiles(key):
        calls.append(("profile", key))
        return {"X": (), "Y": ()}
    def effective(part, raw_fw):
        calls.append(("effective", part, raw_fw))
        api.project_operator_endcap_fw_controls(body, raw_fw)
        return api.resolve_endcap_fw(
            {"fw": raw_fw, "endcap_fw": body}, part, state=body,
        )
    def spec(values, **kwargs):
        calls.append(("spec", kwargs["is_tail"], values["fw"]))
        return {"values": deepcopy(values), "kwargs": kwargs}
    monkeypatch.setattr(
        gui, "_endcap_profiles_for_assembly",
        lambda values, stored, assembly, part: stored,
    )
    app = SimpleNamespace(
        workspace_controller=SimpleNamespace(
            profile_for=profiles, box_body_profile=lambda: (),
            box_body_structure_state=lambda: {},
        ),
        endcap_fw_state=body,
        _effective_endcap_fw=effective,
        _current_box_assembly_type=lambda: "CROSS",
        _baseline_source_model=lambda: "金庫型",
        _resolved_committed_assembly_relief_cuts=lambda *a: (),
        _end_cap_part_spec_from_values=spec,
        _manual_corner_policy=lambda part, fw: (part, fw),
        _endcap_depth_comp_t_for_family=lambda family: None,
        head_holes=(), tail_holes=(),
    )
    return app, calls


@pytest.mark.parametrize("raw", [None, True, False, "", "NaN", "bad", 0, -2,
                                  float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("tail", [False, True])
def test_invalid_or_absent_part_spec_box_fw_cannot_reach_any_manufacturing_stage(
    monkeypatch, raw, tail,
):
    app, calls = _host(monkeypatch)
    input_source = {"model": "金庫型", "w": 500, "h": 600, "d": 200, "t": 2}
    if raw is not None:
        input_source["fw"] = raw
    before = deepcopy(input_source)
    with pytest.raises(ValueError, match="FW 包外尺寸"):
        gui._end_cap_part_spec(app, input_source, is_tail=tail)
    assert calls == []
    assert input_source == before


@pytest.mark.parametrize("tail,expected", [(False, 33.25), (True, 34.5)])
def test_existing_four_mode_override_stays_engine_owned_with_fractional_box_fw(
    monkeypatch, tail, expected,
):
    saved = api.normalize_endcap_fw_state({"fw": 29.125})
    api.commit_endcap_fw(saved, "head", 33.25, box_fw=29.125)
    api.commit_endcap_fw(saved, "tail", 34.5, box_fw=29.125)
    original = deepcopy(saved)
    app, calls = _host(monkeypatch, state=saved)
    val = {"model": "金庫型", "w": 500, "h": 600, "d": 200, "t": 2,
           "fw": "29.125"}
    before = deepcopy(val)
    built = gui._end_cap_part_spec(app, val, is_tail=tail)
    assert built["values"]["fw"] == expected
    assert built["kwargs"]["is_tail"] is tail
    assert calls[0] == ("profile", "tail" if tail else "head")
    assert calls[1] == ("effective", "tail" if tail else "head", 29.125)
    assert calls[2] == ("spec", tail, expected)
    assert val == before and saved == original
    reloaded = json.loads(json.dumps({"fw": 29.125, "endcap_fw": saved}))
    assert api.resolve_endcap_fw(reloaded, "tail" if tail else "head") == expected


def test_main_gui_part_spec_validates_exact_source_before_any_profile_read():
    source = inspect.getsource(gui._end_cap_part_spec)
    assert 'val.get("fw", 25.0)' not in source
    assert 'manufacturing_api.normalize_operator_source_dimension(' in source
    assert 'val.get("fw"), field="fw"' in source
    assert source.index("normalize_operator_source_dimension(") < source.index(
        "self.workspace_controller.profile_for(key)"
    )
    assert "self._effective_endcap_fw(key, box_fw)" in source
