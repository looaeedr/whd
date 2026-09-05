from pathlib import Path
from types import SimpleNamespace

import pytest

import gui
import fold_designer_bridge as bridge
import phase6_settings_panel as settings_panel


class DummyVar:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


class DummyWidget:
    def __init__(self, manager="pack"):
        self.manager = manager
        self.pack_calls = 0
        self.forget_calls = 0
    def pack(self, *args, **kwargs):
        self.manager = "pack"
        self.pack_calls += 1
    def pack_forget(self):
        self.manager = ""
        self.forget_calls += 1
    def winfo_manager(self):
        return self.manager


def _designer_workspace(*parts, active=None):
    from phase6_designer_workspace import Phase6DesignerWorkspace
    return Phase6DesignerWorkspace.from_snapshot({
        "existing_parts": list(parts or ("box_body",)), "active_part": active
    })


def make_indicator_app(*, multi=False, single_box=False, direct=False, selected="0:0", states=None):
    app = object.__new__(gui.BoxCalculatorGUI)
    app.multi_door_enabled_var = DummyVar(multi)
    app.is_indicator_box_var = DummyVar(single_box)
    app.is_door_indicator_var = DummyVar(direct)
    app.indicator_l_var = DummyVar("1")
    app.indicator_layer_g_vars = [DummyVar("2") for _ in range(6)]
    app.door_layout_selected_var = DummyVar(selected)
    app.door_layout_indicator_states = dict(states or {})
    return app


def test_indicator_box_result_groups_exist_only_for_real_indicator_box_mode():
    app = make_indicator_app()
    assert app._active_indicator_box_groups_for_results() is None

    app.is_door_indicator_var.set(True)
    assert app._active_indicator_box_groups_for_results() is None

    app.is_door_indicator_var.set(False)
    app.is_indicator_box_var.set(True)
    assert app._active_indicator_box_groups_for_results() == (2,)


def test_multi_door_result_groups_follow_selected_cell_mode_only():
    app = make_indicator_app(
        multi=True,
        states={
            "0:0": {"mode": "indicator", "layers": 1, "groups": [2, 2, 2, 2, 2, 2]},
            "1:0": {"mode": "indicator_box", "layers": 2, "groups": [3, 2, 2, 2, 2, 2]},
        },
    )
    assert app._active_indicator_box_groups_for_results() is None
    app.door_layout_selected_var.set("1:0")
    assert app._active_indicator_box_groups_for_results() == (3, 2)


def test_indicator_box_result_values_are_blank_when_no_box_and_real_when_enabled():
    app = make_indicator_app()
    app.result_ib_w_var = DummyVar("stale")
    app.result_ib_h_var = DummyVar("stale")
    app.result_ib_door_w_var = DummyVar("stale")
    app.result_ib_door_h_var = DummyVar("stale")
    app.indicator_g_var = DummyVar("stale")
    app.ib_hole_start_x_var = DummyVar("stale")
    app.ib_hole_pitch_var = DummyVar("stale")
    app.ib_hole_count_var = DummyVar("stale")
    app.ib_hole_y_var = DummyVar("stale")

    app._refresh_indicator_box_result_values({"t": 2.0})
    assert app.result_ib_w_var.get() == "-"
    assert app.result_ib_h_var.get() == "-"
    assert app.result_ib_door_w_var.get() == "-"
    assert app.result_ib_door_h_var.get() == "-"

    app.is_indicator_box_var.set(True)
    app._refresh_indicator_box_result_values({"t": 2.0})
    assert app.result_ib_w_var.get() == "396.00 mm"
    assert app.result_ib_h_var.get() == "445.00 mm"
    assert app.result_ib_door_w_var.get() == "323.00 mm"
    assert app.result_ib_door_h_var.get() == "372.00 mm"


def test_has_any_indicator_box_ignores_direct_indicator_and_finds_box_cells():
    app = make_indicator_app(multi=False, single_box=False, direct=True)
    assert app._has_any_indicator_box() is False
    app.is_indicator_box_var.set(True)
    assert app._has_any_indicator_box() is True

    app = make_indicator_app(
        multi=True,
        states={
            "0:0": {"mode": "indicator", "layers": 1, "groups": [2] * 6},
            "1:0": {"mode": "indicator_box", "layers": 1, "groups": [2] * 6},
        },
    )
    app.get_door_layout_cells = lambda: (_ for _ in ()).throw(RuntimeError("no layout objects in unit test"))
    assert app._has_any_indicator_box() is True


def test_indicator_aux_exports_default_off_and_export_path_is_box_gated():
    source = Path(gui.__file__).read_text(encoding="utf-8")
    assert "self.export_ib_var   = tk.BooleanVar(value=False)" in source
    assert "self.export_ib_door_var = tk.BooleanVar(value=False)" in source
    assert "self._has_any_indicator_box()" in source


def test_fold_designer_part_existence_is_not_controlled_by_indicator_export_checkboxes():
    from phase6_workspace_controller import Phase6WorkspaceController
    workspace_controller = Phase6WorkspaceController()
    workspace_controller.commit_workspace({
        "existing_parts": ["box_body", "indicator_box", "indicator_door"],
        "active_part": "box_body",
        "part_profiles": {},
    })
    holder = SimpleNamespace(workspace_controller=workspace_controller)
    existing = gui.BoxCalculatorGUI._phase6_current_existing_parts(holder)
    assert existing == {"box_body", "indicator_box", "indicator_door"}


def test_phase6_legacy_home_api_routes_directly_to_box_body():
    holder = SimpleNamespace()
    calls = []
    holder.activate_part = lambda key: calls.append(key) or True

    assert bridge._phase6_show_home(holder) is True
    assert calls == ["box_body"]


def test_phase6_part_selector_has_no_home_button_but_keeps_compatibility_api():
    source = Path(bridge.__file__).read_text(encoding="utf-8")
    assert 'text="首頁"' not in source
    assert "command=self.show_home" not in source
    assert "def _phase6_show_home" in source


def test_advanced_settings_remain_but_duplicate_corner_compatibility_panel_is_removed():
    assert "補償" in settings_panel.ADVANCED_SETTING_GROUPS
    # 固定孔／封尾固定孔是基準檔資料，不得再從自訂的進階設定重複露出。
    assert "固定孔" not in settings_panel.ADVANCED_SETTING_GROUPS
    assert "封尾固定孔" not in settings_panel.ADVANCED_SETTING_GROUPS
    assert "門縫" in settings_panel.ADVANCED_SETTING_GROUPS
    assert "Relief" in settings_panel.CORNER_COMPAT_SETTING_GROUPS

    source = Path(settings_panel.__file__).read_text(encoding="utf-8")
    assert "進階截角參數" not in source
    assert 'text="進階參數"' in source
    assert 'text="顯示進階設定"' not in source
    assert "截角底層相容參數" not in source
    assert "顯示截角底層相容參數" not in source


def test_real_tk_default_has_no_indicator_aux_size_and_home_roundtrip():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        root.update_idletasks()
        root.update()
        assert app.is_indicator_box_var.get() is False
        assert app.result_ib_w_var.get() == "-"
        assert app.result_ib_h_var.get() == "-"
        assert app.result_ib_door_w_var.get() == "-"
        assert app.result_ib_door_h_var.get() == "-"
        assert app.export_ib_var.get() is False
        assert app.export_ib_door_var.get() is False

        app.is_door_indicator_var.set(True)
        app.update_calculations()
        assert app.result_ib_w_var.get() == "-"
        assert app.result_ib_door_w_var.get() == "-"
        app.is_door_indicator_var.set(False)
        app.is_indicator_box_var.set(True)
        app.update_calculations()
        assert app.result_ib_w_var.get() == "396.00 mm"
        assert app.result_ib_h_var.get() == "445.00 mm"
        assert app.result_ib_door_w_var.get() == "323.00 mm"
        assert app.result_ib_door_h_var.get() == "372.00 mm"
        app.is_indicator_box_var.set(False)
        app.update_calculations()
        assert app.result_ib_w_var.get() == "-"
        assert app.result_ib_door_w_var.get() == "-"

        designer = app.open_original_fold_designer()
        root.update_idletasks()
        root.update()
        assert designer.active_part_key == "box_body"
        assert not hasattr(designer, "home_part_button")
        assert designer.left_global_controls.winfo_manager() == "pack"

        designer.activate_part("door")
        root.update_idletasks()
        root.update()
        assert designer.active_part_key == "door"
        assert designer.left_global_controls.winfo_manager() == "pack"
        assert designer.advanced_toggle_button is None

        designer.show_home()
        root.update_idletasks()
        root.update()
        assert designer.active_part_key == "box_body"
        assert designer.left_global_controls.winfo_manager() == "pack"
        assert designer.fold_editor_host.winfo_manager() == "pack"
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


def test_real_tk_part_selector_menu_opens_part_and_delete_shares_selector_row():
    import os
    if not os.environ.get('DISPLAY'):
        pytest.skip('需要 Tk 顯示環境')
    import tkinter as tk

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()

        # Phase6 no longer has a landing/home page or per-part button strip.
        # Opening 3D enters Box Body directly, while the persistent selector is
        # a Menubutton + Menu row with Add/Delete controls.
        assert designer.active_part_key == 'box_body'
        assert designer.part_buttons == {}
        children = designer.part_selector.winfo_children()
        menubuttons = [w for w in children if w.winfo_class() in {'Menubutton', 'TMenubutton'}]
        assert len(menubuttons) == 2
        selector, add_button = menubuttons
        assert selector.cget('text') == '組合體'
        selector_menu = root.nametowidget(selector.cget('menu'))
        labels = [selector_menu.entrycget(i, 'label') for i in range(selector_menu.index('end') + 1)]
        assert labels[:6] == ['組合體', '箱身', '封頭', '封尾', '門', '底板']
        assert add_button.cget('text') == '新增 ▼'

        # Selecting a part is a single menu action; no second click or separate
        # Edit action exists.
        selector_menu.invoke(labels.index('門'))
        root.update_idletasks(); root.update()
        assert designer.active_part_key == 'door'
        assert not hasattr(designer, 'edit_selected_part_button')
        assert not hasattr(designer, 'delete_selected_part_button')

        # Delete lives in the same persistent selector row and becomes enabled
        # for a removable part.
        assert designer.remove_part_button.master is designer.part_selector
        assert designer.remove_part_button.winfo_manager() == 'pack'
        assert designer.remove_part_button.cget('text') == '刪除'
        assert str(designer.remove_part_button.cget('state')) == 'normal'
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass


def test_custom_mode_hides_baseline_only_settings_section():
    custom = SimpleNamespace(
        baseline_model_var=DummyVar("自訂"),
        _baseline_unknown_value="自訂",
    )
    known = SimpleNamespace(
        baseline_model_var=DummyVar("金庫型"),
        _baseline_unknown_value="自訂",
    )

    assert bridge._phase6_should_show_baseline_data(custom, "box_body", [object()]) is False
    assert bridge._phase6_should_show_baseline_data(custom, "head", []) is False
    assert bridge._phase6_should_show_baseline_data(known, "box_body", []) is True
    assert bridge._phase6_should_show_baseline_data(known, bridge.GLOBAL_CONTEXT, [object()]) is False


def test_baseline_mode_change_invalidates_box_body_page_too(monkeypatch):
    holder = SimpleNamespace(
        _settings_page_cache={
            bridge.GLOBAL_CONTEXT: object(),
            "box_body": object(),
            "head": object(),
        }
    )
    calls = []
    monkeypatch.setattr(
        bridge,
        "_phase6_invalidate_settings_page",
        lambda self, context: calls.append(context),
    )

    bridge._phase6_invalidate_corner_pages(holder)

    assert "box_body" in calls
    assert "head" in calls
    assert bridge.GLOBAL_CONTEXT not in calls


def test_phase6_box_symmetry_toggle_updates_authoritative_state():
    calls = []
    workspace = _designer_workspace("box_body", active="box_body")
    holder = SimpleNamespace(
        designer_workspace=workspace,
        v_sy=DummyVar(False),
        state=SimpleNamespace(symmetric=True),
        do_update=lambda: calls.append("update"),
    )

    bridge._phase6_on_box_symmetry_changed(holder)

    assert holder.state.symmetric is False
    assert workspace.dirty is True
    assert calls == ["update"]


def test_phase6_box_page_restores_symmetry_checkbox():
    source = Path(bridge.__file__).read_text(encoding="utf-8")
    assert 'text="對稱折彎"' in source
    assert "_phase6_on_box_symmetry_changed" in source


def test_corner_type_icon_canvas_mapping_is_vertically_flipped_for_operator_view():
    point_bottom = SimpleNamespace(x=2.0, y=0.0)
    point_top = SimpleNamespace(x=2.0, y=20.0)

    bottom_xy = gui._corner_preview_canvas_point(
        point_bottom, ox=10.0, oy=100.0, scale=2.0, span=20.0
    )
    top_xy = gui._corner_preview_canvas_point(
        point_top, ox=10.0, oy=100.0, scale=2.0, span=20.0
    )

    assert bottom_xy == pytest.approx((14.0, 60.0))
    assert top_xy == pytest.approx((14.0, 100.0))


def test_corner_type_icon_bottom_target_restores_original_vertical_orientation():
    point_bottom = SimpleNamespace(x=2.0, y=0.0)
    point_top = SimpleNamespace(x=2.0, y=20.0)

    bottom_xy = gui._corner_preview_canvas_point(
        point_bottom, ox=10.0, oy=100.0, scale=2.0, span=20.0, flip_y=False
    )
    top_xy = gui._corner_preview_canvas_point(
        point_top, ox=10.0, oy=100.0, scale=2.0, span=20.0, flip_y=False
    )

    assert bottom_xy == pytest.approx((14.0, 100.0))
    assert top_xy == pytest.approx((14.0, 60.0))


def test_corner_type_icon_target_orientation_uses_bottom_only_unflipped():
    assert gui._corner_preview_flip_y_for_target("top") is True
    assert gui._corner_preview_flip_y_for_target("top_left") is True
    assert gui._corner_preview_flip_y_for_target("top_right") is True
    assert gui._corner_preview_flip_y_for_target("bottom") is False
    assert gui._corner_preview_flip_y_for_target("bottom_left") is False
    assert gui._corner_preview_flip_y_for_target("bottom_right") is False


def test_selecting_assembly_type_rebuilds_current_box_body_settings_page(monkeypatch):
    label = bridge.ASSEMBLY_TYPE_LABELS[bridge.CornerTypeId.OVERLAY]
    workspace = _designer_workspace("box_body", "head", "tail", active="box_body")
    holder = SimpleNamespace(
        designer_workspace=workspace,
        _phase6_settings_rendering=False,
        _corner_editable=True,
        assembly_type_var=DummyVar(label),
        _phase6_assembly_type=bridge.CornerTypeId.INSERT,
        _phase6_input_snapshot={},
        _phase6_corner_state={},
        _phase6_corner_pair_same={},
        settings_context="box_body",
        do_update=lambda: None,
    )
    invalidated = []
    rendered = []
    monkeypatch.setattr(
        bridge,
        "apply_box_assembly_type_to_raw_state",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        bridge,
        "_phase6_invalidate_settings_page",
        lambda _self, context: invalidated.append(context),
    )
    monkeypatch.setattr(
        bridge,
        "_phase6_render_settings_context",
        lambda _self, context: rendered.append(context),
    )
    monkeypatch.setattr(bridge, "_phase6_rebuild_linked_endcaps", lambda _self: None)

    bridge._phase6_on_assembly_type_selected(holder)

    assert invalidated == ["head", "tail"]
    assert rendered == []
    assert holder._phase6_assembly_type is bridge.CornerTypeId.OVERLAY


def test_symmetric_box_body_fw_mirrors_by_semantic_key_after_asymmetric_extra_fold_history():
    # Repro: with one extra fold only on the left, raw index mirroring maps
    # fw_left onto d_right. Structural Phase6 rows must mirror by semantic key.
    segs = [
        {"phase6_key": "extra_left", "angle": 90, "len": 12},
        {"phase6_key": "zl1", "angle": 90, "len": 15},
        {"phase6_key": "zl2", "angle": 90, "len": 20},
        {"phase6_key": "fw_left", "angle": 90, "len": 25},
        {"phase6_key": "d_left", "core": "D", "angle": 90, "len": 246},
        {"phase6_key": "w", "core": "W", "angle": 90, "len": 396},
        {"phase6_key": "d_right", "core": "D", "angle": 90, "len": 246},
        {"phase6_key": "fw_right", "angle": 90, "len": 25},
        {"phase6_key": "zr2", "angle": 90, "len": 20},
        {"phase6_key": "zr1", "len": 15},
    ]
    active = {"X": segs}
    controls = [{"len": DummyVar(str(seg["len"]))} for seg in segs]
    controls[3]["len"].set("30")
    holder = object.__new__(bridge.Phase6BendingUI)
    holder._phase6_refreshing_controls = False
    holder.state = SimpleNamespace(
        symmetric=True,
        phase6_fold_ui_vault_key="箱身",
        phase6_thickness=2.0,
    )
    holder.controls = controls
    holder._mark_workspace_dirty = lambda: None
    holder.get_active_dict = lambda: active
    holder._active_profile_key = lambda _active: "X"
    holder.save = lambda: None
    holder.update_cb = lambda: None

    holder.apply_mirror(3, "len")

    assert controls[7]["len"].get() == "30"  # fw_right
    assert controls[6]["len"].get() == "246"  # d_right must not be touched


def test_symmetric_box_body_delete_removes_mirror_segment_too():
    segs = [
        {"phase6_key": "extra_left", "angle": 90, "len": 12},
        {"phase6_key": "fw_left", "angle": 90, "len": 25},
        {"phase6_key": "d_left", "core": True, "angle": 90, "len": 100},
        {"phase6_key": "back", "core": True, "angle": 90, "len": 500},
        {"phase6_key": "d_right", "core": True, "angle": 90, "len": 100},
        {"phase6_key": "fw_right", "angle": 90, "len": 25},
        {"phase6_key": "extra_right", "len": 12},
    ]
    active = {"X": segs}
    calls = []
    holder = SimpleNamespace(
        state=SimpleNamespace(
            symmetric=True,
            phase6_fold_ui_vault_key="箱身",
            phase6_thickness=2.0,
        ),
        _mark_workspace_dirty=lambda: None,
        save=lambda: None,
        get_active_dict=lambda: active,
        _active_profile_key=lambda _active: "X",
        render=lambda: calls.append("render"),
        update_cb=lambda: calls.append("update"),
    )

    bridge.Phase6BendingUI.remove(holder, 0)

    assert [seg.get("phase6_key") for seg in active["X"]] == [
        "fw_left", "d_left", "back", "d_right", "fw_right"
    ]
    assert calls == ["render", "update"]


def test_symmetric_delete_is_box_body_only():
    segs = [
        {"phase6_key": "extra_left", "angle": 90, "len": 12},
        {"phase6_key": "extra_right", "len": 12},
    ]
    active = {"X": segs}
    holder = SimpleNamespace(
        state=SimpleNamespace(
            symmetric=True,
            phase6_fold_ui_vault_key="封頭",
            phase6_thickness=2.0,
        ),
        _mark_workspace_dirty=lambda: None,
        save=lambda: None,
        get_active_dict=lambda: active,
        _active_profile_key=lambda _active: "X",
        render=lambda: None,
        update_cb=lambda: None,
    )

    bridge.Phase6BendingUI.remove(holder, 0)

    assert [seg.get("phase6_key") for seg in active["X"]] == ["extra_right"]



def test_selecting_assembly_type_keeps_current_box_page_alive_and_invalidates_only_endcaps(monkeypatch):
    label = bridge.ASSEMBLY_TYPE_LABELS[bridge.CornerTypeId.OVERLAY]
    workspace = _designer_workspace("box_body", "head", "tail", active="box_body")
    holder = SimpleNamespace(
        designer_workspace=workspace,
        _phase6_settings_rendering=False,
        _corner_editable=True,
        assembly_type_var=DummyVar(label),
        _phase6_assembly_type=bridge.CornerTypeId.INSERT_OVERLAY,
        _phase6_input_snapshot={},
        _phase6_corner_state={},
        _phase6_corner_pair_same={},
        settings_context="box_body",
        do_update=lambda: None,
    )
    invalidated = []
    rendered = []
    monkeypatch.setattr(bridge, "apply_box_assembly_type_to_raw_state", lambda *_a, **_k: None)
    monkeypatch.setattr(bridge, "_phase6_invalidate_settings_page", lambda _s, c: invalidated.append(c))
    monkeypatch.setattr(bridge, "_phase6_render_settings_context", lambda _s, c: rendered.append(c))
    monkeypatch.setattr(bridge, "_phase6_rebuild_linked_endcaps", lambda _self: None)

    bridge._phase6_on_assembly_type_selected(holder)

    assert invalidated == ["head", "tail"]
    assert rendered == []
    assert holder._phase6_assembly_type is bridge.CornerTypeId.OVERLAY


def test_baseline_only_setting_groups_are_not_duplicated_into_advanced_settings():
    specs = list(bridge.settings_for_context("head")) + list(bridge.settings_for_context("tail"))
    baseline = [spec for spec in specs if spec.group in settings_panel.BASELINE_SETTING_GROUPS]
    assert baseline
    assert all(spec.group not in settings_panel.ADVANCED_SETTING_GROUPS for spec in baseline)


def test_open_fold_designer_is_modal_and_blocks_main_2d_while_draft_is_open():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        window = app.fold_designer_window
        assert window is not None and window.winfo_exists()
        assert window.grab_current() == window
        assert str(window.transient()) == str(root)

        # Cancel/X destroys the draft window; Tk must release the modal grab.
        window.event_generate("<Escape>")
        # Escape is not necessarily bound; use protocol-equivalent close path.
        window.destroy()
        app.fold_designer_window = None
        app.fold_designer_app = None
        root.update_idletasks(); root.update()
        assert root.grab_current() is None
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


def test_box_symmetry_checkbox_lives_in_fold_editor_not_right_settings_page():
    settings_source = Path(settings_panel.__file__).read_text(encoding="utf-8")
    source = Path(bridge.__file__).read_text(encoding="utf-8")
    bending_start = source.index("class Phase6BendingUI")
    bending_end = source.index("class Phase6FoldDesignerApp", bending_start)
    bending_source = source[bending_start:bending_end]

    assert "_phase6_build_box_symmetry_settings" not in settings_source
    assert 'text="對稱折彎"' in bending_source
    assert "phase6_symmetry" in bending_source


def test_head_tail_shared_endcap_settings_use_one_authoritative_key_set():
    specs = {spec.key: spec for spec in bridge.settings_for_context("head")}
    tail_specs = {spec.key: spec for spec in bridge.settings_for_context("tail")}
    for key in ("yl1", "yr1", "ytop1", "ybottom1", "hang_hole_r", "sq_width", "sq_height"):
        assert key in specs and key in tail_specs
        assert specs[key] is tail_specs[key]
        assert tuple(specs[key].contexts) == ("head", "tail")

    assert "bottom_hole_r" not in specs
    assert "bottom_hole_r" in tail_specs


def _assembly_snapshot(type_id):
    return {
        "w": 400,
        "h": 600,
        "d": 250,
        "t": 2,
        "fw": 25,
        "yl1": 15,
        "yr1": 15,
        "ytop1": 16,
        "ybottom1": 15,
        "assembly_type": type_id.value,
    }


def test_overlay_endcaps_use_one_flat_x_span_with_no_left_or_right_bends():
    snapshot = _assembly_snapshot(bridge.CornerTypeId.OVERLAY)

    for part_key in ("head", "tail"):
        profiles = bridge.build_endcap_xy_profiles(snapshot, part_key=part_key)
        x_rows = profiles["X"]
        assert len(x_rows) == 1
        assert x_rows[0].get("phase6_key") == "endcap_w_flat"
        assert "angle" not in x_rows[0]

        # OVERLAY has no left/right X folds, so the flat endcap material span
        # is the finished box width itself.  The 1.5T bottom EXTRA_CUT changes
        # only corner CUTTING geometry; it must not inflate the whole X span.
        assert x_rows[0]["len"] == pytest.approx(snapshot["w"])


def test_insert_and_insert_overlay_keep_existing_endcap_x_fold_topology():
    for type_id in (bridge.CornerTypeId.INSERT, bridge.CornerTypeId.INSERT_OVERLAY):
        snapshot = _assembly_snapshot(type_id)
        profiles = bridge.build_endcap_xy_profiles(snapshot, part_key="head")
        assert [row.get("phase6_key") for row in profiles["X"]] == [
            "yl1", "endcap_w_core", "yr1"
        ]
        assert sum("angle" in row for row in profiles["X"]) == 2


def test_overlay_endcap_editor_hides_x_axis_and_keeps_y_axis():
    snapshot = _assembly_snapshot(bridge.CornerTypeId.OVERLAY)
    assert bridge._phase6_fold_tabs_for_part(snapshot, "head") == ["Y"]
    assert bridge._phase6_fold_tabs_for_part(snapshot, "tail") == ["Y"]

    insert = _assembly_snapshot(bridge.CornerTypeId.INSERT)
    assert bridge._phase6_fold_tabs_for_part(insert, "head") is None
    assert bridge._phase6_fold_tabs_for_part(insert, "tail") is None


def test_main_2d_overlay_builds_flat_x_profile_even_without_3d_workspace():
    values = _assembly_snapshot(bridge.CornerTypeId.OVERLAY)
    profiles = gui._endcap_profiles_for_assembly(
        values, None, bridge.CornerTypeId.OVERLAY, "head"
    )
    assert [row.get("phase6_key") for row in profiles["X"]] == ["endcap_w_flat"]
    assert all("angle" not in row for row in profiles["X"])
    assert profiles["Y"]


def test_main_2d_switching_from_overlay_to_wrap_overlay_restores_normal_x_without_corner_enum_projection():
    overlay_values = _assembly_snapshot(bridge.CornerTypeId.OVERLAY)
    overlay_profiles = gui._endcap_profiles_for_assembly(
        overlay_values, None, bridge.CornerTypeId.OVERLAY, "head"
    )
    wrap_values = _assembly_snapshot(bridge.CornerTypeId.INSERT)
    wrap_values["assembly_type"] = "WRAP_OVERLAY"
    restored = gui._endcap_profiles_for_assembly(
        wrap_values, overlay_profiles, "WRAP_OVERLAY", "head"
    )
    assert [row.get("phase6_key") for row in restored["X"]] == [
        "yl1", "endcap_w_core", "yr1"
    ]


def test_main_2d_switching_back_from_overlay_restores_normal_x_fold_topology():
    overlay_values = _assembly_snapshot(bridge.CornerTypeId.OVERLAY)
    overlay_profiles = gui._endcap_profiles_for_assembly(
        overlay_values, None, bridge.CornerTypeId.OVERLAY, "head"
    )
    insert_values = _assembly_snapshot(bridge.CornerTypeId.INSERT)
    restored = gui._endcap_profiles_for_assembly(
        insert_values, overlay_profiles, bridge.CornerTypeId.INSERT, "head"
    )
    assert [row.get("phase6_key") for row in restored["X"]] == [
        "yl1", "endcap_w_core", "yr1"
    ]


def test_overlay_final_scene_contains_no_x_axis_bend_lines():
    from ae_engine.contracts import EndCapPartSpec
    from ae_engine.manufacturing_api import ManufacturingContext, build_part_scene
    from ae_engine.sheetmetal_drawing import LinePrimitive

    values = _assembly_snapshot(bridge.CornerTypeId.OVERLAY)
    profiles = bridge.build_endcap_xy_profiles(values, part_key="head")
    spec = EndCapPartSpec(
        width=values["w"], depth=values["d"], thickness=values["t"],
        frame_width=values["fw"], fold_left=values["yl1"], fold_right=values["yr1"],
        fold_top=values["ytop1"], fold_bottom=values["ybottom1"],
        fold_profile_x=bridge.profile_to_fold_segments(profiles["X"]),
        fold_profile_y=bridge.profile_to_fold_segments(profiles["Y"]),
    )
    scene = build_part_scene(spec, ManufacturingContext())
    bends = [
        p for p in scene.primitives
        if isinstance(p, LinePrimitive) and str(p.layer).upper() == "BEND"
    ]
    assert bends
    # X-profile folds would be vertical lines (constant X). OVERLAY must have
    # only Y-profile bends, therefore every final BEND is horizontal.
    assert all(abs(float(p.p1.y) - float(p.p2.y)) <= 1e-9 for p in bends)


def test_box_assembly_combobox_selection_updates_joint_graph_without_rewriting_corner_state(monkeypatch):
    label = bridge.ASSEMBLY_TYPE_LABELS[bridge.CornerTypeId.OVERLAY]
    workspace = _designer_workspace("box_body", "head", "tail", active="box_body")
    original_corner_state = {"head": {"top": {"type": "MANUAL"}}}
    holder = SimpleNamespace(
        designer_workspace=workspace,
        _phase6_settings_rendering=False,
        _corner_editable=True,
        assembly_type_var=DummyVar(label),
        _phase6_assembly_type=bridge.CornerTypeId.INSERT_OVERLAY,
        _phase6_input_snapshot={},
        _phase6_corner_state=original_corner_state,
        _phase6_corner_pair_same={},
        settings_context="box_body",
        do_update=lambda: None,
    )
    sync_calls = []
    legacy_apply_calls = []

    monkeypatch.setattr(
        bridge,
        "_phase6_sync_joint_state_for_intent",
        lambda self, type_id: sync_calls.append(type_id) or (),
    )
    monkeypatch.setattr(
        bridge,
        "apply_box_assembly_type_to_raw_state",
        lambda *args, **kwargs: legacy_apply_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(bridge, "_phase6_invalidate_settings_page", lambda *_a: None)
    monkeypatch.setattr(bridge, "_phase6_rebuild_linked_endcaps", lambda *_a: None)

    bridge._phase6_on_assembly_type_selected(holder)

    assert sync_calls == [bridge.CornerTypeId.OVERLAY]
    assert legacy_apply_calls == []
    assert holder._phase6_input_snapshot["assembly_type"] == bridge.CornerTypeId.OVERLAY.value
    assert holder._phase6_corner_state is original_corner_state
    assert workspace.dirty is True


def test_main_gui_explicit_overlay_selection_updates_graph_without_bottom_corner_reset():
    app = object.__new__(gui.BoxCalculatorGUI)
    app.baseline_var = DummyVar("自訂")
    app._current_box_assembly_type = lambda: bridge.CornerTypeId.OVERLAY
    calls = []
    app._set_box_assembly_type = lambda type_id, **kwargs: calls.append((type_id, kwargs))

    gui.BoxCalculatorGUI.on_box_assembly_changed(app)

    assert calls == [
        (bridge.CornerTypeId.OVERLAY, {"reset_bottom_defaults": False})
    ]


def test_symmetric_unpaired_extra_fold_never_mirrors_into_structural_fw_or_d_row():
    segs = [
        {"angle": 90, "len": 12},  # legacy/operator-added left-only fold, no semantic key
        {"phase6_key": "zl1", "angle": 90, "len": 15},
        {"phase6_key": "zl2", "angle": 90, "len": 20},
        {"phase6_key": "fw_left", "angle": 90, "len": 25},
        {"phase6_key": "d_left", "core": "D", "angle": 90, "len": 246},
        {"phase6_key": "w", "core": "W", "angle": 90, "len": 396},
        {"phase6_key": "d_right", "core": "D", "angle": 90, "len": 246},
        {"phase6_key": "fw_right", "angle": 90, "len": 25},
        {"phase6_key": "zr2", "angle": 90, "len": 20},
        {"phase6_key": "zr1", "len": 15},
    ]
    active = {"X": segs}
    controls = [{"len": DummyVar(str(seg["len"]))} for seg in segs]
    controls[0]["len"].set("18")
    holder = object.__new__(bridge.Phase6BendingUI)
    holder._phase6_refreshing_controls = False
    holder.state = SimpleNamespace(
        symmetric=True,
        phase6_fold_ui_vault_key="箱身",
        phase6_thickness=2.0,
    )
    holder.controls = controls
    holder._mark_workspace_dirty = lambda: None
    holder.get_active_dict = lambda: active
    holder._active_profile_key = lambda _active: "X"
    holder.save = lambda: None
    holder.update_cb = lambda: None

    holder.apply_mirror(0, "len")

    assert controls[-1]["len"].get() == "15"  # zr1 must not be overwritten
    assert controls[7]["len"].get() == "25"   # fw_right must not be overwritten


def test_symmetric_box_body_angle_mirrors_by_semantic_boundary_after_asymmetric_history():
    segs = [
        {"phase6_key": "extra_left", "angle": 90, "len": 12},
        {"phase6_key": "zl1", "angle": 90, "len": 15},
        {"phase6_key": "zl2", "angle": 90, "len": 20},
        {"phase6_key": "fw_left", "angle": 90, "len": 25},
        {"phase6_key": "d_left", "core": "D", "angle": 90, "len": 246},
        {"phase6_key": "w", "core": "W", "angle": 90, "len": 396},
        {"phase6_key": "d_right", "core": "D", "angle": 90, "len": 246},
        {"phase6_key": "fw_right", "angle": 90, "len": 25},
        {"phase6_key": "zr2", "angle": 90, "len": 20},
        {"phase6_key": "zr1", "len": 15},
    ]
    active = {"X": segs}
    controls = []
    for i, seg in enumerate(segs):
        ctrl = {"len": DummyVar(str(seg["len"]))}
        if "angle" in seg:
            ctrl["angle"] = DummyVar(str(seg["angle"]))
        controls.append(ctrl)
    controls[3]["angle"].set("45")  # boundary fw_left -> d_left
    holder = object.__new__(bridge.Phase6BendingUI)
    holder._phase6_refreshing_controls = False
    holder.state = SimpleNamespace(
        symmetric=True,
        phase6_fold_ui_vault_key="箱身",
        phase6_thickness=2.0,
    )
    holder.controls = controls
    holder._mark_workspace_dirty = lambda: None
    holder.get_active_dict = lambda: active
    holder._active_profile_key = lambda _active: "X"
    holder.save = lambda: None
    holder.update_cb = lambda: None

    holder.apply_mirror(3, "angle")

    assert controls[6]["angle"].get() == "45"  # boundary d_right -> fw_right
    assert controls[5]["angle"].get() == "90"  # W boundary must not be touched
