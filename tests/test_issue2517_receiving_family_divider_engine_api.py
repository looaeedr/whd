"""#2517: Family Divider manufacturing Joint assembly orchestrates only in Engine."""
from __future__ import annotations

from copy import deepcopy
import inspect

from ae_engine import manufacturing_api as api
from ae_engine import divider_manufacturing as owner
from phase6_manufacturing_geometry import _phase6_resolve_family_divider_reliefs as gui_family
from tests.test_issue39_divider_relief import _snapshot, _body_part, _divider_part


def test_public_engine_is_family_divider_owner_and_gui_is_single_api_adapter():
    assert api.resolve_family_divider_reliefs is owner.resolve_family_divider_reliefs
    source = inspect.getsource(gui_family)
    assert "manufacturing_api.resolve_family_divider_reliefs(" in source
    assert "resolve_divider_final_geometry(" not in source
    assert "from phase6_" not in inspect.getsource(owner.resolve_family_divider_reliefs)
    assert "build_joint_world_geometry(" in inspect.getsource(owner.resolve_family_divider_reliefs)


def test_actual_receiving_divider_registry_result_matches_gui_and_unmodified_source():
    snapshot = _snapshot()
    snapshot_before = deepcopy(snapshot)
    body = _body_part(snapshot)
    divider, divider_scene_part = _divider_part(snapshot)
    parts = (body, divider_scene_part)
    kwargs = dict(
        finished_dimensions=(snapshot["w"], snapshot["h"], snapshot["d"]),
        sheet_thickness=snapshot["t"],
        clearance=0.0,
    )
    engine_parts, engine_diagnostics, joints = api.resolve_family_divider_reliefs(parts, **kwargs)
    gui_parts, gui_diagnostics, gui_joints = gui_family(parts, **kwargs)
    by_key = {p.part_key: p for p in engine_parts}
    by_gui = {p.part_key: p for p in gui_parts}
    assert len(joints) == 1
    assert joints[0].subject_part == divider.stable_id
    assert joints == gui_joints
    assert len(engine_diagnostics) == 1
    assert engine_diagnostics[0].registry_status == "HIT"
    assert engine_diagnostics[0].candidate_status.startswith("CERTIFIED_REGISTRY_")
    assert engine_diagnostics[0].candidate_status == gui_diagnostics[0].candidate_status
    assert by_key[divider.stable_id].render_data.material.equals(
        by_gui[divider.stable_id].render_data.material
    )
    assert by_key[divider.stable_id].render_data.material.area < divider_scene_part.render_data.material.area
    assert by_key["box_body"] is body
    assert snapshot == snapshot_before


def test_missing_family_divider_or_missing_body_is_not_manufactured():
    snapshot = _snapshot()
    body = _body_part(snapshot)
    _, divider_part = _divider_part(snapshot)
    assert api.resolve_family_divider_reliefs(
        (body,), finished_dimensions=(800.0, 1600.0, 350.0),
        sheet_thickness=2.0
    ) == ((body,), (), ())
    assert api.resolve_family_divider_reliefs(
        (divider_part,), finished_dimensions=(800.0, 1600.0, 350.0),
        sheet_thickness=2.0
    ) == ((divider_part,), (), ())
