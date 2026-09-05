# -*- coding: utf-8 -*-
"""T03 — every multi-piece Box Body exposes formed-outer and material blank dimensions."""
from __future__ import annotations

import pytest

from ae_engine.box_body_structure import resolve_box_body_structure
from ae_engine.contracts import BoxBodyPartSpec
from ae_engine.manufacturing_api import build_box_body_structure_render_data, measure_unfolded_blanks
from phase6_box_body_structure import (
    BoxBodyStructureType,
    default_box_body_structure_state,
    set_active_structure,
)
from phase6_fold_profiles import build_box_body_profile, profile_to_fold_segments


def _snapshot(*, w=1200.0, h=1600.0, d=400.0, t=2.0):
    return {
        "w": w, "h": h, "d": d, "t": t, "fw": 25.0,
        "zl1": 15.0, "zl2": 20.0, "zr1": 15.0, "zr2": 20.0,
    }


def _state(kind):
    return set_active_structure(default_box_body_structure_state(), kind)


def test_two_piece_each_piece_exposes_formed_outer_and_material_dimensions_from_its_own_topology():
    snap = _snapshot()
    resolved = resolve_box_body_structure(
        build_box_body_profile(snap), w=snap["w"], h=snap["h"], d=snap["d"], t=snap["t"],
        structure_state=_state(BoxBodyStructureType.TWO_PIECE_W_SPLIT),
    )
    assert [p.formed_outer_dimensions for p in resolved.pieces] == pytest.approx([
        (600.0, 1596.0), (600.0, 1596.0),
    ])
    assert sum(p.formed_outer_width for p in resolved.pieces) == pytest.approx(1200.0)
    for piece in resolved.pieces:
        assert piece.material_dimensions == pytest.approx((piece.structural.width, piece.structural.height))
        assert piece.material_width == pytest.approx(sum(seg.length for seg in piece.fold_profile))
        assert piece.material_width != pytest.approx(piece.formed_outer_width)


def test_three_piece_w_split_reports_three_independent_formed_and_material_pairs():
    snap = _snapshot()
    resolved = resolve_box_body_structure(
        build_box_body_profile(snap), w=snap["w"], h=snap["h"], d=snap["d"], t=snap["t"],
        structure_state=_state(BoxBodyStructureType.THREE_PIECE_W_SPLIT),
    )
    assert [p.formed_outer_width for p in resolved.pieces] == pytest.approx([50.0, 1100.0, 50.0])
    assert all(p.formed_outer_height == pytest.approx(1596.0) for p in resolved.pieces)
    assert len({p.key for p in resolved.pieces}) == 3
    assert all(p.material_width == pytest.approx(p.structural.width) for p in resolved.pieces)


def test_side_back_split_uses_depth_for_side_formed_outer_and_preserves_flat_back_material_rule():
    snap = _snapshot()
    resolved = resolve_box_body_structure(
        build_box_body_profile(snap), w=snap["w"], h=snap["h"], d=snap["d"], t=snap["t"],
        structure_state=_state(BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT),
    )
    left, back, right = resolved.pieces
    assert [p.formed_outer_width for p in resolved.pieces] == pytest.approx([400.0, 1199.0, 400.0])
    assert left.material_width > left.formed_outer_width  # front folds + rear joining fold are material, not D package allocation
    assert right.material_width > right.formed_outer_width
    assert back.material_dimensions == pytest.approx((1199.0, 1596.0))
    assert back.formed_outer_dimensions == pytest.approx((1199.0, 1596.0))


def test_manufacturing_render_data_carries_same_piece_dimension_contract_and_blank_measurement():
    snap = _snapshot()
    profile = build_box_body_profile(snap)
    spec = BoxBodyPartSpec(
        width=snap["w"], height=snap["h"], depth=snap["d"], thickness=snap["t"], frame_width=25.0,
        fold_profile=profile_to_fold_segments(profile),
        structure_state=_state(BoxBodyStructureType.TWO_PIECE_W_SPLIT),
    )
    data = build_box_body_structure_render_data(spec)
    blanks = measure_unfolded_blanks(data, part_key="box_body")
    assert len(data.pieces) == len(blanks) == 2
    for piece, blank in zip(data.pieces, blanks):
        assert piece.formed_outer_dimensions == pytest.approx((600.0, 1596.0))
        assert piece.material_dimensions == pytest.approx((blank.width, blank.height))
        assert piece.material_dimensions == pytest.approx((piece.render_data.unfolded_topology.width, piece.render_data.unfolded_topology.height))


def _descendants(widget):
    out = []
    for child in widget.winfo_children():
        out.append(child)
        out.extend(_descendants(child))
    return out


def test_real_two_piece_settings_page_shows_per_piece_formed_outer_and_material_dimensions():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        designer = app.open_original_fold_designer()
        designer.activate_part("box_body")
        root.update_idletasks(); root.update()
        designer.structure_type_var.set("二件式（W 二分）")
        bridge._phase6_select_box_structure_type(designer, designer.structure_type_var)
        root.update_idletasks(); root.update()
        page = designer.settings_panel.page_cache["box_body"]["frame"]
        texts = [str(w.cget("text")) for w in _descendants(page) if "text" in w.keys()]
        dimension_lines = [text for text in texts if "包外尺寸" in text and "料尺寸" in text]
        assert len(dimension_lines) == 2
        assert any("左箱身" in text for text in dimension_lines)
        assert any("右箱身" in text for text in dimension_lines)
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


def test_bridge_projects_receiving_side_back_pieces_to_stable_traditional_chinese_dimensions():
    import fold_designer_bridge as bridge

    snap = _snapshot(w=800.0, h=1600.0, d=350.0, t=2.0)
    profile = build_box_body_profile(snap)
    spec = BoxBodyPartSpec(
        width=snap["w"], height=snap["h"], depth=snap["d"], thickness=snap["t"], frame_width=25.0,
        fold_profile=profile_to_fold_segments(profile),
        structure_state=_state(BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT),
    )
    data = build_box_body_structure_render_data(spec)
    projections = bridge._phase6_box_body_piece_dimension_projections(data)
    assert [p.part_key for p in projections] == ["box_body:left_side", "box_body:back", "box_body:right_side"]
    assert [p.label for p in projections] == ["左側板", "後面板", "右側板"]
    assert [(p.formed_width, p.formed_height) for p in projections] == pytest.approx([
        data.pieces[0].formed_outer_dimensions,
        data.pieces[1].formed_outer_dimensions,
        data.pieces[2].formed_outer_dimensions,
    ])
    assert [(p.blank_width, p.blank_height) for p in projections] == pytest.approx([
        data.pieces[0].material_dimensions,
        data.pieces[1].material_dimensions,
        data.pieces[2].material_dimensions,
    ])
    assert projections[0].formed_width == pytest.approx(350.0)
    assert projections[1].formed_width != pytest.approx(800.0)


def test_final_scene_piece_dimension_lines_use_each_resolved_piece_not_cabinet_whd():
    from phase6_final_scene_view import _phase6_box_body_piece_dimension_lines

    snap = _snapshot(w=800.0, h=1600.0, d=350.0, t=2.0)
    spec = BoxBodyPartSpec(
        width=snap["w"], height=snap["h"], depth=snap["d"], thickness=snap["t"], frame_width=25.0,
        fold_profile=profile_to_fold_segments(build_box_body_profile(snap)),
        structure_state=_state(BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT),
    )
    data = build_box_body_structure_render_data(spec)
    lines = _phase6_box_body_piece_dimension_lines(data)
    assert len(lines) == 3
    assert lines[0].startswith("左側板：成形 350")
    assert "後面板：成形 799" in lines[1]
    assert "box_body_" not in "\n".join(lines)
