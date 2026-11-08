"""#2517: side/back physical Fold edit is Engine-owned, not GUI material geometry."""
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api
from ae_engine.box_body_structure_state import (
    default_box_body_structure_state,
    normalize_box_body_structure_state,
)
from ae_engine.box_body_fold_profile import build_box_body_profile
import fold_designer_bridge as bridge


def _snapshot(model="金庫型"):
    return {
        "model": model, "w": 800.0, "h": 600.0, "d": 250.0,
        "t": 2.0, "fw": 25.0, "zl1": 15.0, "zl2": 16.0,
        "zr1": 15.0, "zr2": 16.0,
    }


def _piece(role):
    if role == "left_side":
        return {"X": [
            {"phase6_key": "zl1", "len": 17.0, "angle": 90, "phase6_ui_sign": -1},
            {"phase6_key": "zl2", "len": 14.0, "angle": -90},
            {"phase6_key": "fw_left", "len": 25.0, "angle": -90},
            {"phase6_key": "d_left", "len": 244.0, "angle": -90},
            {"phase6_key": "side_rear_bend_left", "len": 12.5},
        ]}
    if role == "right_side":
        return {"X": [
            {"phase6_key": "d_right", "len": 244.0, "angle": -90},
            {"phase6_key": "fw_right", "len": 25.0, "angle": 90},
            {"phase6_key": "zr2", "len": 16.0, "angle": -90},
            {"phase6_key": "zr1", "len": 15.0, "angle": 90},
            {"phase6_key": "side_rear_bend_right", "len": 13.5},
        ]}
    return {"X": [{"phase6_key": "back_panel", "len": 797.5, "angle": 90}]}


def _plan(role, *, model="金庫型", piece=None, thickness=2.0, width=800.0,
          aggregate=None, structure=None):
    original = _snapshot(model)
    return manufacturing_api.plan_operator_box_body_piece_fold_commit(
        f"box_body:{role}",
        _piece(role) if piece is None else piece,
        structure_state=default_box_body_structure_state() if structure is None else structure,
        aggregate_profile=build_box_body_profile(original) if aggregate is None else aggregate,
        original_snapshot=original,
        thickness=thickness, total_width=width, box_height=600,
    )


@pytest.mark.parametrize("model", ["金庫型", "受電箱"])
@pytest.mark.parametrize("role", ["left_side", "back", "right_side"])
def test_real_engine_family_piece_plan_and_independent_save_reload(model, role):
    source = _snapshot(model)
    aggregate = build_box_body_profile(source)
    structure = default_box_body_structure_state()
    original_profile, original_structure = deepcopy(aggregate), deepcopy(structure)
    editing = _piece(role)
    original_edit = deepcopy(editing)
    result = _plan(
        role, model=model, aggregate=aggregate, structure=structure,
    )
    assert isinstance(result, manufacturing_api.OperatorBoxBodyPieceFoldPlan)
    assert ae_engine.plan_operator_box_body_piece_fold_commit is (
        manufacturing_api.plan_operator_box_body_piece_fold_commit
    )
    assert aggregate == original_profile and structure == original_structure
    assert editing == original_edit
    stored = result.structure_state["configs"]["three_piece_side_back_split"]
    assert role in stored["piece_profiles"]
    assert result.settings_values["h"] == 600.0
    assert tuple(row.get("phase6_key") for row in result.aggregate_profile) == tuple(
        row.get("phase6_key") for row in original_profile
    )
    if role == "back":
        assert stored["back_width_comp_t"] == pytest.approx(1.25)
        assert next(row["len"] for row in result.aggregate_profile if row.get("core") == "W") == next(
            row["len"] for row in aggregate if row.get("core") == "W"
        )
    else:
        assert result.settings_values["fw"] > 0
        assert result.aggregate_profile != ()
        assert not any(
            row.get("phase6_key") == "side_rear_bend_" + ("left" if role == "left_side" else "right")
            for row in result.aggregate_profile
        )
    if role == "left_side":
        assert result.settings_values["zl1"] < 0
        assert all(row["len"] > 0 for row in stored["piece_profiles"][role])
        assert all("phase6_ui_sign" not in row for row in stored["piece_profiles"][role])
    if role == "right_side":
        assert stored["piece_profiles"][role][0]["phase6_key"] == "side_rear_bend_right"
        assert all("phase6_ui_sign" not in row for row in stored["piece_profiles"][role])
    reopened = normalize_box_body_structure_state(json.loads(json.dumps(result.structure_state)))
    assert reopened["configs"]["three_piece_side_back_split"]["piece_profiles"][role] == stored["piece_profiles"][role]
    assert json.loads(json.dumps(result.aggregate_profile)) == list(result.aggregate_profile)


def test_role_material_mapping_is_shared_in_engine_only():
    original = _snapshot()
    base = build_box_body_profile(original)
    left = _plan("left_side", aggregate=base)
    by = {row.get("phase6_key"): row for row in left.aggregate_profile}
    assert by["zl1"]["len"] == 17
    assert by["zl2"]["len"] == 14
    assert by["fw_left"]["len"] == by["fw_right"]["len"] == 25
    assert by["d_left"]["len"] == by["d_right"]["len"] == 244
    right = _plan("right_side", aggregate=base)
    by = {row.get("phase6_key"): row for row in right.aggregate_profile}
    assert by["fw_left"]["len"] == by["fw_right"]["len"] == 25
    assert by["d_left"]["len"] == by["d_right"]["len"] == 244
    assert by["zr2"]["len"] == 16


@pytest.mark.parametrize("bad_part", [
    "back", "box_body", "box_body:divider", "box_body:left_side:extra", None, True,
])
def test_invalid_physical_piece_fails_closed(bad_part):
    with pytest.raises(ValueError):
        manufacturing_api.plan_operator_box_body_piece_fold_commit(
            bad_part, _piece("back"),
            structure_state=default_box_body_structure_state(),
            aggregate_profile=build_box_body_profile(_snapshot()),
            original_snapshot=_snapshot(),
            thickness=2.0, total_width=800, box_height=600,
        )


@pytest.mark.parametrize("bad", [True, 0, -3, float("nan"), float("inf"), "oops"])
@pytest.mark.parametrize("field", ["thickness", "width", "height"])
def test_physical_inputs_fail_before_any_source_write(bad, field):
    state = default_box_body_structure_state()
    profile = build_box_body_profile(_snapshot())
    previous = (deepcopy(state), deepcopy(profile))
    values = {"thickness": 2.0, "total_width": 800, "box_height": 600}
    values[{"width": "total_width", "height": "box_height", "thickness": "thickness"}[field]] = bad
    with pytest.raises((ValueError, TypeError)):
        manufacturing_api.plan_operator_box_body_piece_fold_commit(
            "box_body:back", _piece("back"),
            structure_state=state, aggregate_profile=profile,
            original_snapshot=_snapshot(), **values,
        )
    assert (state, profile) == previous


def test_late_bad_piece_row_rejects_without_partial_aggregate_or_structure_write():
    piece = _piece("left_side")
    piece["X"][-1]["len"] = float("nan")
    source = default_box_body_structure_state()
    aggregate = build_box_body_profile(_snapshot())
    saved = deepcopy(source), deepcopy(aggregate), deepcopy(piece)
    with pytest.raises(ValueError):
        _plan("left_side", piece=piece, structure=source, aggregate=aggregate)
    assert saved == (source, aggregate, piece)


def test_gui_submits_one_public_engine_plan_before_cache_mutation(monkeypatch):
    original = _snapshot()
    aggregate = build_box_body_profile(original)
    state = default_box_body_structure_state()
    host = SimpleNamespace(
        state=SimpleNamespace(profiles_vault={"箱身": deepcopy(aggregate)}),
        _phase6_input_snapshot=deepcopy(original),
        _settings_values={"t": 2.0},
        _phase6_box_whd={"w": 800.0, "h": 600.0, "d": 250.0},
    )
    calls = []
    monkeypatch.setattr(bridge, "_phase6_box_structure_state", lambda _self: deepcopy(state))
    monkeypatch.setattr(bridge, "_phase6_box_structure_w", lambda _self: 800.0)
    monkeypatch.setattr(bridge, "_phase6_store_editor_values",
                        lambda self, value, notify: calls.append(("settings", deepcopy(value), notify)))
    monkeypatch.setattr(bridge, "_phase6_commit_box_structure_state",
                        lambda self, value, rebuild: calls.append(("structure", deepcopy(value), rebuild)))
    monkeypatch.setattr(bridge, "_phase6_sync_authoritative_derived_parts",
                        lambda self: calls.append(("sync",)))
    bridge._phase6_commit_box_body_physical_piece_profile(
        host, "box_body:back", _piece("back"), notify=False,
    )
    assert [item[0] for item in calls] == ["settings", "structure", "sync"]
    assert calls[1][1]["configs"]["three_piece_side_back_split"]["back_width_comp_t"] == pytest.approx(1.25)
    assert host._phase6_input_snapshot["box_body_profile"] == host.state.profiles_vault["箱身"]


def test_gui_invalid_piece_leaves_all_sources_unmodified(monkeypatch):
    original = _snapshot()
    aggregate = build_box_body_profile(original)
    host = SimpleNamespace(
        state=SimpleNamespace(profiles_vault={"箱身": deepcopy(aggregate)}),
        _phase6_input_snapshot=deepcopy(original),
        _settings_values={"t": 2.0},
        _phase6_box_whd={"w": 800.0, "h": 600.0, "d": 250.0},
    )
    called = []
    monkeypatch.setattr(bridge, "_phase6_box_structure_state", lambda _self: default_box_body_structure_state())
    monkeypatch.setattr(bridge, "_phase6_box_structure_w", lambda _self: 800.0)
    monkeypatch.setattr(bridge, "_phase6_store_editor_values", lambda *a, **k: called.append("settings"))
    monkeypatch.setattr(bridge, "_phase6_commit_box_structure_state", lambda *a, **k: called.append("structure"))
    invalid = _piece("right_side")
    invalid["X"][-1]["len"] = float("nan")
    with pytest.raises(ValueError):
        bridge._phase6_commit_box_body_physical_piece_profile(host, "box_body:right_side", invalid)
    assert host.state.profiles_vault["箱身"] == aggregate
    assert host._phase6_input_snapshot == original
    assert called == []


def test_bridge_contains_no_child_material_or_back_width_compensation_formula():
    body = inspect.getsource(bridge._phase6_commit_box_body_physical_piece_profile)
    assert "manufacturing_api.plan_operator_box_body_piece_fold_commit(" in body
    for forbidden in (
        "back_width_comp_t", "copy_material_length", "piece_by_key",
        "set_side_back_geometry", "set_side_back_piece_profile",
        "apply_outside_dimension_compensation", "read_box_body_profile",
    ):
        assert forbidden not in body
