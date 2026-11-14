"""#2517: Door Divider 2D preview must reject malformed physical sources early."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import assembly_placement, door_dividers
from gui_modules.application.render_snapshots import door_layout_divider_frame_snapshot


def source(family="金庫型"):
    cols = [[200.25, [100.25, 200.25]], [300.25, [300.5]]]
    state = {
        "model": family, "w": 500.5, "h": 300.5, "d": 350.0,
        "t": 2.0, "fw": 29.0, "door_layout_columns": cols,
    }
    values = {"w": 500.5, "h": 300.5, "d": 350.0, "t": 2.0, "fw": 29.0}
    return state, cols, values


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_headless_gui_json_and_real_assembly_placement_are_same(family):
    saved, columns, val = source(family)
    original = deepcopy((saved, columns, val))
    reloaded = json.loads(json.dumps(saved, ensure_ascii=False))
    result = api.project_operator_door_divider_frame_preview(
        reloaded, columns, val, layout_scope="main", model_name=family,
    )
    host = SimpleNamespace(
        _compose_phase6_project_snapshot_from_main_gui=lambda: deepcopy(reloaded),
        _baseline_source_model=lambda: family,
        door_layout_scope="main", door_layout_handle_edges={},
    )
    assert door_layout_divider_frame_snapshot(host, columns, val) == result
    direct = door_dividers.derive_box_body_dividers(
        columns, depth=350.0, thickness=2.0, frame_width=29.0,
        layout_scope="main", model_name=family, handle_edges={},
    )
    assert len(direct) == 2
    assert len(result["dividers"]) == len(direct)
    for actual, part in zip(result["dividers"], direct):
        placed = assembly_placement.resolve_assembly_placement(reloaded, part.stable_id)
        assert actual == {
            "axis": part.axis,
            "span": part.span,
            "formed_core_depth": part.formed_core_depth,
            "world_offset": tuple(placed.world_offset),
        }
    assert (saved, columns, val) == original


@pytest.mark.parametrize("field,raw,where", [
    ("w", True, "snapshot"), ("h", False, "snapshot"),
    ("w", "nan", "snapshot"), ("h", "inf", "snapshot"),
    ("d", True, "live"), ("t", 0, "live"), ("t", "nan", "live"),
    ("d", -10, "live"), ("fw", "bad", "live"),
    ("fw", float("inf"), "live"), ("fw", False, "live"),
])
def test_bad_explicit_physical_source_rejected_before_divider_solver(monkeypatch, field, raw, where):
    snap, cols, val = source()
    if where == "snapshot":
        snap[field] = raw
    else:
        val[field] = raw
    monkeypatch.setattr(door_dividers, "derive_box_body_dividers",
                        lambda *a, **kw: pytest.fail("must fail before geometry"))
    with pytest.raises(ValueError, match="包外尺寸"):
        api.project_operator_door_divider_frame_preview(
            snap, cols, val, model_name="金庫型",
        )


@pytest.mark.parametrize("bad,which", [
    (True, "width"), (float("nan"), "width"),
    ("inf", "width"), (0, "width"), (False, "height"),
    ("nan", "height"), (-5, "height"),
])
def test_bad_canonical_cell_is_not_rewritten_as_empty_dividers(bad, which):
    state, columns, values = source()
    corrupted = deepcopy(columns)
    if which == "width":
        corrupted[0][0] = bad
    else:
        corrupted[0][1][0] = bad
    with pytest.raises(ValueError):
        api.project_operator_door_divider_frame_preview(
            state, corrupted, values, model_name="金庫型",
        )


@pytest.mark.parametrize("field", ("t", "d"))
def test_missing_thickness_or_depth_is_not_invented_from_preview_default(field):
    snap, cols, val = source()
    del snap[field]
    del val[field]
    with pytest.raises(ValueError, match="包外尺寸"):
        api.project_operator_door_divider_frame_preview(snap, cols, val)


def test_supplied_bad_snapshot_w_does_not_fallback_to_good_live_w():
    snap, cols, val = source()
    snap["w"] = True
    with pytest.raises(ValueError, match="包外尺寸"):
        api.project_operator_door_divider_frame_preview(snap, cols, val)


def test_legacy_absent_authoritative_layout_keeps_empty_display_not_fake_manufacturing():
    state, cols, val = source()
    state["door_layout_columns"] = []
    result = api.project_operator_door_divider_frame_preview(
        state, cols, val, model_name="金庫型",
    )
    assert isinstance(result["dividers"], tuple)
    assert isinstance(result["frames"], tuple)


def test_gui_and_engine_do_not_precast_cell_counts_or_fake_physical_dimensions():
    engine = inspect.getsource(api.project_operator_door_divider_frame_preview)
    gui = inspect.getsource(door_layout_divider_frame_snapshot)
    assert "normalize_operator_source_dimension(raw, field=field)" in engine
    assert "derive_door_layout_cells(normalized)" in engine
    assert "float(c[0])" not in engine
    assert 'val.get("t", 2.0)' not in engine
    assert 'val.get("d", 350.0)' not in engine
    assert "manufacturing_api.project_operator_door_divider_frame_preview(" in gui
