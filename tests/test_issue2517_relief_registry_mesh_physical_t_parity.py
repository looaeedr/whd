"""#2517: Fold Designer 3D Registry and Fold Mesh T obey immutable Engine source."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
import inspect
import json

import pytest

from ae_engine import manufacturing_api as api
import ae_engine.operator_relief_candidate_3d as candidate
import fold_designer_bridge as gui
import phase6_project_file as project


def _snap(t=2.125):
    return {"model": "金庫型", "w": 800.0, "h": 1200.0, "d": 350.0, "t": t}


def _host(snapshot, settings=None):
    calls = []
    material = object()
    host = SimpleNamespace(
        _phase6_input_snapshot=deepcopy(snapshot),
        _settings_values=deepcopy(settings or {}),
        _phase6_assembly_type="INSERT",
        designer_workspace=SimpleNamespace(
            available_parts=("box_body",),
            active_part="head",
            profiles_for=lambda *_args: {"X": (), "Y": ()},
        ),
        state=SimpleNamespace(profiles={"X": (), "Y": ()}, profiles_vault={}),
        _scene_query_callback=lambda part, payload: (
            calls.append(("scene", part)) or SimpleNamespace(material=material)
        ),
    )
    return host, calls, material


def _registry_monkeypatch(monkeypatch):
    events = []
    monkeypatch.setattr(gui, "_phase6_scene_query_payload_for_part", lambda *_: {})
    monkeypatch.setattr(gui, "_phase6_mesh_profiles_for_part", lambda *_: ((), ()))
    monkeypatch.setattr(gui, "_phase6_operator_finished_dimensions", lambda *_: {
        "w": 800.0, "h": 1200.0, "d": 350.0,
    })
    monkeypatch.setattr(gui, "_phase6_assembly_relief_clearance", lambda *_: 0.0)
    monkeypatch.setattr(gui, "_phase6_box_structure_state", lambda *_: {})
    monkeypatch.setattr(gui, "_phase6_current_cabinet_family", lambda *_: "金庫型")

    def validate(_record, **kwargs):
        events.append(kwargs)
        return {"source_T": kwargs["sheet_thickness"]}
    monkeypatch.setattr(api, "validate_operator_relief_registry_candidate_3d", validate)
    return events


@pytest.mark.parametrize("bad", (
    True, False, None, 0, -1, "bad", "nan",
    float("nan"), float("inf"), float("-inf"), [], {},
))
def test_direct_public_3d_candidate_rejects_invalid_t_before_rule_or_geometry(
    monkeypatch, bad,
):
    # Invalid headless physical sources cannot reach any Rule/FinalScene solver.
    monkeypatch.setattr(
        candidate, "_validate_editable_rule_record",
        lambda *_: pytest.fail("invalid physical T entered Registry"),
    )
    with pytest.raises(ValueError):
        api.validate_operator_relief_registry_candidate_3d(
            {"rule_id": "test"}, candidate_id="candidate",
            assembly_intent="INSERT", part_inputs={},
            finished_dimensions=(800, 1200, 350),
            sheet_thickness=bad, clearance=0.0,
            box_body_structure_state={}, cabinet_family="金庫型",
        )


def test_direct_headless_registry_candidate_uses_fractional_real_t_in_both_solvers(
    monkeypatch,
):
    seen = []
    monkeypatch.setattr(candidate, "_validate_editable_rule_record",
                        lambda *_: {"assembly_intent": "INSERT"})
    monkeypatch.setattr(
        candidate, "evaluate_editable_endcap_rule_record",
        lambda _record, **kw: (seen.append(("rule", kw["sheet_thickness"])) or object()),
    )
    def solve(**kw):
        seen.append(("world3d", kw["sheet_thickness"]))
        return SimpleNamespace(
            verified=True, trust_level="CERTIFIED", rule_id="test",
            rule_revision=0, residual_projection=SimpleNamespace(pair_count=0),
        )
    monkeypatch.setattr(candidate, "solve_world_backprojected_endcap_relief", solve)
    render = SimpleNamespace(material=object())
    part = (render, ({"len": 20.0},), ())
    result = api.validate_operator_relief_registry_candidate_3d(
        {"rule_id": "test"}, candidate_id="c", assembly_intent="INSERT",
        part_inputs={"box_body": part, "head": part},
        finished_dimensions=(800, 1200, 350),
        sheet_thickness="2.125", clearance=0.0,
        box_body_structure_state={}, cabinet_family="金庫型",
    )
    assert result["candidate_specific"]
    assert result["validated_parts"] == ["head"]
    assert seen == [("rule", 2.125), ("world3d", 2.125)]


def test_gui_3d_registry_t_prioritizes_saved_snapshot_before_stale_settings(
    monkeypatch,
):
    events = _registry_monkeypatch(monkeypatch)
    host, calls, _ = _host(_snap(t="2.125"), {"t": 9.0})
    source_before = deepcopy(host._phase6_input_snapshot)
    assert gui._phase6_registry_validate_candidate_3d(
        host, {"rule_id": "c"}, candidate_id="c",
    ) == {"source_T": 2.125}
    assert events[0]["sheet_thickness"] == api.project_operator_manufacturing_request_snapshot(
        host._phase6_input_snapshot, host._settings_values, {},
    )["t"]
    assert calls == [("scene", "box_body")]
    assert host._phase6_input_snapshot == source_before


@pytest.mark.parametrize("snapshot,settings", (
    ({"t": True}, {"t": 2}),
    ({"t": float("nan")}, {"t": 2}),
    ({"t": 0}, {"t": 2}),
    ({}, {"t": "not numeric"}),
    ({}, {}),
))
def test_invalid_gui_3d_candidate_blocks_before_any_scene_or_registry(
    monkeypatch, snapshot, settings,
):
    events = _registry_monkeypatch(monkeypatch)
    host, calls, _ = _host({"model": "金庫型", **snapshot}, settings)
    with pytest.raises(ValueError):
        gui._phase6_registry_validate_candidate_3d(
            host, {}, candidate_id="c",
        )
    assert calls == []
    assert events == []


def test_gui_active_3d_fold_mesh_uses_same_engine_t_and_retains_raw_source(
    monkeypatch,
):
    values = []
    monkeypatch.setattr(
        api, "project_operator_3d_mesh_profiles",
        lambda *_a, **kw: values.append(kw) or (("x",), ("y",)),
    )
    host, _, material = _host(_snap(t=2.125), {"t": 9.0})
    source = deepcopy(host._phase6_input_snapshot)
    assert gui._phase6_mesh_profiles_for_part(host, "head", material) == (
        ("x",), ("y",),
    )
    assert values[0]["thickness"] == 2.125
    assert host._phase6_input_snapshot == source


@pytest.mark.parametrize("raw", (True, 0, "nan", float("inf"), None))
def test_gui_3d_fold_mesh_invalid_saved_t_never_reaches_engine_solver(
    monkeypatch, raw,
):
    calls = []
    monkeypatch.setattr(
        api, "project_operator_3d_mesh_profiles",
        lambda *_a, **kw: calls.append(kw) or (),
    )
    host, _, material = _host(_snap(t=raw), {"t": 2.0})
    with pytest.raises(ValueError):
        gui._phase6_mesh_profiles_for_part(host, "head", material)
    assert calls == []


def test_real_project_save_reload_has_one_physical_t_for_gui_mesh_registry_and_request(
    tmp_path, monkeypatch,
):
    settings = {"t": 9.0}
    authored = _snap(t=2.375)
    before = deepcopy(authored)
    target = project.write_project(
        tmp_path / "real-relief-t-source.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": authored},
    )
    saved = project.read_project(target)["snapshot"]
    json_roundtrip = json.loads(json.dumps(saved, ensure_ascii=False))
    assert api.project_operator_manufacturing_request_snapshot(
        json_roundtrip, settings, {},
    )["t"] == 2.375

    events = _registry_monkeypatch(monkeypatch)
    host, calls, _ = _host(json_roundtrip, settings)
    assert gui._phase6_registry_validate_candidate_3d(
        host, {}, candidate_id="c",
    )["source_T"] == 2.375
    assert events[0]["sheet_thickness"] == 2.375
    assert calls == [("scene", "box_body")]
    assert authored == before


def test_gui_has_no_separate_t_float_fallback_in_3d_source_paths():
    candidate_source = inspect.getsource(gui._phase6_registry_validate_candidate_3d)
    mesh_source = inspect.getsource(gui._phase6_mesh_profiles_for_part)
    for source in (candidate_source, mesh_source):
        assert "manufacturing_api.project_operator_manufacturing_request_snapshot(" in source
        assert 'snapshot.get("t", 2.0)' not in source
        assert "_num(settings.get(" not in source

@pytest.mark.parametrize("raw,expected", (
    ("false", False), ("true", False), (1, False),
    (0, False), (None, False), (False, False), (True, True),
))
def test_direct_registry_3d_never_claims_string_or_numeric_verified_evidence(
    monkeypatch, raw, expected,
):
    monkeypatch.setattr(
        candidate, "_validate_editable_rule_record",
        lambda *_: {"assembly_intent": "INSERT"},
    )
    monkeypatch.setattr(
        candidate, "evaluate_editable_endcap_rule_record",
        lambda *_a, **_kw: object(),
    )
    monkeypatch.setattr(
        candidate, "solve_world_backprojected_endcap_relief",
        lambda **_kw: SimpleNamespace(
            verified=raw, trust_level="CERTIFIED", rule_id="test",
            rule_revision=1, residual_projection=SimpleNamespace(pair_count=0),
        ),
    )
    render = SimpleNamespace(material=object())
    physical = (render, ({"len": 20.0},), ())
    outcome = api.validate_operator_relief_registry_candidate_3d(
        {"rule_id": "test"}, candidate_id="test",
        assembly_intent="INSERT",
        part_inputs={"box_body": physical, "head": physical},
        finished_dimensions=(800.0, 1200.0, 350.0),
        sheet_thickness=2.125, clearance=0.0,
        box_body_structure_state={}, cabinet_family="金庫型",
    )
    assert outcome["zero_penetration"] is expected
    assert outcome["solutions"]["head"]["verified"] is expected
    assert type(outcome["zero_penetration"]) is bool
