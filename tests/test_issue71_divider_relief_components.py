# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

import fold_designer_bridge as bridge
from ae_engine.assembly_collision import (
    _divider_front_fold_segments,
    build_divider_front_fold_relief_candidate,
    project_joint_interference_to_relief_owner,
)
from tests.test_issue39_divider_relief import (
    _body_part,
    _divider_insert_joint,
    _divider_part,
    _snapshot,
    _source_fold_bands,
)


def _non_axis_aligned_edges(geometry, *, tolerance=1.0e-5):
    """Return manufacturing edges that are neither parallel to X nor Y."""
    rows = []
    geoms = [geometry] if getattr(geometry, "geom_type", "") == "Polygon" else list(
        getattr(geometry, "geoms", ()) or ()
    )
    for geom in geoms:
        if getattr(geom, "geom_type", "") != "Polygon":
            continue
        rings = [geom.exterior, *tuple(geom.interiors)]
        for ring in rings:
            coords = list(ring.coords)
            for a, b in zip(coords, coords[1:]):
                dx = abs(float(b[0]) - float(a[0]))
                dy = abs(float(b[1]) - float(a[1]))
                if dx > tolerance and dy > tolerance:
                    rows.append(((float(a[0]), float(a[1])), (float(b[0]), float(b[1]))))
    return tuple(rows)


def _physical_depth_from_projection(front_segments, material):
    """Test-only observation of physical skin penetration at the touched span end."""
    minx, miny, maxx, maxy = map(float, material.bounds)
    points = [
        (float(point[0]), float(point[1]))
        for segment in tuple(front_segments or ())
        for point in segment
    ]
    assert points
    low_depth = max(0.0, max(y for _x, y in points) - miny)
    high_depth = max(0.0, maxy - min(y for _x, y in points))
    if low_depth <= high_depth:
        return "MIN_Y", low_depth
    return "MAX_Y", high_depth


@pytest.mark.parametrize("source_key", ("box_body:left_side", "box_body:right_side"))
def test_issue71_divider_standard_relief_never_promotes_triangulation_diagonal_to_cutting(source_key):
    """STANDARD topology comes from Fold semantics; collision supplies physical depth.

    No measured fixture dimension is sent into production.  The RED only checks
    that the resolved candidate obeys the project's manufacturing invariant:
    triangulation vertices may not invent a diagonal STANDARD cutting edge.
    """
    snap = _snapshot()
    body = _body_part(snap)
    divider, divider_part = _divider_part(snap)
    world = bridge._phase6_build_joint_world_geometry(
        (body, divider_part), (snap["w"], snap["h"], snap["d"]), snap["t"]
    )
    joint = _divider_insert_joint(divider.stable_id)
    material = world["flat_material_by_part"][divider.stable_id]
    core_start = float(
        divider_part.render_data.metadata["physical_geometry_contract"]
        ["core_physical_segment"]["flat_band"][0]
    )

    projected = project_joint_interference_to_relief_owner(
        joint,
        world_triangles_by_part=world["world_triangles_by_part"],
        mapped_skin_triangles_by_part=world["mapped_skin_triangles_by_part"],
        flat_material_by_part=world["flat_material_by_part"],
        source_geometry_key=source_key,
    )
    front = _divider_front_fold_segments(
        projected.projection, core_start=core_start
    )
    edge, skin_depth = _physical_depth_from_projection(front, material)

    candidate = build_divider_front_fold_relief_candidate(
        joint,
        world_triangles_by_part=world["world_triangles_by_part"],
        mapped_skin_triangles_by_part=world["mapped_skin_triangles_by_part"],
        flat_material_by_part=world["flat_material_by_part"],
        core_start=core_start,
        source_geometry_keys=(source_key,),
        source_fold_bands_by_key=_source_fold_bands(body),
        clearance=0.0,
        sheet_thickness=float(divider.thickness),
    )
    assert candidate is not None
    physical_cut = candidate.cut_polygon_2d.intersection(material)
    evidence = dict(candidate.evidence or {})
    source_evidence = dict(dict(evidence.get("projection_by_source") or {}).get(source_key) or {})

    print("ISSUE71_STANDARD_TOPOLOGY_RED=", {
        "source": source_key,
        "core_start_evidence_only": core_start,
        "penetrating_bands": source_evidence.get("penetrating_bands"),
        "retained_contact_bands": source_evidence.get("retained_contact_bands"),
        "cut_bounds": tuple(map(float, physical_cut.bounds)),
        "non_axis_edges": _non_axis_aligned_edges(physical_cut),
        "evidence": evidence,
    })

    # Issue74 refined the authority boundary: core_start is a Divider Fold datum,
    # not the legality boundary for side-piece true-thickness penetration.
    # Source Fold-band identity owns stage provenance; physical both-skin
    # backprojection owns required extent. Validation never feeds measured
    # fixture dimensions back into production.
    assert evidence.get("classification") == "SOURCE_FOLD_BAND_TRUE_THICKNESS"
    assert source_evidence.get("manufacturing_topology") == (
        "STANDARD_PLUS_SOURCE_FOLD_BAND_ORTHOGONAL"
    )
    assert tuple(source_evidence.get("penetrating_bands") or ())
    assert tuple(source_evidence.get("retained_contact_bands") or ())

    # The original Issue71 regression remains guarded: triangulation vertices
    # may not create diagonal manufacturing CUTTING edges, even when Issue74
    # adds source-Fold-derived orthogonal stages beyond core_start.
    assert _non_axis_aligned_edges(physical_cut) == (), (
        "Divider STANDARD relief contains a triangulation-generated diagonal; "
        "physical backprojection may determine required side/depth but may not "
        "invent manufacturing CUTTING topology",
        source_key,
        _non_axis_aligned_edges(physical_cut),
    )
