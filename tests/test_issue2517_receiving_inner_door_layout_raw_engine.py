# -*- coding: utf-8 -*-
"""#2517 Receiving physical inner-door layouts are validated before coercion."""
from copy import deepcopy
import json
import inspect

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.cabinet_types import policy as family_policy
from ae_engine.cabinet_types import receiving as owner
from ae_engine.box_body_structure_state import (
    default_box_body_structure_state, set_side_back_back_panel_mode,
)
from gui_modules.application import receiving_inner_door_hole_editor as gui


PART = "inner_door:upper:panel"


def _snapshot():
    return {
        "model": "受電箱", "w": 800, "h": 1600, "d": 350,
        "t": 2, "fw": 29, "door_gap_w": 3.5, "door_gap_h": 3.5,
        "multi_door_enabled": True,
        "door_layout_columns": [[800, [1100, 500]]],
        "inner_doors": [{
            "stable_id": "upper", "cell_key": "0:0",
            "included_frame_sides": ["top"],
        }],
    }


def test_public_hole_editor_consumes_same_canonical_inner_door_family_policy():
    source = _snapshot()
    panel = family_policy.derive_inner_door_panels(source)[0]
    editor = api.resolve_inner_door_hole_editor_context(source, PART)
    assert editor.panel == panel
    assert editor.render.metadata["stable_id"] == PART
    assert "manufacturing_api.resolve_inner_door_hole_editor_context(" in inspect.getsource(gui.open_inner_door_hole_editor)


def test_saved_serialized_false_never_mints_manufactured_inner_door_or_frame():
    source = _snapshot()
    source["multi_door_enabled"] = "false"
    original = deepcopy(source)
    assert family_policy.derive_inner_door_panels(source) == ()
    assert family_policy.derive_inner_door_frame_sets(source) == ()
    with pytest.raises(ValueError, match="目前專案沒有"):
        api.resolve_inner_door_hole_editor_context(source, PART)
    assert source == original


def test_serialized_true_matches_native_boolean_in_real_part_and_frame_results():
    source = _snapshot()
    baseline = family_policy.derive_inner_door_panels(source)
    baseline_frames = family_policy.derive_inner_door_frame_sets(source)
    source["multi_door_enabled"] = "true"
    assert family_policy.derive_inner_door_panels(source) == baseline
    assert family_policy.derive_inner_door_frame_sets(source) == baseline_frames
    assert baseline_frames and baseline_frames[0].included_sides == ("top",)
    context = api.resolve_inner_door_hole_editor_context(source, PART)
    assert context.panel == baseline[0]
    reloaded = json.loads(json.dumps(source, allow_nan=False))
    assert api.resolve_inner_door_hole_editor_context(reloaded, PART).panel == context.panel


@pytest.mark.parametrize("bad", ["maybe", None, {}, [], 2, float("nan")])
def test_invalid_saved_multidoor_flag_is_rejected_before_any_physical_panel(bad):
    source = _snapshot()
    source["multi_door_enabled"] = bad
    before = repr(source)
    with pytest.raises(ValueError):
        family_policy.derive_inner_door_panels(source)
    with pytest.raises(ValueError):
        family_policy.derive_inner_door_frame_sets(source)
    with pytest.raises(ValueError):
        api.resolve_inner_door_hole_editor_context(source, PART)
    assert repr(source) == before


@pytest.mark.parametrize(("bad_column","needle"), [
    ([True, [1100, 500]], "bool"),
    ([800, [1100, True]], "bool"),
    (["nan", [1100, 500]], "finite"),
])
def test_unused_door_grid_cell_is_not_allowed_to_hide_bad_manufacturing_source(bad_column, needle):
    source = _snapshot()
    # First cell remains a valid upper inner door; malformed *unused* second
    # column used to be coerced by float(True) before any physical validation.
    source["door_layout_columns"].append(bad_column)
    before = deepcopy(source)
    with pytest.raises(ValueError, match=needle):
        family_policy.derive_inner_door_panels(source)
    with pytest.raises(ValueError, match=needle):
        family_policy.derive_inner_door_frame_sets(source)
    with pytest.raises(ValueError, match=needle):
        api.resolve_inner_door_hole_editor_context(source, PART)
    assert source == before


@pytest.mark.parametrize(("key","bad"), [
    ("cell_height", True), ("cell_height", float("nan")),
    ("thickness", False), ("thickness", float("inf")),
    ("gap_h", True), ("gap_h", float("nan")), ("gap_h", float("-inf")),
])
def test_engine_vertical_inner_door_panel_uses_true_finite_source(key, bad):
    values = {"cell_height": 1100.0, "thickness": 2.0, "gap_h": 3.5}
    values[key] = bad
    with pytest.raises(ValueError, match="finite"):
        owner.inner_door_panel_vertical_contract(**values)


def test_vertical_frame_rejects_serialized_disabled_door_topology_before_mating():
    source = _snapshot()
    source["multi_door_enabled"] = "false"
    with pytest.raises(ValueError, match="requires enabled Door topology"):
        owner.inner_door_vertical_frame_contract(source, "upper")


def test_half_back_panel_consumes_same_saved_door_enable_flag():
    source = _snapshot()
    structure = set_side_back_back_panel_mode(
        default_box_body_structure_state(), "HALF",
    )
    baseline = family_policy.resolve_back_panel_contract(
        source, source, structure_state=structure, panel_width=800, full_panel_height=1600,
    )
    assert baseline["mode"] == "HALF"
    for malformed in ("true", "false", "0", 1, {"enabled": True}):
        source["multi_door_enabled"] = malformed
        with pytest.raises(ValueError, match="requires authoritative Door topology"):
            family_policy.resolve_back_panel_contract(
                source, source, structure_state=structure, panel_width=800, full_panel_height=1600,
            )
    source["multi_door_enabled"] = True
    assert family_policy.resolve_back_panel_contract(
        source, source, structure_state=structure, panel_width=800, full_panel_height=1600,
    ) == baseline



def _persisted_legacy_inner_door_source(flag):
    return {
        "model": "金庫型",
        "multi_door_enabled": flag,
        "door_layout_columns": [[800.0, [1100.0, 500.0]]],
        "inner_doors": [{
            "stable_id": "upper",
            "cell_key": "0:0",
            # A disabled Door may not retain an obsolete physical Divider mate.
            "lower_frame_role": {
                "role": "stale", "divider_stable_id": "old-divider",
            },
        }],
    }


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
@pytest.mark.parametrize("flag", ("false", "off", "0", 0, False))
def test_saved_project_disabled_door_never_recomputes_obsolete_lower_mate(model, flag):
    snapshot = _persisted_legacy_inner_door_source(flag)
    snapshot["model"] = model
    prior = deepcopy(snapshot)
    normalized = api.normalize_authoritative_door_state(snapshot)
    assert "lower_frame_role" not in normalized["inner_doors"][0]
    # Persistence must not convert a serialized True to native bool and
    # thereby accidentally grant the separate Receiving HALF rear-panel policy.
    assert type(normalized["multi_door_enabled"]) is type(flag)
    assert normalized["multi_door_enabled"] == flag
    assert snapshot == prior


@pytest.mark.parametrize("flag", ("true", "on", "1", 1, True))
def test_saved_project_enabled_flag_keeps_its_source_type_for_half_policy(flag):
    source = {"model": "受電箱", "multi_door_enabled": flag, "inner_doors": []}
    normalized = api.normalize_authoritative_door_state(source)
    assert normalized["multi_door_enabled"] == flag
    assert type(normalized["multi_door_enabled"]) is type(flag)
    assert source["multi_door_enabled"] == flag


@pytest.mark.parametrize("flag", ("invalid", 2, None, [], {}, float("nan")))
def test_invalid_saved_multidoor_flag_fails_in_public_project_authority_before_write(flag):
    payload = {
        "schema": "phase6-fold-project-v1",
        "snapshot": {"model": "金庫型", "multi_door_enabled": flag},
    }
    prior = repr(payload)
    with pytest.raises(ValueError, match="布林值"):
        api.project_operator_project_for_write(payload)
    assert repr(payload) == prior


def test_real_p6fold_legacy_false_door_clears_obsolete_physical_mate(tmp_path):
    import phase6_project_file as project

    source = _persisted_legacy_inner_door_source("false")
    before = deepcopy(source)
    target = project.write_project(
        tmp_path / "legacy-disabled-inner-door.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": source},
    )
    reopened = project.read_project(target)["snapshot"]
    assert reopened["multi_door_enabled"] == "false"
    assert "lower_frame_role" not in reopened["inner_doors"][0]
    assert source == before


def test_project_authority_has_no_python_truthiness_for_saved_door_presence():
    from ae_engine import project_snapshot_state as persistence_owner

    function = inspect.getsource(persistence_owner.normalize_authoritative_door_state)
    assert "normalize_operator_settings_boolean(" in function
    assert 'bool(result.get("multi_door_enabled"' not in function
    assert 'result["multi_door_enabled"] = enabled_door_topology' not in function
