import inspect
from types import SimpleNamespace

import gui
import fold_designer_bridge as bridge


def _source(obj):
    return inspect.getsource(obj)


def test_t7_main_create_widgets_has_no_user_reachable_legacy_2d_notebook():
    src = _source(gui.BoxCalculatorGUI.create_widgets)
    assert 'self.notebook = ttk.Notebook(right_container)' not in src
    assert 'self.notebook.add(' not in src
    assert '<<NotebookTabChanged>>' not in src
    assert '_legacy_2d_compat_host' in src
    assert '展開圖已移至折彎 / 3D 設計的「截角資料」' in src


def test_t7_snapshot_presence_and_manual_corner_identity_do_not_read_view_tabs():
    methods = (
        gui.BoxCalculatorGUI._make_original_fold_designer_snapshot,
        gui.BoxCalculatorGUI._apply_existing_parts_from_fold_workspace,
        gui.BoxCalculatorGUI._current_manual_corner_part_key,
    )
    for method in methods:
        src = _source(method)
        assert 'self.notebook' not in src
        assert 'tab_z' not in src
        assert 'tab_head' not in src
        assert 'tab_tail' not in src
        assert 'tab_door' not in src
        assert 'tab_base_plate' not in src
    manual_src = _source(gui.BoxCalculatorGUI._current_manual_corner_part_key)
    assert 'workspace_controller' in manual_src
    assert 'active_part' in manual_src


def test_t7_open_designer_has_no_return_to_legacy_2d_navigation_callback():
    src = _source(gui.BoxCalculatorGUI.open_original_fold_designer)
    assert 'def return_to_2d_corner' not in src
    assert 'on_return_2d=' not in src
    assert 'self.notebook.select' not in src


def test_t7_fold_designer_top_bar_has_no_return_to_legacy_2d_entry():
    top_src = _source(bridge._phase6_build_persistent_top_area)
    init_src = _source(bridge._fix11_init)
    assert '回2D截角' not in top_src
    assert '_phase6_return_to_2d_corner' not in top_src
    assert 'return_2d_button' not in top_src
    assert 'on_return_2d' not in inspect.signature(bridge._fix11_init).parameters
    assert '_return_2d_callback' not in init_src
    assert not hasattr(bridge, '_phase6_return_to_2d_corner')


def test_t7_draw_preview_only_refreshes_visible_authoritative_corner_data_view():
    calls = []

    class Designer:
        _phase6_3d_display_mode = 'corner_data'
        corner_data_canvas = object()

        def _phase6_refresh_corner_data_unfold_view(self):
            calls.append('refresh')
            return 'projection'

    owner = gui.BoxCalculatorGUI.__new__(gui.BoxCalculatorGUI)
    owner.fold_designer_app = Designer()
    assert owner.draw_preview() == 'projection'
    assert calls == ['refresh']

    owner.fold_designer_app._phase6_3d_display_mode = 'assembly'
    assert owner.draw_preview() is None
    assert calls == ['refresh']

    owner.fold_designer_app = None
    assert owner.draw_preview() is None
    assert calls == ['refresh']


def test_t7_shared_t5_view_and_interaction_helpers_are_preserved():
    renderer = _source(gui.BoxCalculatorGUI._render_fold_designer_corner_data_view)
    assert 'render_drawing_scene(' in renderer
    assert '_draw_phase6_annotation_projection(' in renderer
    assert 'open_part_hole_editor' in renderer
    assert 'on_door_canvas_press' in renderer
    assert 'on_door_canvas_drag' in renderer
    assert 'on_door_canvas_release' in renderer
    assert hasattr(gui, 'render_drawing_scene')
    assert hasattr(gui, '_draw_phase6_annotation_projection')
    assert hasattr(gui.BoxCalculatorGUI, 'open_part_hole_editor')
    assert hasattr(gui.BoxCalculatorGUI, 'on_door_canvas_press')
    assert hasattr(gui.BoxCalculatorGUI, 'on_door_canvas_drag')
    assert hasattr(gui.BoxCalculatorGUI, 'on_door_canvas_release')


def test_t7_corner_data_refresh_is_exposed_as_view_only_designer_method():
    assert getattr(
        bridge.Phase6FoldDesignerApp,
        '_phase6_refresh_corner_data_unfold_view',
        None,
    ) is bridge._phase6_refresh_corner_data_unfold_view


def test_t7_legacy_draw_dispatch_is_not_a_navigation_authority():
    src = _source(gui.BoxCalculatorGUI.draw_preview)
    for forbidden in (
        'self.notebook', 'tab_z', 'tab_head', 'tab_tail', 'tab_door',
        'tab_base_plate', 'draw_box_body(', 'draw_end_cap(', 'draw_door(',
        'draw_base_plate(',
    ):
        assert forbidden not in src
    assert 'fold_designer_app' in src
    assert '_phase6_refresh_corner_data_unfold_view' in src
