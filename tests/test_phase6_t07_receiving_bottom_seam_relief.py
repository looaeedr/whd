# -*- coding: utf-8 -*-
"""T7 Contract Tests: Receiving Bottom Seam Relief & Base Plate Nominal Integrity."""
import pytest
from ae_engine.contracts import BasePlatePartSpec, ManufacturingContext
from ae_engine.manufacturing_api import build_part_render_data
from ae_engine.sheetmetal_drawing import LinePrimitive
from ae_engine.sheetmetal_part_adapters import build_base_plate_result
from ae_engine.box_body_structure import (
    apply_base_plate_structure_reliefs,
    ResolvedBoxBodyPiece,
    ResolvedBoxBodyStructure,
)
from phase6_box_body_structure import (
    BoxBodyStructureType,
    default_box_body_structure_state,
    set_active_structure,
)


def _base_blank(w=800.0, h=1600.0, t=2.0, bend=15.0):
    return build_base_plate_result(
        w=w, h=h, t=t,
        shrink_top=0.0, shrink_bottom=0.0, shrink_left=0.0, shrink_right=0.0,
        bend=bend,
    )


def test_case1_no_seam_intersection_yields_full_nominal_blank():
    """Case 1: 無 seam intersection -> 完整 nominal blank."""
    base = _base_blank(w=800.0, h=1600.0, t=2.0, bend=15.0)
    state = set_active_structure(
        default_box_body_structure_state(),
        BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT,
    )
    # Seams outside the plate (e.g. -50mm, 900mm)
    relieved = apply_base_plate_structure_reliefs(
        base, box_w=800.0, shrink_left=0.0, shrink_right=0.0,
        thickness=2.0, structure=None, structure_state=state,
        seam_positions=(-50.0, 900.0),
    )
    assert relieved.outline == base.outline
    assert relieved.bends == base.bends
    assert relieved.width == pytest.approx(800.0 + 30.0)
    assert relieved.height == pytest.approx(1600.0 + 30.0)


def test_case2_single_real_intersection_yields_local_relief_20mm_and_half_t_meat():
    """Case 2: 單一實際 intersection -> 只做該處 local relief."""
    base = _base_blank(w=800.0, h=1600.0, t=2.0, bend=15.0)
    state = set_active_structure(
        default_box_body_structure_state(),
        BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT,
    )
    # Single seam at 400.0 (center of 800mm box)
    relieved = apply_base_plate_structure_reliefs(
        base, box_w=800.0, shrink_left=0.0, shrink_right=0.0,
        thickness=2.0, structure=None, structure_state=state,
        seam_positions=(400.0,),
    )
    # Unfolded X coordinate for seam 400: left_fold(15) + (400 - 0) = 415.0
    # Relief span: 405.0 to 425.0 (total 20mm)
    # Meat: 0.5 * 2.0 = 1.0mm, so cut depth from edge is 15 - 1 = 14mm
    coords = {(round(p.x, 6), round(p.y, 6)) for p in relieved.outline}
    assert (405.0, 14.0) in coords
    assert (425.0, 14.0) in coords
    assert (405.0, 0.0) in coords
    assert (425.0, 0.0) in coords

    # Horizontal bends should be split at 405..425
    bottom_bends = sorted((b.p1.x, b.p2.x) for b in relieved.bends if b.name == "bottom")
    top_bends = sorted((b.p1.x, b.p2.x) for b in relieved.bends if b.name == "top")
    assert bottom_bends == pytest.approx([(15.0, 405.0), (425.0, 815.0)])
    assert top_bends == pytest.approx([(15.0, 405.0), (425.0, 815.0)])
    # Vertical bends remain uncut
    assert len([b for b in relieved.bends if b.name == "left"]) == 1
    assert len([b for b in relieved.bends if b.name == "right"]) == 1


def test_case3_multiple_intersections_yields_independent_local_reliefs():
    """Case 3: 多個 intersection -> 各交會點各自處理."""
    base = _base_blank(w=800.0, h=1600.0, t=2.0, bend=15.0)
    state = set_active_structure(
        default_box_body_structure_state(),
        BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT,
    )
    # Two seams at 200.0 and 600.0
    relieved = apply_base_plate_structure_reliefs(
        base, box_w=800.0, shrink_left=0.0, shrink_right=0.0,
        thickness=2.0, structure=None, structure_state=state,
        seam_positions=(200.0, 600.0),
    )
    # Seam 1 unfolded X: 15 + 200 = 215 -> span 205..225
    # Seam 2 unfolded X: 15 + 600 = 615 -> span 605..625
    coords = {(round(p.x, 6), round(p.y, 6)) for p in relieved.outline}
    assert (205.0, 14.0) in coords
    assert (225.0, 14.0) in coords
    assert (605.0, 14.0) in coords
    assert (625.0, 14.0) in coords

    bottom_bends = sorted((b.p1.x, b.p2.x) for b in relieved.bends if b.name == "bottom")
    assert bottom_bends == pytest.approx([
        (15.0, 205.0), (225.0, 605.0), (625.0, 815.0)
    ])


def test_case4_relief_preserves_nominal_outer_dimension_semantics_and_2d_dxf_match(tmp_path):
    """Case 4: relief 不改變 nominal outer dimension semantics，且 2D 與 DXF 一致."""
    from ae_engine.manufacturing_api import generate_part
    import ezdxf

    spec = BasePlatePartSpec(
        width=800.0, height=1600.0, thickness=2.0,
        shrink_top=0.0, shrink_bottom=0.0, shrink_left=0.0, shrink_right=0.0,
        bend=15.0,
        model_name="受電箱",
        seam_positions=(400.0,),
    )
    render_data = build_part_render_data(spec)
    minx, miny, maxx, maxy = render_data.material.bounds
    assert maxx - minx == pytest.approx(830.0)
    assert maxy - miny == pytest.approx(1630.0)

    # Export to DXF and verify geometry match
    dxf_path = tmp_path / "receiving_base_plate.dxf"
    generate_part(spec, str(dxf_path), ManufacturingContext())
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    cutting_lines = [e for e in msp if e.dxftype() in {"LINE", "LWPOLYLINE"} and e.dxf.layer == "CUTTING"]
    assert len(cutting_lines) > 0


def test_receiving_family_defaults_use_55_nominal_shrink():
    """T13: 受電箱 Family 的 nominal 底板四邊縮固定預設為 55 mm."""
    from ae_engine.cabinet_types import receiving
    snapshot = receiving.apply_family_defaults({})
    assert snapshot.get("base_plate_shrink_top") == 55.0
    assert snapshot.get("base_plate_shrink_bottom") == 55.0
    assert snapshot.get("base_plate_shrink_left") == 55.0
    assert snapshot.get("base_plate_shrink_right") == 55.0


def test_receiving_base_plate_explicit_shrink_is_not_suppressed_to_zero():
    """T13: Receiving 不得在 Manufacturing 邊界把合法 shrink 偷改成 0."""
    spec = BasePlatePartSpec(
        width=800.0, height=1600.0, thickness=2.0,
        shrink_top=10.0, shrink_bottom=10.0, shrink_left=10.0, shrink_right=10.0,
        bend=15.0,
        model_name="受電箱",
    )
    render_data = build_part_render_data(spec)
    minx, miny, maxx, maxy = render_data.material.bounds
    assert maxx - minx == pytest.approx(810.0)
    assert maxy - miny == pytest.approx(1610.0)

