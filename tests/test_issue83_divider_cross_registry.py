# -*- coding: utf-8 -*-
import pytest

from ae_engine.certified_relief_registry import (
    evaluate_divider_cross_formula_record,
    lookup_certified_divider_cross_relief,
)
from ae_engine.sheetmetal_geometry import (
    CornerTypeId,
    CornerTypeSelection,
    CrossCornerMode,
    placed_corner_cut_polygons,
    resolve_corner_relief,
)


def _receiving_reference_variables():
    return {
        "T": 2.0,
        "core_start": 41.0,
        "divider_first_outside": 18.0,
        "divider_fw_outside": 29.0,
        "divider_fw_material": 25.0,
        "divider_last_outside": 17.0,
        "box_zl1_formed": 24.0,
    }


def test_cross_slot_parameters_keep_fold_u_fold_v_as_primary_basis():
    selection = CornerTypeSelection(
        CornerTypeId.CROSS,
        cross_mode=CrossCornerMode.STANDARD,
        slot_width=7.0,
        slot_straight_depth=24.0,
        slot_radius=3.5,
    )
    relief = resolve_corner_relief(
        selection,
        fold_u=66.0,
        fold_v=27.0,
        thickness=2.0,
        fw=25.0,
    )
    assert relief.primary_u == pytest.approx(66.0)
    assert relief.primary_v == pytest.approx(27.0)
    assert relief.slot_width == pytest.approx(7.0)
    assert relief.slot_straight_depth == pytest.approx(24.0)
    assert relief.slot_radius == pytest.approx(3.5)


def test_cross_slot_geometry_matches_normalized_divider_dxf_local_shape():
    selection = CornerTypeSelection(
        CornerTypeId.CROSS,
        cross_mode=CrossCornerMode.STANDARD,
        slot_width=7.0,
        slot_straight_depth=24.0,
        slot_radius=3.5,
    )
    relief = resolve_corner_relief(
        selection, fold_u=66.0, fold_v=27.0, thickness=2.0, fw=25.0,
    )
    cut = placed_corner_cut_polygons(
        corner_name="bottom_left", relief=relief, width=158.0, height=596.0,
    )
    merged = cut[0]
    for item in cut[1:]:
        merged = merged.union(item)
    minx, miny, maxx, maxy = merged.bounds
    assert (minx, miny) == pytest.approx((0.0, 0.0))
    assert maxx == pytest.approx(66.0)
    # primary 27 + straight 24 + R3.5 rounded cap
    assert maxy == pytest.approx(54.5)


def test_receiving_divider_registry_formula_derives_dxf_values_from_parameters():
    record = {
        "formula": {
            "min_y_fold_u": "core_start + divider_last_outside + T",
            "max_y_fold_u": "core_start + divider_fw_material",
            "fold_v": "divider_fw_outside - T",
            "slot_width": "divider_fw_material - divider_first_outside",
            "slot_straight_depth": "box_zl1_formed",
            "slot_radius": "(divider_fw_material - divider_first_outside) / 2",
        }
    }
    values = evaluate_divider_cross_formula_record(record, _receiving_reference_variables())
    assert values == pytest.approx({
        "min_y_fold_u": 60.0,
        "max_y_fold_u": 66.0,
        "fold_v": 27.0,
        "slot_width": 7.0,
        "slot_straight_depth": 24.0,
        "slot_radius": 3.5,
    })


def test_receiving_divider_registry_hit_is_cross_plus_parameters():
    result = lookup_certified_divider_cross_relief(
        cabinet_family="受電箱",
        variables=_receiving_reference_variables(),
    )
    assert result is not None
    assert result.rule.rule_id == "RECEIVING_DIVIDER_CROSS_STANDARD_V1"
    assert result.rule.corner_type == "CROSS"
    assert result.min_y.primary_u == pytest.approx(60.0)
    assert result.min_y.primary_v == pytest.approx(27.0)
    assert result.min_y.slot_width is None
    assert result.min_y.slot_straight_depth is None
    assert result.min_y.slot_radius is None
    assert result.max_y.primary_u == pytest.approx(66.0)
    assert result.max_y.primary_v == pytest.approx(27.0)
    assert result.max_y.slot_width == pytest.approx(7.0)
    assert result.max_y.slot_straight_depth == pytest.approx(24.0)
    assert result.max_y.slot_radius == pytest.approx(3.5)

def _read_normalized_divider_dxf_relief():
    from pathlib import Path
    import ezdxf
    from ezdxf import bbox as ezdxf_bbox

    path = Path(__file__).resolve().parents[1] / "基準檔" / "金庫型" / "中隔.dxf"
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    ext = ezdxf_bbox.extents(msp)
    assert ext.has_data
    minx, miny = float(ext.extmin.x), float(ext.extmin.y)
    maxx, maxy = float(ext.extmax.x), float(ext.extmax.y)

    lines = list(msp.query("LINE"))
    arcs = list(msp.query("ARC"))
    assert len(arcs) == 1
    arc = arcs[0]

    def vertical_at(x):
        rows = []
        for entity in lines:
            a, b = entity.dxf.start, entity.dxf.end
            if abs(float(a.x) - float(b.x)) <= 1e-8 and abs(float(a.x) - x) <= 1e-8:
                rows.append((min(float(a.y), float(b.y)), max(float(a.y), float(b.y))))
        return rows

    # Existing production rigid mapping is clockwise 90 degrees:
    # source max-X -> Divider min-Y, source min-X -> Divider max-Y.
    source_min_x_edge = vertical_at(minx)
    source_max_x_edge = vertical_at(maxx)
    assert source_min_x_edge and source_max_x_edge
    min_y_fold_u = min(row[0] for row in source_max_x_edge) - miny
    max_y_fold_u = min(row[0] for row in source_min_x_edge) - miny

    bottom_verticals = []
    for entity in lines:
        a, b = entity.dxf.start, entity.dxf.end
        if abs(float(a.x) - float(b.x)) > 1e-8:
            continue
        lo = min(float(a.y), float(b.y))
        if abs(lo - miny) > 1e-8:
            continue
        x = float(a.x)
        if minx + 1e-8 < x < maxx - 1e-8:
            bottom_verticals.append(x)
    assert bottom_verticals
    fold_v = min(min(x - minx, maxx - x) for x in bottom_verticals)

    radius = float(arc.dxf.radius)
    slot_width = 2.0 * radius
    slot_straight_depth = (float(arc.dxf.center.x) - minx) - fold_v
    return {
        "blank_u": maxy - miny,
        "reference_span": maxx - minx,
        "min_y_fold_u": min_y_fold_u,
        "max_y_fold_u": max_y_fold_u,
        "fold_v": fold_v,
        "slot_width": slot_width,
        "slot_straight_depth": slot_straight_depth,
        "slot_radius": radius,
    }


def test_registry_parameters_match_actual_divider_dxf_after_existing_rigid_mapping():
    dxf = _read_normalized_divider_dxf_relief()
    result = lookup_certified_divider_cross_relief(
        cabinet_family="受電箱",
        variables=_receiving_reference_variables(),
    )
    assert result is not None
    values = dict(result.geometry_evidence["formula_values"])

    assert dxf["blank_u"] == pytest.approx(158.0)
    assert dxf["reference_span"] == pytest.approx(596.0)
    assert values["min_y_fold_u"] == pytest.approx(dxf["min_y_fold_u"])
    assert values["max_y_fold_u"] == pytest.approx(dxf["max_y_fold_u"])
    assert values["fold_v"] == pytest.approx(dxf["fold_v"])
    assert values["slot_width"] == pytest.approx(dxf["slot_width"])
    assert values["slot_straight_depth"] == pytest.approx(dxf["slot_straight_depth"])
    assert values["slot_radius"] == pytest.approx(dxf["slot_radius"])


def test_receiving_production_resolver_uses_certified_cross_registry_not_collision_dimensions():
    import fold_designer_bridge as bridge
    from tests.test_issue39_divider_relief import _snapshot, _body_part, _divider_part

    snap = _snapshot()
    body = _body_part(snap)
    divider, divider_part = _divider_part(snap)
    solved_parts, diagnostics, _joints = bridge._phase6_resolve_family_divider_reliefs(
        (body, divider_part),
        finished_dimensions=(snap["w"], snap["h"], snap["d"]),
        sheet_thickness=snap["t"],
        clearance=0.0,
    )
    solved = next(part for part in solved_parts if part.part_key == divider.stable_id)
    relief = dict(solved.render_data.metadata["divider_assembly_relief"])
    evidence = dict(relief["evidence"])
    formula = dict(evidence["formula_values"])

    assert relief["verified"] is True
    assert relief["trust_level"] == "CERTIFIED"
    assert relief["rule_id"] == "RECEIVING_DIVIDER_CROSS_STANDARD_V1"
    assert relief["corner_type"] == "CROSS"
    assert evidence["manufacturing_dimensions_source"] == "CERTIFIED_REGISTRY_CROSS_PARAMETERS"
    assert formula["min_y_fold_u"] == pytest.approx(60.0)
    assert formula["max_y_fold_u"] == pytest.approx(66.0)
    assert formula["fold_v"] == pytest.approx(27.0)
    assert formula["slot_width"] == pytest.approx(7.0)
    assert formula["slot_straight_depth"] == pytest.approx(24.0)
    assert formula["slot_radius"] == pytest.approx(3.5)
    assert diagnostics and diagnostics[0].illegal_penetration is False

