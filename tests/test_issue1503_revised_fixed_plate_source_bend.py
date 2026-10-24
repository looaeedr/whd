# -*- coding: utf-8 -*-
"""User-uploaded 2026-10-18 固定片.dxf source BEND and CUTTING measured facts.

This fixture measures the REAL uploaded DXF entity positions independently of
the WHD policy implementation. Physical weld and signed forming are separate.
"""
import pytest

from ae_engine.manufacturing_render_data import fold_guides_from_final_scene
from ae_engine.receiving_base_fixing_plate_geometry import (
    LARGE_PATTERN, SMALL_PATTERN, SOURCE_DXF_SHA256,
    build_fixing_plate_source_render_data,
)
from ae_engine.receiving_weld_ear_policy import (
    resolve_receiving_large_weld_ear_fit,
)
from ae_engine.sheetmetal_drawing import LinePrimitive, PolylinePrimitive

# Measured from uploaded DXF (mm), not reverse-calculated from policy.
FILE_SHA256 = "dd123595e384b7ce6bf4c444b5af23a11e559de2a715c40ce5d89e2552167cbe"
SOURCE_FACTS = {
    "large": {
        "part": "base_plate:fixing_plate:left",
        "size": (256., 105.), "t": 2.,
        "slot_xy": ((23., 84.), (58., 84.), (198., 84.), (233., 84.)),
        "bend": (0., 23., 256., 23.),
        "cuts": 5, "slot_size": (25., 11.),
    },
    "small": {
        "part": "base_plate:fixing_plate:small_source",
        "size": (90., 90.), "t": 2.,
        "slot_xy": ((25., 69.), (65., 69.)),
        "bend": (0., 23., 90., 23.),
        "cuts": 3, "slot_size": (30., 11.),
    },
}


@pytest.mark.parametrize("kind", ("large", "small"))
def test_current_uploaded_fixed_plate_has_real_bend_line_and_moved_holes(kind):
    from ae_engine.receiving_base_fixing_plate_geometry import source_pattern
    facts = SOURCE_FACTS[kind]
    pattern = source_pattern(kind)
    part = build_fixing_plate_source_render_data(
        facts["part"], source_kind=kind,
    )
    assert SOURCE_DXF_SHA256 == FILE_SHA256
    assert part.metadata["source_dxf_sha256"] == FILE_SHA256
    assert pattern.slot_centers == facts["slot_xy"]
    assert (pattern.width, pattern.height) == facts["size"]
    assert pattern.thickness == facts["t"] == part.metadata["thickness"]
    assert pattern.corner_radius == 0.0  # outer CUTTING native polyline no bulge
    assert (pattern.slot_length, pattern.slot_width) == facts["slot_size"]
    assert part.metadata["source_bend_verified"] is True
    assert part.metadata["source_bend_line_mm"] == 23.0
    assert part.metadata["source_bend_rule"] == "21+EAR_T"
    assert part.metadata["source_derived_formed_hole_center_mm"] == (63.0 if kind == "large" else 48.0)
    assert part.metadata["factory_bend_compensation_required"] is False
    lines = [p for p in part.scene.primitives
             if isinstance(p, LinePrimitive) and p.layer == "BEND"]
    assert len(lines) == 1
    line = lines[0]
    assert (
        line.p1.x, line.p1.y, line.p2.x, line.p2.y,
    ) == facts["bend"]
    assert len(part.fold_guides) == 1
    assert part.fold_guides == fold_guides_from_final_scene(part.scene)
    assert part.fold_guides[0].axis == "y"
    assert part.fold_guides[0].position == 23.
    assert part.fold_guides[0].span_start == 0.
    assert part.fold_guides[0].span_end == facts["size"][0]
    cutting = [p for p in part.scene.primitives
               if isinstance(p, PolylinePrimitive)
               and p.layer == "CUTTING" and p.closed]
    assert len(cutting) == facts["cuts"]
    # Source bend is now verified; do not fake an unobserved signed rotation.
    assert part.metadata["formed_direction_verified"] is False
    assert part.metadata["formed_geometry_verified"] is False
    assert part.metadata["weld_z_verified"] is False
    assert part.metadata["manufacturing_ready"] is False


@pytest.mark.parametrize("pitch,pair", ((210., (0, 3)), (140., (1, 2))))
def test_revised_ear_bend_t2_closes_63mm_inside_skin_and_670mm_pitch(pitch,pair):
    fit = resolve_receiving_large_weld_ear_fit(
        box_outer_width_mm=800., box_side_thickness_mm=2.,
        fixing_hole_pitch_x_mm=670., fixing_hole_pitch_y_mm=pitch,
    )
    assert fit.ear_weld_edge_to_hole_center_mm == 84.
    assert fit.ear_thickness_mm == 2.
    assert fit.nominal_fold_from_weld_edge_mm == 23.
    assert (fit.ear_weld_edge_to_hole_center_mm -
            fit.nominal_fold_from_weld_edge_mm + fit.ear_thickness_mm) == 63.
    assert fit.fixing_center_from_inside_skin_mm == 63.
    assert fit.fixing_center_from_outer_side_mm == 65.
    assert fit.slot_pair_indexes == pair


def test_only_revised_t2_source_can_claim_uploaded_bend23():
    with pytest.raises(ValueError, match="T=2"):
        resolve_receiving_large_weld_ear_fit(
            box_outer_width_mm=800., box_side_thickness_mm=2.,
            fixing_hole_pitch_x_mm=670., fixing_hole_pitch_y_mm=210.,
            ear_thickness_mm=3.,
        )
    with pytest.raises(ValueError, match="84"):
        resolve_receiving_large_weld_ear_fit(
            box_outer_width_mm=800., box_side_thickness_mm=2.,
            fixing_hole_pitch_x_mm=670., fixing_hole_pitch_y_mm=210.,
            ear_weld_edge_to_hole_center_mm=86.,
        )


def test_r3_manual_116_fixed_plate_3d_export_notice_matches_real_source_bend(tmp_path, monkeypatch):
    """Operator-facing 3D source-export text must not revive the superseded no-BEND claim."""
    from types import SimpleNamespace
    import tkinter.filedialog as filedialog
    import tkinter.messagebox as messagebox
    import ezdxf
    from gui_modules.application.fold_designer_composition_state import (
        export_selected_dxf_from_3d,
    )

    output = tmp_path / "fixed_plate_source_flat.dxf"
    seen = {}

    def confirm(title, body):
        seen["confirmation"] = body
        return True

    monkeypatch.setattr(messagebox, "askokcancel", confirm)
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kwargs: str(output))
    monkeypatch.setattr(
        messagebox, "showinfo",
        lambda title, body: seen.update({"success": body}),
    )
    monkeypatch.setattr(
        messagebox, "showerror",
        lambda title, body: pytest.fail(f"Unexpected source DXF export error: {body}"),
    )
    context = SimpleNamespace(app=SimpleNamespace(
        designer_workspace=SimpleNamespace(active_part="base_plate:fixing_plate:left"),
    ))
    saved = export_selected_dxf_from_3d(context)
    assert saved is not None and output.is_file()
    assert "BEND23" in seen["confirmation"]
    assert "未有正式折線" not in seen["confirmation"]
    assert "不使用折彎補償" in seen["confirmation"]
    assert "整箱" in seen["confirmation"]
    assert "含來源 BEND23" in seen["success"]
    assert "不代表整箱正式製造放行" in seen["success"]

    # This is the real DXF written by the GUI's source export, not a mocked drawing.
    doc = ezdxf.readfile(str(output))
    bends = [entity for entity in doc.modelspace()
             if entity.dxftype() == "LINE" and entity.dxf.layer == "BEND"]
    assert any(
        abs(float(entity.dxf.start.y) - 23.0) < 1e-6
        and abs(float(entity.dxf.end.y) - 23.0) < 1e-6
        and abs(abs(float(entity.dxf.end.x) - float(entity.dxf.start.x)) - 256.0) < 1e-6
        for entity in bends
    )
