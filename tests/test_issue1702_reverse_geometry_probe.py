# -*- coding: utf-8 -*-
"""Temporary independent inverse-geometry inspection (#1702).

The probe imports NO certified formula or DXF oracle into the inverse solver.
It deliberately emits a failing test containing its complete numeric witness
so GitHub Actions preserves the captured output for review.
"""
from __future__ import annotations

import json
import pytest
from shapely.ops import unary_union

from ae_engine.assembly_collision import build_divider_front_fold_relief_candidate
from ae_engine.divider_manufacturing import _core_start
from ae_engine.divider_reverse_relief import reconstruct_receiving_divider_cross
from tests.test_issue39_divider_relief import (
    _snapshot, _body_part, _divider_part, _divider_insert_joint,
)
from tests.test_issue74_divider_side_front_penetration import _piece_bands
import fold_designer_bridge as bridge


def _rounded_bounds(poly):
    return tuple(round(float(v), 6) for v in poly.bounds)


def test_issue1702_independent_full_thickness_reverse_cut_probe():
    snap = _snapshot()
    body = _body_part(snap)
    divider, part = _divider_part(snap)
    dims = (snap["w"], snap["h"], snap["d"])
    world = bridge._phase6_build_joint_world_geometry((body, part), dims, snap["t"])
    candidate = build_divider_front_fold_relief_candidate(
        _divider_insert_joint(divider.stable_id),
        world_triangles_by_part=world["world_triangles_by_part"],
        mapped_skin_triangles_by_part=world["mapped_skin_triangles_by_part"],
        flat_material_by_part=world["flat_material_by_part"],
        core_start=_core_start(part),
        source_geometry_keys=("box_body:left_side", "box_body:right_side"),
        source_fold_bands_by_key=_piece_bands(body),
        clearance=0.0,
        sheet_thickness=snap["t"],
    )
    assert candidate is not None, "Full-thickness reverse solver returned no candidate"
    minx, miny, maxx, maxy = map(float, part.render_data.material.bounds)
    probes = []
    for source, evidence in candidate.evidence["projection_by_source"].items():
        stages = {}
        for key, raw in evidence["physical_stages"].items():
            stages[key] = {
                "role": raw.get("role"),
                "edge": raw.get("edge"),
                "fw_contact_bounds": raw.get("fw_contact_bounds"),
                "primary_cutting_depth": raw.get("primary_cutting_depth"),
                "source_solid_footprint_bounds": raw.get("source_solid_footprint_bounds"),
                "stage_u_span": raw.get("stage_u_span"),
                "stage_v_span": raw.get("stage_v_span"),
                "cut_bounds": raw.get("cut_bounds"),
            }
        probes.append({
            "source": source,
            "penetrating_bands": evidence["penetrating_bands"],
            "contact_bands": evidence["retained_contact_bands"],
            "physical_stages": stages,
        })
    # This is separate evidence only, not an input to the reverse solver.
    solved_parts, diagnostics, _joints = bridge._phase6_resolve_family_divider_reliefs(
        (body, part), finished_dimensions=dims,
        sheet_thickness=snap["t"], clearance=0.0,
    )
    solved = next(row for row in solved_parts if row.part_key == divider.stable_id)
    certified_removed = part.render_data.material.difference(solved.render_data.material)
    y0, y1 = float(part.render_data.material.bounds[1]), float(part.render_data.material.bounds[3])
    all_pieces = tuple(getattr(certified_removed, 'geoms', (certified_removed,)))
    end_pieces = tuple(g for g in all_pieces if float(g.area) > 0 and (float(g.bounds[1]) <= y0 + 1e-6 or float(g.bounds[3]) >= y1 - 1e-6))
    assert len(end_pieces) == 2, [(g.area, g.bounds) for g in all_pieces]
    certified_cross = unary_union(end_pieces)
    inverse = reconstruct_receiving_divider_cross(
        divider=part, box_body=body, candidate=candidate, thickness=snap["t"],
    )
    reverse_removed = inverse.cut_polygon_2d
    witness = {
        "input": {"W": snap["w"], "T": snap["t"], "FW": snap["fw"], "D": snap["d"]},
        "flat_blank_bounds": (minx, miny, maxx, maxy),
        "reverse_source": "PRE_RELIEF_TWO_SKIN_WORLD_CROSSINGS_TO_FLAT",
        "reverse_cut_bounds": _rounded_bounds(reverse_removed),
        "reverse_cut_area": float(reverse_removed.area),
        "collision_only_cut_depths_reported": candidate.cut_depths,
        "full_inverse_parameters": inverse.parameters,
        "full_inverse_evidence": inverse.evidence,
        "reverse_source_bands": probes,
        "certified_final_cut_bounds": _rounded_bounds(certified_removed),
        "certified_final_cut_area": float(certified_removed.area),
        "reverse_extra_area": float(reverse_removed.difference(certified_cross).area),
        "reverse_missing_area": float(certified_cross.difference(reverse_removed).area),
        "independent_non_cross_area": float(certified_removed.difference(certified_cross).area),
        "source_classification": candidate.evidence["classification"],
        "geometry_subsystem": candidate.evidence["manufacturing_dimensions_source"],
    }
    # Validate independent inverse and approved final material as complete
    # geometry; any discrepancy is reported with measured source-face evidence.
    assert float(reverse_removed.area) > 0.0
    assert (
        witness["reverse_extra_area"] <= 1e-4
        and witness["reverse_missing_area"] <= 1e-4
    ), "ISSUE1702_REVERSE_PROBE=" + json.dumps(witness, ensure_ascii=False, default=str)
