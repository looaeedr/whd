from copy import deepcopy
from pathlib import Path

from ae_engine.corner_type_ui import UNKNOWN_MODEL_NAME
from ae_engine.sheetmetal_geometry import CornerTypeId, CornerTypeSelection, FourCornerTypePolicy
from ae_engine.sheetmetal_part_adapters import DoorFrameEdges, build_door_result, build_unknown_door_result

ROOT = Path(__file__).resolve().parents[1]


def _outline(result):
    return [(round(p.x, 6), round(p.y, 6)) for p in result.outline]


def _c02_policy(fw=25.0):
    c02 = CornerTypeSelection(CornerTypeId.C02)
    return FourCornerTypePolicy(c02, c02, c02, c02, fw=fw)


def test_corner_type_update_preserves_phase6_clean_break_layout():
    forbidden = (
        'ae.py', 'contracts.py', 'manufacturing_api.py', 'sheetmetal_geometry.py',
        'sheetmetal_features.py', 'sheetmetal_part_adapters.py', 'sheetmetal_drawing.py',
        'hole_catalog.py', 'corner_type_ui.py',
    )
    assert all(not (ROOT / name).exists() for name in forbidden)
    assert (ROOT / 'ae_engine' / 'corner_type_ui.py').is_file()
    source = (ROOT / 'gui.py').read_text(encoding='utf-8')
    assert 'import ae_engine.ae as ae' in source
    assert '\nimport ae\n' not in source


def test_unknown_c02_preserves_phase6_multi_door_frame_edge_semantics():
    edges = DoorFrameEdges(left=True, right=False, top=True, bottom=False)
    kwargs = dict(
        w=400, h=300, t=2, fw=25, gap_w=3.5, gap_h=3.5,
        fold_left=19, fold_right=15, fold_top=15, fold_bottom=15,
        frame_edges=edges,
    )
    vault = build_door_result(**kwargs)
    unknown = build_unknown_door_result(**kwargs, corner_policy=_c02_policy())
    assert _outline(unknown) == _outline(vault)
    assert (unknown.width, unknown.height) == (vault.width, vault.height)


def test_unknown_model_name_is_not_a_phase6_baseline_source():
    source = (ROOT / 'gui.py').read_text(encoding='utf-8')
    assert 'def _baseline_source_model' in source
    assert 'is_unknown_model(value)' in source
    assert UNKNOWN_MODEL_NAME == '自訂'


def _open_fold_designer(model_name):
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    app.baseline_var.set(model_name)
    root.update_idletasks(); root.update()
    designer = app.open_original_fold_designer()
    designer.activate_part('door')
    root.update_idletasks(); root.update()
    return root, app, designer


def test_corner_panel_is_visible_for_known_and_custom_models_with_type_locking():
    import fold_designer_bridge as bridge

    root, app, designer = _open_fold_designer('金庫型')
    try:
        assert not hasattr(app, 'notebook')
        assert bridge._phase6_corner_type_editable(designer, 'door') is False
        before = deepcopy(designer._phase6_corner_state['door'])

        designer.toggle_corner_parameter_lock()
        root.update_idletasks(); root.update()
        assert bridge._phase6_corner_parameters_unlocked(designer, 'door') is True
        assert designer.corner_type_vars

        # Known families expose fine parameters after unlock, but CornerType is
        # owned by the family contract.  Even a programmatic selector change is ignored.
        target = 'top' if 'top' in designer.corner_type_vars else next(iter(designer.corner_type_vars))
        designer.corner_type_vars[target].set('C02')
        bridge._phase6_corner_type_selected(designer, 'door', target)
        assert designer._phase6_corner_state['door'] == before
    finally:
        try:
            designer.root.destroy()
        except Exception:
            pass
        root.destroy()

    root, app, designer = _open_fold_designer(UNKNOWN_MODEL_NAME)
    try:
        assert not hasattr(app, 'notebook')
        assert bridge._phase6_corner_type_editable(designer, 'door') is True
        assert designer._phase6_corner_pair_same['door'] == {'top': True, 'bottom': True}
        designer.toggle_corner_parameter_lock()
        root.update_idletasks(); root.update()
        assert designer.corner_pair_vars['top'].get() is True
        assert designer.corner_pair_vars['bottom'].get() is True
        assert designer.corner_type_vars
    finally:
        try:
            designer.root.destroy()
        except Exception:
            pass
        root.destroy()


def test_unknown_gui_defaults_to_top_bottom_pair_edit_and_splits_only_on_request():
    import fold_designer_bridge as bridge

    root, app, designer = _open_fold_designer(UNKNOWN_MODEL_NAME)
    try:
        assert not hasattr(app, 'notebook')
        designer.toggle_corner_parameter_lock()
        root.update_idletasks(); root.update()

        state = designer._phase6_corner_state['door']
        assert designer._phase6_corner_pair_same['door'] == {'top': True, 'bottom': True}

        insert_overlay_label = bridge._CORNER_TYPE_LABEL_BY_ID[CornerTypeId.INSERT_OVERLAY.value]
        cross_label = bridge._CORNER_TYPE_LABEL_BY_ID[CornerTypeId.CROSS.value]
        overlay_label = bridge._CORNER_TYPE_LABEL_BY_ID[CornerTypeId.OVERLAY.value]

        designer.corner_type_vars['top'].set(insert_overlay_label)
        bridge._phase6_corner_type_selected(designer, 'door', 'top')
        assert state['top_left']['type_id'] == CornerTypeId.INSERT_OVERLAY.value
        assert state['top_right']['type_id'] == CornerTypeId.INSERT_OVERLAY.value

        designer.corner_type_vars['bottom'].set(cross_label)
        bridge._phase6_corner_type_selected(designer, 'door', 'bottom')
        assert state['bottom_left']['type_id'] == CornerTypeId.CROSS.value
        assert state['bottom_right']['type_id'] == CornerTypeId.CROSS.value

        designer.corner_pair_vars['top'].set(False)
        bridge._phase6_corner_pair_var_changed(designer, 'door', 'top', designer.corner_pair_vars['top'])
        root.update_idletasks(); root.update()
        assert designer._phase6_corner_pair_same['door']['top'] is False
        designer.corner_type_vars['top_right'].set(overlay_label)
        bridge._phase6_corner_type_selected(designer, 'door', 'top_right')
        assert state['top_left']['type_id'] == CornerTypeId.INSERT_OVERLAY.value
        assert state['top_right']['type_id'] == CornerTypeId.OVERLAY.value

        designer.corner_pair_vars['top'].set(True)
        bridge._phase6_corner_pair_var_changed(designer, 'door', 'top', designer.corner_pair_vars['top'])
        assert state['top_left']['type_id'] == CornerTypeId.INSERT_OVERLAY.value
        assert state['top_right']['type_id'] == CornerTypeId.INSERT_OVERLAY.value
    finally:
        try:
            designer.root.destroy()
        except Exception:
            pass
        root.destroy()
