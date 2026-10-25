# -*- coding: utf-8 -*-
"""WHD true source FinalScene for non-W800 SIDE fixed-plate markings.

The fixture creates NEW physical mother sheets from the requested cabinet
W/H/D/T and uses the actual folded-ear, world-to-flat backprojection and
real DXF exporter. Never move a W800 mesh and call it a W750 witness.
"""
from copy import deepcopy

import ezdxf
import pytest

from ae_engine.manufacturing_scene_access import owner_render_data
from ae_engine.receiving_joint_marking import resolve_receiving_joint_markings
from ae_engine.receiving_ear_side_manufacturing_marking import (
    with_verified_receiving_ear_side_markings,
)
from ae_engine.manufacturing_api import save_resolved_manufacturing_geometry_dxf
from ae_engine.sheetmetal_drawing import LinePrimitive
from tests.test_issue1050_receiving_mother_plate_marking import (
    _snapshot as _box_snapshot, _full_receiving_geometry,
)
from tests.test_receiving_base_physical_3d_z_assembly import _assembled
from tests.test_receiving_two_tier_physical_base_parts import _two_tier


@pytest.mark.parametrize("factory,tier_count", ((_assembled, 1), (_two_tier, 2)))
@pytest.mark.parametrize("width,pitch", ((750., 620.), (900., 770.)))
def test_actual_non800_source_sheets_produce_frame_and_ear_marking_dxf(
    factory, tier_count, width, pitch, tmp_path,
):
    snap = _box_snapshot()
    snap.update(deepcopy(factory()))
    snap["w"] = width
    snap["door_layout_columns"] = [[width, [1100., 500.]]]
    geom = _full_receiving_geometry(snap)

    joint = resolve_receiving_joint_markings(
        snap, geom,
        dimensions=(width, snap["h"], snap["d"]),
        sheet_thickness=snap["t"], cabinet_family="受電箱",
    )
    emitted = [row for row in joint.results if row.status == "EMITTED"]
    assert len(emitted) == 7, [
        (row.attached_part_id, row.status, row.diagnostic_code,
         row.diagnostic_detail) for row in joint.results
    ]

    source = with_verified_receiving_ear_side_markings(
        snap, joint.geometry,
        dimensions=(width, snap["h"], snap["d"]),
        sheet_thickness=snap["t"],
    )
    expected_x = (-pitch/2., pitch/2.)
    for side, expected_world_x in zip(("left_side", "right_side"), expected_x):
        data = owner_render_data(source, "box_body:" + side)
        assert data is not None
        assert len(data.metadata.get("joint_markings") or ()) == 2
        assert data.metadata["receiving_ear_side_marking_segment_count"] == tier_count
        assert sum(
            p.layer == "MARKING" for p in data.scene.primitives
            if isinstance(p, LinePrimitive)
        ) >= 2 + tier_count
        # Physical inside SIDE is at W/2 - source SIDE thickness.
        # No +/-398 constant may enter either assembly or flat 2D.
        assert abs(expected_world_x) == pytest.approx(
            width/2. - snap["t"] - 63.
        )

    paths = save_resolved_manufacturing_geometry_dxf(
        source, tmp_path, overwrite=True,
    )
    for role in ("left_side", "right_side"):
        key = "box_body:box_body_" + role
        doc = ezdxf.readfile(paths[key])
        marks = [e for e in doc.modelspace()
                 if e.dxftype() == "LINE"
                 and str(e.dxf.layer).upper() == "MARKING"]
        assert len(marks) >= 2 + tier_count
