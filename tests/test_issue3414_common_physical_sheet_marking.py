"""Shared tool over existing ordinary/scoped authorities; no new DXF admission."""

from dataclasses import replace

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_drawing import LinePrimitive
from ae_engine.sheetmetal_geometry import Vec2
from tests.test_issue3412_manual_marking_first_sheet import actual_sheet
from tests.test_issue3414_scoped_marking_proto import _ids, _real_source, _resize, _raw_write


def _place(draft, *, shift=0):
    bend = next(p for p in draft.context.render_data.scene.primitives
                if isinstance(p, LinePrimitive) and p.layer == "BEND")
    x = (bend.p1.x + bend.p2.x) / 2 + shift
    y = (bend.p1.y + bend.p2.y) / 2
    return api.create_physical_sheet_mark(
        draft, draft.features, midpoint=Vec2(x, y), length=12, angle_deg=37,
    )


def test_same_tool_ordinary_and_two_physical_scoped_owners(actual_sheet, tmp_path):
    _, render, context, _, _ = actual_sheet
    with pytest.raises(ValueError, match="CONTEXT_MISMATCH"):
        api.open_physical_sheet_marking(
            "base_plate", context=replace(context, width=context.width + 1),
        )
    ordinary = api.open_physical_sheet_marking("base_plate", context=context)
    assert ordinary.saved_marks == () and "circle" in ordinary.allowed_tools
    first = _place(ordinary)
    update = api.commit_physical_sheet_marking(ordinary, ordinary, (first,))
    assert ordinary.features == () and update.scoped_store is None
    assert update.features == (first,)
    rendered = api.with_physical_sheet_features("base_plate", render, update.features)
    path = tmp_path / "ordinary-left.dxf"
    api.save_part_render_data_dxf(rendered, path, verify_reopen=True)
    doc = ezdxf.readfile(path)
    ink, = doc.modelspace().query('LWPOLYLINE[layer=="MARKING"]')
    assert tuple(map(tuple, ink.get_points("xy"))) == tuple((p.x, p.y) for p in first.points)
    assert api.verify_saved_part_render_data_dxf(rendered, path).ok

    source = _real_source()
    owner_a, owner_b = _ids(source)
    a = api.open_physical_sheet_marking("base_plate", snapshot=source, selection=(0, 0))
    b = api.open_physical_sheet_marking("base_plate", snapshot=source, selection=(0, 1))
    assert a.owner_id == owner_a and b.owner_id == owner_b
    assert a.owner_id != b.owner_id != ordinary.owner_id
    assert a.allowed_tools == b.allowed_tools == ("line",)
    mark_a, mark_b = _place(a, shift=14), _place(b, shift=-18)
    assert mark_a != mark_b
    a_update = api.commit_physical_sheet_marking(a, a, (mark_a,))
    assert api.SCOPED_BASE_PLATE_MARKS not in source
    current = {**source, api.SCOPED_BASE_PLATE_MARKS: a_update.scoped_store}
    b_current = api.open_physical_sheet_marking("base_plate", snapshot=current, selection=(0, 1))
    both = api.commit_physical_sheet_marking(b_current, b, (mark_b,)).scoped_store
    assert both[owner_a]["features"] == [mark_a] and both[owner_b]["features"] == [mark_b]
    assert a.saved_marks == b.saved_marks == ()
    with pytest.raises(ValueError, match="OWNER_STALE"):
        api.commit_physical_sheet_marking(b, a, (mark_a,))
    with pytest.raises(ValueError, match="TOOL_UNSUPPORTED"):
        api.create_physical_sheet_mark(a, (), tool="circle")

    old_a = api.open_physical_sheet_marking("base_plate", snapshot=current, selection=(0, 0))
    assert old_a.saved_marks == (mark_a,)
    with pytest.raises(ValueError, match="SOURCE_STALE"):
        api.commit_physical_sheet_marking(old_a, a, (mark_a,))
    assert current[api.SCOPED_BASE_PLATE_MARKS] == a_update.scoped_store


def test_canonical_native_head_is_not_a_marking_entitlement(tmp_path):
    import tkinter as tk
    from gui import Phase6PrimaryApplication
    from phase6_manufacturing_adapter import build_scene_payload_for_app
    source = _resize(_real_source(), 1)
    source["existing_parts"] = ["box_body", "head", "base_plate"]
    path = _raw_write(tmp_path / "actual.p6fold", source)
    root = tk.Tk()
    try:
        host = Phase6PrimaryApplication(root)
        host.load_phase6_project(path, open_designer=True)
        root.update()
        app = host.fold_designer_app
        app.activate_part("head")
        root.update()
        spec, context = host._fold_designer_part_spec_from_payload(
            "head", build_scene_payload_for_app(app, "head"),
        )
        canonical = api.build_part_render_data(spec, context)
        assert canonical.unfolded_topology.piece_id == "head"
        assert canonical.unfolded_topology.source == "ENDCAP_FOLD_PROFILE"
        assert spec.fold_profile_x and spec.fold_profile_y
        assert canonical.material.bounds == (0, 0, 822, 402)
        assert canonical.fold_guides
        head_context = api.resolve_physical_sheet_editor_context("head", canonical)
        with pytest.raises(ValueError, match="MANUAL_MARKING_V1_UNSUPPORTED_SOURCE"):
            api.open_physical_sheet_marking("head", context=head_context)
        with pytest.raises(ValueError, match="PART_MISMATCH"):
            api.open_physical_sheet_marking("base_plate", context=head_context)
    finally:
        root.destroy()
