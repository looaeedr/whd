# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import tkinter as tk

import pytest
from shapely.geometry import box

from ae_engine.assembly_joint import AssemblyJointRelation, edge_relation_for_part
from ae_engine.certified_relief_registry import registered_certified_relief_rules

FIXTURE = Path(__file__).with_name('fixtures') / 'vault_overlay_w400_t2_fw25.p6fold'


def _destroy(app, root):
    try:
        win = getattr(app, 'fold_designer_window', None)
        if win is not None and win.winfo_exists():
            win.destroy()
    except Exception:
        pass
    try:
        root.destroy()
    except tk.TclError:
        pass


def _edge_span(material, *, high: bool):
    minx, miny, maxx, maxy = map(float, material.bounds)
    eps = 0.5
    band = (
        box(minx - 1.0, maxy - eps, maxx + 1.0, maxy)
        if high else
        box(minx - 1.0, miny, maxx + 1.0, miny + eps)
    )
    section = material.intersection(band)
    sx0, _sy0, sx1, _sy1 = map(float, section.bounds)
    return sx0 - minx, maxx - sx1, sx1 - sx0


def _assert_overlay_material(part_key, material):
    # Native head/tail Y direction is opposite.  Semantic TOP is the lower flat
    # edge for Head and the upper flat edge for Tail.
    top = _edge_span(material, high=(part_key == 'tail'))
    bottom = _edge_span(material, high=(part_key == 'head'))

    # Certified OVERLAY revision 3 owns the final top relief.  The historical
    # formed-FW=29 measurement is shadow evidence only; it is not the runtime
    # formula.  For this fixture STANDARD + Semantic Delta resolves
    # primary_u = side_fold(15) + FW(25) = 40 mm on both sides.
    rule = next(
        row for row in registered_certified_relief_rules()
        if row.rule_id == "ENDCAP_TOP_OVERLAY_STANDARD_V1"
    )
    assert rule.revision == 3
    assert dict(rule.formula_record or {})["primary_u"] == "side_fold + FW"
    expected_top_u = 15.0 + 25.0
    assert top[0] == pytest.approx(expected_top_u)
    assert top[1] == pytest.approx(expected_top_u)
    assert top[2] == pytest.approx((material.bounds[2] - material.bounds[0]) - 2.0 * expected_top_u)

    # BOTTOM is not an OVERLAY-formula oracle in this intent.  Its geometry is
    # still compared byte-for-byte across 2D/single-3D/assembly/reload below.
    # Relation ownership itself is asserted from the resolved Joint Graph.
    assert all(value >= 0.0 for value in bottom)


def test_vault_overlay_fw_width_invariant_2d_single3d_assembly_and_reload(tmp_path):
    import gui
    import fold_designer_bridge as bridge

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    save_path = tmp_path / 'vault_overlay_roundtrip.p6fold'
    try:
        app.load_phase6_project(FIXTURE, open_designer=False)
        assert app._current_box_assembly_type().value == 'OVERLAY'
        val = app.get_float_values()
        assert val['w'] == pytest.approx(400.0)
        assert val['t'] == pytest.approx(2.0)
        assert val['fw'] == pytest.approx(25.0)
        for part_key in ('head', 'tail'):
            assert edge_relation_for_part(app.assembly_joint_state, part_key, 'TOP') is AssemblyJointRelation.OVERLAY
            assert edge_relation_for_part(app.assembly_joint_state, part_key, 'BOTTOM') is AssemblyJointRelation.INSERT

        designer = app.open_original_fold_designer()
        designer.preview_3d_enabled = False
        designer._phase6_3d_display_mode = 'assembly'
        bundle = bridge._phase6_query_assembly_render_data(designer)
        assert dict(getattr(designer, '_phase6_last_relief_errors', {}) or {}) == {}
        assembly = {part.part_key: part.render_data for part in bundle.assembly_parts}

        for part_key, is_tail in (('head', False), ('tail', True)):
            main_2d = app._authoritative_render_data(
                app._end_cap_part_spec(val, is_tail=is_tail),
                app._manufacturing_context(draw_stock=False),
            )
            _assert_overlay_material(part_key, main_2d.material)
            _assert_overlay_material(part_key, assembly[part_key].material)
            assert main_2d.material.symmetric_difference(assembly[part_key].material).area <= 1e-6

            designer.activate_part(part_key)
            single_3d = bridge._phase6_query_final_render_data(designer)
            _assert_overlay_material(part_key, single_3d.material)
            assert single_3d.material.symmetric_difference(main_2d.material).area <= 1e-6

        app.project_controller.save(
            save_path,
            app._compose_phase6_project_snapshot_from_main_gui,
            active_part_hint='box_body',
        )
    finally:
        _destroy(app, root)

    root2 = tk.Tk(); root2.withdraw()
    app2 = gui.BoxCalculatorGUI(root2)
    try:
        app2.load_phase6_project(save_path, open_designer=False)
        assert app2._current_box_assembly_type().value == 'OVERLAY'
        for part_key in ('head', 'tail'):
            assert edge_relation_for_part(app2.assembly_joint_state, part_key, 'TOP') is AssemblyJointRelation.OVERLAY
            assert edge_relation_for_part(app2.assembly_joint_state, part_key, 'BOTTOM') is AssemblyJointRelation.INSERT
        val2 = app2.get_float_values()
        for part_key, is_tail in (('head', False), ('tail', True)):
            main_2d = app2._authoritative_render_data(
                app2._end_cap_part_spec(val2, is_tail=is_tail),
                app2._manufacturing_context(draw_stock=False),
            )
            _assert_overlay_material(part_key, main_2d.material)
    finally:
        _destroy(app2, root2)
