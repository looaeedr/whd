# -*- coding: utf-8 -*-
from shapely.geometry import box
from ae_engine.manufacturing_api import (
    MaterialSegment, UnfoldedBlankTopology, PartRenderData, measure_unfolded_blanks,
)


def _topology():
    return UnfoldedBlankTopology(
        piece_id="head",
        x_segments=(MaterialSegment("X", "left", 15, "fold_profile"), MaterialSegment("X", "core", 100, "fold_profile")),
        y_segments=(MaterialSegment("Y", "top", 16, "fold_profile"), MaterialSegment("Y", "core", 50, "fold_profile")),
        source="fold_profile", revision=1,
    )


def test_local_relief_changes_area_not_blank_envelope_when_topology_is_same():
    topo = _topology()
    full = PartRenderData(scene=object(), material=box(0, 0, 115, 66), unfolded_topology=topo)
    cut = PartRenderData(scene=object(), material=box(0, 0, 115, 66).difference(box(105, 56, 115, 66)), unfolded_topology=topo)
    a = measure_unfolded_blanks(full, part_key="head")[0]
    b = measure_unfolded_blanks(cut, part_key="head")[0]
    assert (a.width, a.height) == (b.width, b.height) == (115.0, 66.0)
    assert a.area != b.area
    assert a.topology_fingerprint == b.topology_fingerprint
    assert a.material_bounds == b.material_bounds == (0.0, 0.0, 115.0, 66.0)
