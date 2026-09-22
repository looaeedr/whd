from __future__ import annotations

import pytest


def _snapshot(*, upper=1100.0, lower=500.0):
    from ae_engine.cabinet_types import receiving

    snapshot = receiving.apply_family_defaults({"model": "受電箱"})
    snapshot["h"] = float(upper) + float(lower)
    snapshot["door_layout_columns"] = [[800.0, [float(upper), float(lower)]]]
    return snapshot


def _state(mode):
    from ae_engine.cabinet_types import receiving
    from phase6_box_body_structure import set_side_back_back_panel_mode

    state = receiving.resolve_box_body_structure_state(None)
    return set_side_back_back_panel_mode(state, mode)


def _contract(mode, *, upper=1100.0, lower=500.0):
    from ae_engine.cabinet_types import receiving

    snapshot = _snapshot(upper=upper, lower=lower)
    return receiving.resolve_back_panel_contract(
        snapshot,
        structure_state=_state(mode),
        panel_width=795.0,
        full_panel_height=float(snapshot["h"]) - 4.0,
    )


def _render(mode):
    from ae_engine.cabinet_types import receiving
    from ae_engine.contracts import BoxBodyPartSpec
    from ae_engine.manufacturing_api import build_box_body_structure_render_data
    from phase6_fold_profiles import build_box_body_profile, profile_to_fold_segments

    snapshot = _snapshot()
    state = _state(mode)
    contract = receiving.resolve_back_panel_contract(
        snapshot,
        structure_state=state,
        panel_width=795.0,
        full_panel_height=1596.0,
    )
    spec = BoxBodyPartSpec(
        width=800.0,
        height=1600.0,
        depth=350.0,
        thickness=2.0,
        frame_width=29.0,
        model_name="受電箱",
        fold_profile=profile_to_fold_segments(build_box_body_profile(snapshot)),
        structure_state=state,
        back_panel_contract=contract,
    )
    data = build_box_body_structure_render_data(spec)
    return data, next(piece for piece in data.pieces if piece.role == "back")


def _cutting_closed(render_data):
    from ae_engine.sheetmetal_drawing import PolylinePrimitive

    return [
        primitive
        for primitive in tuple(render_data.scene.primitives)
        if isinstance(primitive, PolylinePrimitive)
        and str(primitive.layer) == "CUTTING"
        and primitive.closed
    ]


def _bounds(polyline):
    xs = [float(point.x) for point in polyline.points]
    ys = [float(point.y) for point in polyline.points]
    return min(xs), min(ys), max(xs), max(ys)


def test_receiving_back_panel_state_defaults_full_and_persists_one_of_three_modes():
    from ae_engine.cabinet_types import receiving
    from phase6_box_body_structure import (
        BackPanelMode,
        back_panel_mode,
        set_side_back_back_panel_mode,
    )

    state = receiving.resolve_box_body_structure_state(None)
    assert back_panel_mode(state) is BackPanelMode.FULL

    for mode in (BackPanelMode.FULL, BackPanelMode.HALF, BackPanelMode.BACK_OPENING):
        changed = set_side_back_back_panel_mode(state, mode)
        assert back_panel_mode(changed) is mode
        from phase6_box_body_structure import BoxBodyStructureType
        key = BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
        assert changed["configs"][key]["back_panel_mode"] == mode.value


def test_receiving_1100_half_contract_uses_certified_fixed_position_and_four_slot_datums():
    contract = _contract("HALF")

    assert contract["mode"] == "HALF"
    assert contract["full_panel_height"] == pytest.approx(1596.0)
    assert contract["material_height"] == pytest.approx(1124.0)
    assert contract["formed_y_offset"] == pytest.approx(236.0)
    assert contract["opening"] is None
    expected = (
        (120.0, 1004.0),
        (675.0, 1004.0),
        (120.0, 120.0),
        (675.0, 120.0),
    )
    assert len(contract["fixed_slot_datums"]) == len(expected)
    for actual, wanted in zip(contract["fixed_slot_datums"], expected):
        assert tuple(actual) == pytest.approx(wanted)

    changed = _contract("HALF", upper=900.0, lower=700.0)
    assert changed["material_height"] == pytest.approx(924.0)


def test_receiving_full_and_back_opening_contracts_use_four_holes_and_fixed_650x200_opening():
    full = _contract("FULL")
    opened = _contract("BACK_OPENING")

    expected_slots = (
        (120.0, 1476.0),
        (675.0, 1476.0),
        (120.0, 120.0),
        (675.0, 120.0),
    )
    for contract in (full, opened):
        assert len(contract["fixed_slot_datums"]) == len(expected_slots)
        for actual, wanted in zip(contract["fixed_slot_datums"], expected_slots):
            assert tuple(actual) == pytest.approx(wanted)
    assert full["opening"] is None
    assert tuple(opened["opening"]) == pytest.approx((72.5, 248.0, 722.5, 448.0))


@pytest.mark.parametrize(
    ("mode", "expected_height", "extra_cut_count"),
    (("FULL", 1596.0, 4), ("HALF", 1124.0, 4), ("BACK_OPENING", 1596.0, 5)),
)
def test_back_panel_finalscene_uses_mode_height_four_reference_slots_and_optional_opening(
    mode, expected_height, extra_cut_count
):
    data, back = _render(mode)

    minx, miny, maxx, maxy = map(float, back.render_data.material.bounds)
    assert maxx - minx == pytest.approx(795.0)
    assert maxy - miny == pytest.approx(expected_height)

    cutting = _cutting_closed(back.render_data)
    # primary back-panel boundary + four reference slots (+ fixed rear opening)
    assert len(cutting) == 1 + extra_cut_count

    secondary = cutting[1:]
    if mode == "BACK_OPENING":
        opening = max(secondary, key=lambda row: (_bounds(row)[2] - _bounds(row)[0]))
        assert _bounds(opening) == pytest.approx((72.5, 248.0, 722.5, 448.0))
        secondary.remove(opening)

    assert len(secondary) == 4
    assert all((_bounds(row)[2] - _bounds(row)[0]) == pytest.approx(16.0, abs=0.03) for row in secondary)
    assert all((_bounds(row)[3] - _bounds(row)[1]) == pytest.approx(23.5, abs=0.03) for row in secondary)


def test_half_back_panel_3d_keeps_original_top_edge_instead_of_recentering_shorter_panel():
    from phase6_final_scene_view import _phase6_box_body_structure_meshes

    full_data, _ = _render("FULL")
    half_data, half_back = _render("HALF")
    full_meshes = _phase6_box_body_structure_meshes(full_data, thickness=2.0)
    half_meshes = _phase6_box_body_structure_meshes(half_data, thickness=2.0)

    def y_bounds(meshes, role):
        points = [
            point
            for piece, triangles in meshes
            if piece.role == role
            for triangle in triangles
            for point in triangle
        ]
        return min(p[1] for p in points), max(p[1] for p in points)

    full_back = y_bounds(full_meshes, "back")
    half_back_bounds = y_bounds(half_meshes, "back")
    side_bounds = y_bounds(half_meshes, "left_side")

    assert half_back.formed_y_offset == pytest.approx(236.0)
    assert half_back_bounds[1] == pytest.approx(full_back[1])
    assert half_back_bounds[1] == pytest.approx(side_bounds[1])
    assert half_back_bounds[0] > full_back[0]


def test_back_panel_modes_round_trip_through_project_file_and_workspace(tmp_path):
    import phase6_project_file as project
    from phase6_box_body_structure import BackPanelMode, back_panel_mode
    from phase6_designer_workspace import Phase6DesignerWorkspace

    state = _state(BackPanelMode.BACK_OPENING)
    payload = {
        "schema": project.PROJECT_SCHEMA,
        "snapshot": {
            "model": "受電箱",
            "workspace": {
                "existing_parts": [
                    "box_body",
                    "box_body:left_side",
                    "box_body:back",
                    "box_body:right_side",
                    "head",
                    "tail",
                ],
                "active_part": "box_body:back",
                "box_body_structure": state,
            },
        },
        "final_geometry": {},
    }
    path = project.write_project(tmp_path / "receiving-back-panel-mode.p6fold", payload)
    loaded = project.read_project(path)
    restored = Phase6DesignerWorkspace.from_snapshot(loaded["snapshot"])

    assert restored.active_part == "box_body:back"
    assert back_panel_mode(restored.box_body_structure_state()) is BackPanelMode.BACK_OPENING


@pytest.mark.parametrize(
    ("mode", "expected_closed_cutting"),
    (("FULL", 5), ("HALF", 5), ("BACK_OPENING", 6)),
)
def test_back_panel_dxf_save_reopen_preserves_reference_cutting(mode, expected_closed_cutting, tmp_path):
    import ezdxf
    from ae_engine.manufacturing_api import save_part_render_data_dxf

    _data, back = _render(mode)
    output = tmp_path / f"back-{mode}.dxf"
    save_part_render_data_dxf(back.render_data, output, overwrite=True)
    doc = ezdxf.readfile(output)
    cutting = [
        entity
        for entity in doc.modelspace()
        if entity.dxftype() == "LWPOLYLINE"
        and str(entity.dxf.layer) == "CUTTING"
        and bool(entity.closed)
    ]
    assert len(cutting) == expected_closed_cutting


def test_receiving_back_panel_selector_lives_inside_existing_back_section_and_updates_canonical_state():
    import os

    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")

    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge
    from phase6_box_body_structure import BackPanelMode, back_panel_mode

    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    designer = None
    try:
        app.baseline_var.set("受電箱")
        root.update_idletasks(); root.update()
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()

        designer.activate_part("box_body")
        bridge._phase6_invalidate_settings_page(designer, "box_body")
        bridge._phase6_render_settings_context(designer, "box_body")
        root.update_idletasks(); root.update()

        sections = dict(designer.box_body_piece_input_sections)
        assert tuple(sections) == (
            "box_body:left_side",
            "box_body:back",
            "box_body:right_side",
        )
        assert "back_panel_mode" in designer.box_body_piece_input_vars["box_body:back"]
        selector_var = designer.box_body_piece_input_vars["box_body:back"]["back_panel_mode"]
        selector = designer.box_body_piece_input_entries["box_body:back"]["back_panel_mode"]
        assert selector_var.get() == "全板"
        assert tuple(selector.cget("values")) == ("全板", "半截", "背開孔")
        assert str(selector.cget("state")) == "readonly"

        selector_var.set("半截")
        selector.event_generate("<<ComboboxSelected>>")
        root.update_idletasks(); root.update()
        assert back_panel_mode(
            designer.designer_workspace.box_body_structure_state()
        ) is BackPanelMode.HALF

        rendered = bridge._phase6_query_final_render_data(designer)
        back = next(piece for piece in rendered.pieces if piece.role == "back")
        assert back.material_dimensions[1] == pytest.approx(1124.0)

        bridge._phase6_invalidate_settings_page(designer, "box_body")
        bridge._phase6_render_settings_context(designer, "box_body")
        root.update_idletasks(); root.update()
        assert (
            designer.box_body_piece_input_vars["box_body:back"]["back_panel_mode"].get()
            == "半截"
        )
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass

