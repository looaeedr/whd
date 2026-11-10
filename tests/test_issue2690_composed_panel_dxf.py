"""#2690 Engine-only one-DXF physical-flat composition acceptance."""
from __future__ import annotations

from dataclasses import replace

import ezdxf
import pytest
from shapely.geometry import Point, Polygon

from ae_engine import manufacturing_api
from ae_engine.contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart
from ae_engine.manufacturing_render_data import (
    PartRenderData, fold_guides_from_final_scene,
)
from ae_engine.sheetmetal_drawing import DrawingScene, TextPrimitive
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine import composed_panel_dxf


def _flat(physical_id, *, width=100.0, height=60.0, hole=True, metadata=None):
    scene = DrawingScene()
    scene.add_polyline(
        ((0, 0), (width, 0), (width, height), (0, height)),
        layer="CUTTING", closed=True,
    )
    material = Polygon(((0, 0), (width, 0), (width, height), (0, height)))
    if hole:
        scene.add_circle((width/2, height/2), 4, layer="CUTTING",
                         source_type="mount_hole", source_id=physical_id + ":hole")
        material = material.difference(
            Point(width/2, height/2).buffer(4, quad_segs=32)
        )
    scene.add_line((10, 10), (width - 10, 10), layer="BEND")
    scene.add_line((11, 12), (width - 11, 12), layer="MARKING")
    scene.add_circle((width/2, 15), 2, layer="BLIND_HOLE")
    scene.add(TextPrimitive("REV-A", Vec2(20, 20), "CHECK", 5, 1, 2))
    return PartRenderData(
        scene=scene, material=material,
        fold_guides=fold_guides_from_final_scene(scene),
        metadata=metadata or {},
    )


def _geometry(*parts):
    return ResolvedManufacturingGeometry(
        parts=tuple(ResolvedManufacturingPart(key, render) for key, render in parts)
    )


def test_two_panels_and_multi_parts_one_dxf_full_primitive_reopen(tmp_path):
    left = _flat("box_body:left")
    right = _flat("box_body:right", width=90)
    door = _flat("door", width=80, height=40, hole=False)
    tail = _flat("tail", width=75)
    panels = (
        ("P2", _geometry(("box_body:left", left),
                         ("box_body:right", right), ("door", door))),
        ("P1", _geometry(("tail", tail))),
    )
    path = tmp_path / "manufacturing.dxf"
    validations = []
    result = manufacturing_api.save_composed_panel_dxf(
        panels, path, pre_commit_guard=lambda: validations.append("verified"),
    )
    assert result.path == str(path)
    assert len(validations) == 2
    assert tuple(p.panel_name for p in result.sheets) == ("P1", "P2", "P2", "P2")
    assert tuple(p.physical_id for p in result.sheets) == (
        "tail", "box_body:left", "box_body:right", "door",
    )
    assert list(tmp_path.glob("*.dxf")) == [path]
    doc = ezdxf.readfile(path)
    entities = tuple(doc.modelspace())
    assert {e.dxf.layer for e in entities} >= {
        "CUTTING", "BEND", "MARKING", "BLIND_HOLE", "CHECK",
    }
    text = [e.plain_text() for e in entities if e.dxftype() == "MTEXT"]
    for marker in ("P1", "P2", "tail", "box_body:left", "box_body:right", "door"):
        assert marker in text
    assert all(e.dxf.layer == "CHECK" for e in entities
               if e.dxftype() == "MTEXT" and e.plain_text() in {"P1", "P2"})
    assert len(tuple(e for e in entities if e.dxftype() == "CIRCLE"
                     and e.dxf.layer == "CUTTING")) == 3
    # Separate physical sheet envelopes plus a positive gap, never nested
    # overlap or world-coordinate recomputation.
    p2 = [sheet for sheet in result.sheets if sheet.panel_name == "P2"]
    previous_end = None
    for sheet in p2:
        x0,y0,x1,y1 = sheet.flat_bounds
        dx,dy = sheet.offset
        if previous_end is not None:
            assert x0+dx - previous_end >= 59.99
        previous_end = x1+dx
    assert result.sheets[0].offset[1] < p2[0].offset[1]
    assert list(tmp_path.glob(".whd-composed-stage-*")) == []


def test_rejected_metadata_preserves_preexisting_destination(tmp_path):
    target = tmp_path / "old.dxf"
    original = b"original-unchanged"
    target.write_bytes(original)
    bad = _flat("nfb_pad:fake", metadata={"nfb_deferred_manufacturing_role": "PAD"})
    with pytest.raises(ValueError, match="NFB_PAD_EAR"):
        manufacturing_api.save_composed_panel_dxf(
            (("P1", _geometry(("nfb_pad:fake", bad))),),
            target, pre_commit_guard=lambda: None, overwrite=True,
        )
    assert target.read_bytes() == original
    with pytest.raises(ValueError, match="SOURCE_NOT_MANUFACTURING_APPROVED"):
        manufacturing_api.save_composed_panel_dxf(
            (("P1", _geometry(("door", _flat(
                "door", metadata={"baseline_fit_error": "source mismatch"},
            )))),),
            target, pre_commit_guard=lambda: None, overwrite=True,
        )
    assert target.read_bytes() == original


def test_guard_source_drift_after_staging_leaves_destination_intact(tmp_path):
    target = tmp_path / "old.dxf"
    target.write_bytes(b"retained")
    count = 0
    def guard():
        nonlocal count
        count += 1
        if count == 2:
            raise ValueError("project source changed")
    with pytest.raises(ValueError, match="project source changed"):
        manufacturing_api.save_composed_panel_dxf(
            (("P1", _geometry(("door", _flat("door")))),),
            target, pre_commit_guard=guard, overwrite=True,
        )
    assert count == 2
    assert target.read_bytes() == b"retained"


def test_staged_corruption_cannot_replace_existing_output(tmp_path, monkeypatch):
    target = tmp_path / "old.dxf"
    target.write_bytes(b"preserve-me")
    real_save = composed_panel_dxf.save_scene_dxf
    def corrupt_composite(path, scene):
        if str(path).endswith("old.dxf"):
            scene = DrawingScene()  # simulate dropped material in staged output
        return real_save(path, scene)
    monkeypatch.setattr(composed_panel_dxf, "save_scene_dxf", corrupt_composite)
    with pytest.raises(ValueError, match="SHEET_READBACK_MISMATCH"):
        manufacturing_api.save_composed_panel_dxf(
            (("P1", _geometry(("door", _flat("door")))),),
            target, pre_commit_guard=lambda: None, overwrite=True,
        )
    assert target.read_bytes() == b"preserve-me"


def test_validation_of_names_inventory_request_and_unverified_cutting(tmp_path):
    good = _geometry(("door", _flat("door")))
    target = tmp_path / "x.dxf"
    for panels, code in [
        ((("P1", good), ("P1", good)), "DUPLICATE_PANEL_NAME"),
        ((("", good),), "盤名"),
        ((("P1", object()),), "FINAL_SCENE_REQUIRED"),
        ((("P1", _geometry()),), "PHYSICAL_INVENTORY_INVALID"),
        ((("P1", _geometry(("base_plate:nfb_layer:0", _flat("x")))),),
         "RECEIVING_NFB_TIER_BASE_MANUFACTURING_UNVERIFIED"),
        ((("P1", _geometry(("door", _flat(
            "door", metadata={"stable_id": "tail"},
        )))),), "COMPOSED_DXF_PHYSICAL_ID_SOURCE_MISMATCH"),
    ]:
        with pytest.raises(ValueError, match=code):
            manufacturing_api.save_composed_panel_dxf(
                panels, target, pre_commit_guard=lambda: None,
            )
    with pytest.raises(ValueError, match="PRECOMMIT_SOURCE_GUARD_REQUIRED"):
        manufacturing_api.save_composed_panel_dxf(
            (("P1", good),), target, pre_commit_guard=None,
        )
    assert not target.exists()



def test_canonical_box_body_topology_drives_flat_packaging(tmp_path):
    """Assembly's real formed-piece order and inset must survive flat packing."""
    from ae_engine.manufacturing_render_data import (
        BoxBodyPieceRenderData, BoxBodyStructureRenderData,
    )
    left = BoxBodyPieceRenderData(
        "box_body_left_side", "left_side", 0.0, 0.0, (),
        _flat("left"),
    )
    back = BoxBodyPieceRenderData(
        "box_body_back", "back", 100.0, 700.0, (),
        _flat("back", height=42), formed_y_offset=20.0,
    )
    right = BoxBodyPieceRenderData(
        "box_body_right_side", "right_side", 800.0, 800.0, (),
        _flat("right"),
    )
    # Deliberately scramble the pieces: a GUI display list is NOT the
    # immutable BoxBody owner's manufacturing order.
    assembly = BoxBodyStructureRenderData(
        "side_back", (right, back, left),
        _flat("exploded"), _flat("canonical"),
    )
    geometry = _geometry(
        ("box_body", assembly),
        ("door", _flat("door")),
    )
    path = tmp_path / "canonical-topology.dxf"
    result = manufacturing_api.save_composed_panel_dxf(
        (("P1", geometry),), path, pre_commit_guard=lambda: None,
    )
    assert tuple(sheet.physical_id for sheet in result.sheets) == (
        "box_body:box_body_left_side",
        "box_body:box_body_back",
        "box_body:box_body_right_side",
        "door",
    )
    # An inset back is elevated by the actual Engine formed_y_offset;
    # every flat's own UV and hole features remain unchanged.
    assert result.sheets[1].offset[1] - result.sheets[0].offset[1] == 20.0
    last_right_edge = None
    for sheet in result.sheets:
        x0, _, x1, _ = sheet.flat_bounds
        if last_right_edge is not None:
            assert x0 + sheet.offset[0] - last_right_edge >= 59.99
        last_right_edge = x1 + sheet.offset[0]
    msp = ezdxf.readfile(path).modelspace()
    assert sum(e.dxftype() == "CIRCLE" and e.dxf.layer == "CUTTING"
               for e in msp) == 4
    assert [e.plain_text() for e in msp if e.dxftype() == "MTEXT"
            and e.dxf.layer == "CHECK"][-1] == "P1"


def test_untrusted_body_topology_cannot_replace_existing_dxf(tmp_path):
    from ae_engine.manufacturing_render_data import (
        BoxBodyPieceRenderData, BoxBodyStructureRenderData,
    )
    bad = BoxBodyPieceRenderData(
        "box_body_left_side", "left_side", float("nan"), 0.0, (),
        _flat("left"),
    )
    source = BoxBodyStructureRenderData(
        "side_back", (bad,), _flat("exploded"), _flat("canonical"),
    )
    target = tmp_path / "verified.dxf"
    target.write_bytes(b"previous-good-verified-export")
    with pytest.raises(ValueError, match="COMPOSED_DXF_INVALID_FLAT_COORDINATE"):
        manufacturing_api.save_composed_panel_dxf(
            (("P1", _geometry(("box_body", source))),),
            target, pre_commit_guard=lambda: None, overwrite=True,
        )
    assert target.read_bytes() == b"previous-good-verified-export"


def test_quantity_summary_groups_only_identical_physical_holes_and_keeps_cutting(tmp_path):
    same_a = _flat("door", width=90.0, hole=True)
    same_b = _flat("door", width=90.0, hole=True)
    different_holes = _flat("door", width=90.0, hole=False)
    panels = (
        ("P1", _geometry(("door", same_a))),
        ("P2", _geometry(("door", same_b))),
        ("P3", _geometry(("door", different_holes))),
    )
    output = tmp_path / "grouped-receiving.dxf"
    receipts = manufacturing_api.save_composed_panel_dxf(
        panels, output, pre_commit_guard=lambda: None, quantity_summary=True,
    )
    assert len(receipts.sheets) == 3
    reopened = ezdxf.readfile(output)
    assert not reopened.audit().errors
    labels = [
        (entity.plain_text(), entity.dxf.layer)
        for entity in reopened.modelspace()
        if entity.dxftype() == "MTEXT"
    ]
    assert ("總計：3片；同板件同孔位 2 種", "CHECK") in labels
    assert ("door（式樣1） × 2：P1, P2", "CHECK") in labels
    assert ("door（式樣2） × 1：P3", "CHECK") in labels
    # No source CUTTING/holes may be lost, merged, or newly manufactured.
    assert sum(entity.dxf.layer == "CUTTING" and entity.dxftype() == "CIRCLE"
               for entity in reopened.modelspace()) == 2
    assert sum(entity.dxf.layer == "CUTTING" and entity.dxftype() == "LWPOLYLINE"
               for entity in reopened.modelspace()) == 3
    assert [label for label, layer in labels if layer == "CHECK"].count("door") == 3


def test_quantity_summary_rejects_non_boolean_without_writing(tmp_path):
    output = tmp_path / "invalid.dxf"
    with pytest.raises(TypeError, match="QUANTITY_SUMMARY_FLAG_MUST_BE_BOOL"):
        manufacturing_api.save_composed_panel_dxf(
            (("P1", _geometry(("door", _flat("door")))),),
            output, pre_commit_guard=lambda: None, quantity_summary="yes",
        )
    assert not output.exists()
