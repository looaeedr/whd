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


def test_corner_panel_is_visible_for_known_and_custom_models_with_type_locking():
    import tkinter as tk
    from gui import BoxCalculatorGUI

    root = tk.Tk()
    root.withdraw()
    try:
        app = BoxCalculatorGUI(root)
        root.update_idletasks()
        app.notebook.select(app.tab_door)
        app.baseline_var.set('金庫型')
        app.refresh_corner_type_panel()
        root.update_idletasks()
        assert app.corner_type_panel.winfo_ismapped()
        assert app.manual_corner_title_label.cget("text") == "截角類型（基準預設）"
        assert all(button.cget("state") == "disabled" for button in app.manual_corner_type_buttons.values())

        app.baseline_var.set(UNKNOWN_MODEL_NAME)
        app.refresh_corner_type_panel()
        root.update_idletasks()
        assert app.corner_type_panel.winfo_ismapped()
        assert app.manual_corner_title_label.cget("text") == "截角類型"
        assert all(button.cget("state") == "normal" for button in app.manual_corner_type_buttons.values())
        assert len(app.corner_type_small_canvases) == 4
        assert app.manual_corner_pair_same["door"] == {"top": True, "bottom": True}
        assert app.manual_top_same_var.get() is True
        assert app.manual_bottom_same_var.get() is True
        assert not hasattr(app, "manual_corner_buttons") or not app.manual_corner_buttons
    finally:
        root.destroy()


def test_unknown_gui_defaults_to_top_bottom_pair_edit_and_splits_only_on_request():
    import tkinter as tk
    from gui import BoxCalculatorGUI

    root = tk.Tk()
    root.withdraw()
    try:
        app = BoxCalculatorGUI(root)
        app.update_calculations = lambda: None
        app.notebook.select(app.tab_door)
        app.baseline_var.set(UNKNOWN_MODEL_NAME)
        app.refresh_corner_type_panel()

        app.select_manual_corner('top')
        app.set_manual_corner_type(CornerTypeId.INSERT_OVERLAY)
        state = app.manual_corner_state['door']
        assert state['top_left'].type_id is CornerTypeId.INSERT_OVERLAY
        assert state['top_right'].type_id is CornerTypeId.INSERT_OVERLAY

        app.select_manual_corner('bottom')
        app.set_manual_corner_type(CornerTypeId.CROSS)
        assert state['bottom_left'].type_id is CornerTypeId.CROSS
        assert state['bottom_right'].type_id is CornerTypeId.CROSS

        app.toggle_manual_corner_parameter_lock()
        assert app._manual_corner_parameters_unlocked('door') is True
        app.manual_top_same_var.set(False)
        app.on_manual_corner_pair_same_changed('top')
        app.select_manual_corner('top_right')
        app.set_manual_corner_type(CornerTypeId.OVERLAY)
        assert state['top_left'].type_id is CornerTypeId.INSERT_OVERLAY
        assert state['top_right'].type_id is CornerTypeId.OVERLAY

        app.manual_top_same_var.set(True)
        app.on_manual_corner_pair_same_changed('top')
        assert state['top_left'].type_id is CornerTypeId.INSERT_OVERLAY
        assert state['top_right'].type_id is CornerTypeId.INSERT_OVERLAY
    finally:
        root.destroy()
