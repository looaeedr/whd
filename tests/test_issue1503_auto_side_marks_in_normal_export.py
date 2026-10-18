# -*- coding: utf-8 -*-
"""#1503 actual ordinary physical BoxBody export auto-marks both side panels.

No extra EAR buttons. Proven source-world contact -> SIDE UV MARKING passes
through the EXISTING selected-DXF export and canonical manufacturing sink.
Other box-body physical pieces remain present/unchanged, and submitted NFB
door/base/quantity safety blocks remain intact.
"""
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine.manufacturing_export import (
    resolved_physical_render_parts,
)
from ae_engine.manufacturing_scene_access import owner_render_data
from gui_modules.project.export_actions import _export_selected_resolved_parts
from tests.test_issue1503_ear_side_check_only_dxf import _actual
from tests.test_receiving_base_physical_3d_z_assembly import _assembled
from tests.test_receiving_two_tier_physical_base_parts import _two_tier


def _host(snapshot, geometry):
    calls = []
    class Designer:
        _phase6_input_snapshot = snapshot
        designer_workspace = None
        def _phase6_resolve_manufacturing_geometry(self):
            calls.append("resolve")
            return geometry
    return SimpleNamespace(fold_designer_app=Designer()), calls


def _flags(**edits):
    base = {
        "box_body": True, "head": False, "tail": False,
        "door": False, "base_plate": False,
        "indicator_box": False, "indicator_door": False,
    }
    base.update(edits)
    return base


def _mark_lines(fp):
    result = []
    doc = ezdxf.readfile(fp)
    for entity in doc.modelspace():
        if entity.dxftype() != "LINE" or entity.dxf.layer.upper() != "MARKING":
            continue
        p1 = (round(entity.dxf.start.x, 6), round(entity.dxf.start.y, 6))
        p2 = (round(entity.dxf.end.x, 6), round(entity.dxf.end.y, 6))
        result.append(tuple(sorted((p1, p2))))
    return tuple(sorted(result))


@pytest.mark.parametrize("factory,expected_per_side", ((_assembled, 4), (_two_tier, 8)))
def test_normal_selected_boxbody_exports_all_physical_pieces_plus_real_ear_marks(
    tmp_path, factory, expected_per_side,
):
    from ae_engine.receiving_ear_side_manufacturing_marking import (
        export_receiving_ear_side_manufacturing_marking_dxf,
    )
    snapshot, geometry = _actual(factory)
    host, calls = _host(snapshot, geometry)
    original = tuple(
        (key, tuple(render.scene.primitives or ()))
        for key, render in resolved_physical_render_parts(geometry)
    )
    before_l = owner_render_data(geometry, "box_body:left_side")
    before_r = owner_render_data(geometry, "box_body:right_side")
    normal = tmp_path / "normal"
    filenames, errors = _export_selected_resolved_parts(host, str(normal), _flags())
    assert errors == []
    assert calls == ["resolve"]
    assert "box_body__left_side.dxf" in filenames
    assert "box_body__right_side.dxf" in filenames
    assert len(filenames) > 2, "normal export must retain other body panels"
    assert len(list(normal.glob("*.dxf"))) == len(filenames)
    for part in ("left_side", "right_side"):
        actual = _mark_lines(normal / ("box_body__" + part + ".dxf"))
        assert len(actual) >= expected_per_side
    # The former separate manual export remains an independent reference,
    # not a prerequisite or the implementation of the normal exporter.
    reference = export_receiving_ear_side_manufacturing_marking_dxf(
        snapshot, geometry, tmp_path / "reference",
        dimensions=(800, 1600, 350), sheet_thickness=2.,
    )
    for side, fp in reference.output_paths:
        assert _mark_lines(fp) == _mark_lines(
            normal / ("box_body__" + side.split(":")[1] + ".dxf")
        )
    assert owner_render_data(geometry, "box_body:left_side") is before_l
    assert owner_render_data(geometry, "box_body:right_side") is before_r
    assert original == tuple(
        (key, tuple(render.scene.primitives or ()))
        for key, render in resolved_physical_render_parts(geometry)
    )


@pytest.mark.parametrize("flags", (
    {"door": True},
    {"base_plate": True},
    {"door": True, "base_plate": True},
))
def test_normal_export_with_submitted_nfb_must_not_release_unverified_other_parts(
    tmp_path, flags,
):
    snapshot, geometry = _actual(_assembled)
    host, calls = _host(snapshot, geometry)
    with pytest.raises(ValueError, match="舊式內門|NFB"):
        _export_selected_resolved_parts(host, str(tmp_path / "blocked"), _flags(**flags))
    assert calls == []
    assert not (tmp_path / "blocked").exists()


@pytest.mark.parametrize("changes,pattern", (
    ({"w":750.}, "CURRENT_W800_T2"),
    ({"t":3.}, "CURRENT_W800_T2"),
    ({"nfb_config_submitted":False}, None),
))
def test_normal_export_cannot_invent_ear_marks_for_unsupported_input(
    tmp_path, changes, pattern,
):
    snapshot, geometry = _actual(_assembled)
    snapshot = {**snapshot, **changes}
    host, _ = _host(snapshot, geometry)
    if pattern:
        with pytest.raises(ValueError, match=pattern):
            _export_selected_resolved_parts(host, str(tmp_path/"out"), _flags())
        assert not (tmp_path/"out").exists()
    else:
        names, errors = _export_selected_resolved_parts(
            host, str(tmp_path/"unsubmitted"), _flags())
        assert not errors
        assert "box_body__left_side.dxf" in names
        # Unsubmitted original body has no auto-applied EAR contact marks.
        assert not owner_render_data(geometry, "box_body:left_side").metadata.get(
            "receiving_ear_side_marking_provenance"
        )


def test_normal_export_rejects_source_geometry_mismatch_before_output(tmp_path):
    snap, geom = _actual(_assembled)
    host, _ = _host({**snap, "h": 1700.}, geom)
    with pytest.raises(ValueError, match="SOURCE|MATERIAL|MATING|CONTACT|PREVIEW"):
        _export_selected_resolved_parts(host, str(tmp_path/"bad"), _flags())
    assert not (tmp_path/"bad").exists()


def test_no_extra_ear_buttons_in_normal_left_panel_source():
    path = Path(__file__).resolve().parents[1] / "gui_modules/layout/left_panel.py"
    text = path.read_text(encoding="utf-8")
    assert "command=host.export_selected_dxf" in text
    assert "command=host.export_receiving_ear_side_check_dxf" not in text
    assert "command=host.export_receiving_ear_side_manufacturing_dxf" not in text
