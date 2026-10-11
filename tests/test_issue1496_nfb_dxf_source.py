# -*- coding: utf-8 -*-
"""#1496 source-native DXF inventory: never invent main-hole centers or approval."""
from __future__ import annotations

from math import isclose

import ezdxf
import pytest

from ae_engine.receiving_nfb_dxf_source import (
    SOURCE_STATUS,
    circle_candidate_pivot,
    inspect_expected_nfb_sources,
    inspect_nfb_dxf_source,
    rotate_point_around_source_pivot,
)


def _source_dxf(tmp_path):
    """Two deliberately separated drawing groups: bbox midpoint is NOT pivot."""
    doc = ezdxf.new("R2010")
    doc.layers.new("BASE_CUT", dxfattribs={"color": 30})
    doc.layers.new("MIDDLE_CUT", dxfattribs={"color": 150})
    doc.layers.new("BASE_MARK", dxfattribs={"color": 212})
    m = doc.modelspace()
    upper = m.add_circle((100, 900), radius=11, dxfattribs={"layer": "BASE_CUT"})
    other = m.add_circle((1900, -200), radius=20, dxfattribs={"layer": "MIDDLE_CUT", "color": 30})
    curved = m.add_arc((70, 900), 8, 25, 140, dxfattribs={"layer": "MIDDLE_CUT"})
    outline = m.add_lwpolyline(
        [(60, 860, 0.0), (140, 860, 0.2), (140, 960, 0.0), (60, 960, 0.0)],
        format="xyb", close=True, dxfattribs={"layer": "BASE_MARK"},
    )
    block = doc.blocks.new("DUPLICATED_CUT")
    block.add_circle((0, 0), 3, dxfattribs={"layer": "0", "color": 0})
    m.add_blockref("DUPLICATED_CUT", (300, 1000), dxfattribs={"layer": "BASE_CUT", "color": 150})
    m.add_blockref("DUPLICATED_CUT", (700, -400), dxfattribs={"layer": "BASE_MARK", "color": 150})
    m.add_line((100, 800), (120, 810), dxfattribs={"layer": "BASE_CUT"})
    m.add_text("NOT CUTTING")
    path = tmp_path / "NFB source.dxf"
    doc.saveas(path)
    return path, upper.dxf.handle, other.dxf.handle, curved.dxf.handle, outline.dxf.handle


def test_true_source_identity_circle_vs_whole_document_bbox(tmp_path):
    path, upper_h, other_h, _arc_h, _poly_h = _source_dxf(tmp_path)
    inventory = inspect_nfb_dxf_source(path)
    assert inventory.status == SOURCE_STATUS
    assert inventory.source_id == f"NFB-DXF:{inventory.source_sha256}"
    assert inventory.main_hole_source_id is None
    assert inventory.approved_manufacturing_rule_revision is None
    assert inventory.entities
    ids = {e.handle_path: e.source_id for e in inventory.entities}
    assert circle_candidate_pivot(inventory, source_entity_id=ids[upper_h]) == (100.0, 900.0)
    assert circle_candidate_pivot(inventory, source_entity_id=ids[other_h]) == (1900.0, -200.0)
    # A global bbox center could never select either legitimate separate center.
    selected = circle_candidate_pivot(inventory, source_entity_id=ids[upper_h])
    assert selected != (1000.0, 350.0)
    assert inspect_nfb_dxf_source(path) == inventory
    with pytest.raises(ValueError, match="uniquely selected"):
        circle_candidate_pivot(inventory, source_entity_id="nonexistent")


def test_color_sources_preserve_entity_layer_and_block_inheritance(tmp_path):
    path, upper_h, other_h, arc_h, poly_h = _source_dxf(tmp_path)
    inv = inspect_nfb_dxf_source(path)
    by_handle = {e.handle_path: e for e in inv.entities}
    assert by_handle[upper_h].layer == "BASE_CUT"
    assert by_handle[upper_h].effective_color_aci == 30
    assert by_handle[upper_h].color_authority == "LAYER"
    assert by_handle[other_h].layer_color_aci == 150
    assert by_handle[other_h].effective_color_aci == 30
    assert by_handle[other_h].color_authority == "ENTITY"
    assert by_handle[arc_h].dxf_type == "ARC"
    assert by_handle[arc_h].center_xy == (70.0, 900.0)
    assert by_handle[arc_h].arc_angles == (25.0, 140.0)
    poly = by_handle[poly_h]
    assert poly.dxf_type == "LWPOLYLINE"
    assert poly.closed
    assert poly.bulges[1] == pytest.approx(0.2)  # cannot lose ARC bulge as straight line
    assert any("INSERT:" in e.group_id for e in inv.entities)
    inserted = [e for e in inv.entities if "INSERT:" in e.group_id]
    assert len(inserted) == 2
    assert {e.effective_color_aci for e in inserted} == {150}
    assert {e.color_authority for e in inserted} == {"BLOCK_INHERITED"}
    assert {tuple(round(v, 5) for v in e.center_xy) for e in inserted} == {
        (300.0, 1000.0), (700.0, -400.0),
    }
    color_counts = dict(inv.process_aci_entity_counts)
    assert color_counts[30] == 2
    assert color_counts[150] == 3  # 2 nested CIRCLE + 1 layer ARC
    assert color_counts[212] == 1
    assert sum(color_counts.values()) <= len(inv.entities)
    # Count is entity inventory, not total model / plate / manufacturable-hole count.
    assert inv.status != "MANUFACTURING_READY"


@pytest.mark.parametrize("angle", [0, 90, 180, 270])
def test_diagnostic_quarter_turns_preserve_explicit_pivot(angle):
    pivot = (100.0, 900.0)
    point = (112.0, 908.0)
    rotated = rotate_point_around_source_pivot(
        point, pivot_xy=pivot, rotation_deg=angle,
    )
    assert rotate_point_around_source_pivot(
        pivot, pivot_xy=pivot, rotation_deg=angle,
    ) == pivot
    assert rotated == {
        0: (112.0, 908.0),
        90: (92.0, 912.0),
        180: (88.0, 892.0),
        270: (108.0, 888.0),
    }[angle]
    reverse = rotate_point_around_source_pivot(
        rotated, pivot_xy=pivot, rotation_deg=(360 - angle) % 360,
    )
    assert reverse == point


def test_missing_source_is_unknown_not_zero(tmp_path):
    exists = tmp_path / "NFB.dxf"
    exists.write_text("placeholder", encoding="utf-8")
    missing = tmp_path / "UNAVAILABLE.dxf"
    assert inspect_expected_nfb_sources((exists, missing)) == (
        (str(exists), "SOURCE_PRESENT_NOT_CERTIFIED"),
        (str(missing), "SOURCE_MISSING_UNKNOWN"),
    )


def test_unsupported_not_silently_treated_as_certified(tmp_path):
    doc = ezdxf.new("R2010")
    doc.layers.new("MIDDLE", dxfattribs={"color": 150})
    doc.modelspace().add_ellipse((10, 20), (10, 0), 0.5,
                                 dxfattribs={"layer": "MIDDLE"})
    doc.modelspace().add_line((0, 0), (1, 0), dxfattribs={"layer": "MIDDLE"})
    p = tmp_path / "unsupported.dxf"
    doc.saveas(p)
    inv = inspect_nfb_dxf_source(p)
    assert any("UNSUPPORTED:ELLIPSE" in note for note in inv.diagnostics)
    assert len(inv.entities) == 1
    assert inv.main_hole_source_id is None
    assert inv.approved_manufacturing_rule_revision is None


@pytest.mark.parametrize("angle", [-90, 30, 360, True])
def test_invalid_rotation_is_refused(angle):
    with pytest.raises(ValueError, match="0/90/180/270"):
        rotate_point_around_source_pivot(
            (1, 2), pivot_xy=(0, 0), rotation_deg=angle,
        )
