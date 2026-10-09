# -*- coding: utf-8 -*-
"""Application compatibility orchestration for the Phase6 Part Session.

Phase6PartSessionOwner owns activation/save sequencing and compatibility effect
ordering only. Navigation/workspace identity, project persistence, update
scheduling, rendering and Settings semantics remain with their existing
canonical owners. Manufacturing formula ownership remains in the existing
canonical modules; geometry and DXF truth stay outside this owner. The Bridge
keeps narrow compatibility delegates.
"""
from __future__ import annotations

from typing import Any


class Phase6PartSessionOwner:
    """Own application-level part activation/save compatibility orchestration."""

    def __init__(self):
        self.app = None

    def bind_application(self, host: Any):
        self.app = host
        return self

    def save_current_part(self, notify=True):
        app = self.app

        bridge = __import__('fold_designer_bridge')
        if app.designer_workspace.switching:
            return
        key = app.designer_workspace.active_part
        if not key:
            return
        if app.designer_workspace.custom_part(key) is not None:
            app.designer_workspace.stash_profiles(key, {axis:bridge.clone_profile(app.state.profiles.get(axis,())) for axis in ("X","Y")})
            return
        try:
            app.bend_ui.save()
        except Exception:
            return
        bridge._phase6_replace_mapping(app, '_phase6_box_whd', {'w': bridge.original.get_int(app.v_w.get()), 'h': bridge.original.get_int(app.v_h.get()), 'd': bridge.original.get_int(app.v_d.get())})
        if bridge._phase6_is_box_body_physical_piece_key(key):
            profiles = {'X': bridge.clone_profile(app.state.profiles.get('X', [])), 'Y': bridge.clone_profile(app.state.profiles.get('Y', []))}
            if bridge._phase6_is_side_back_editable_piece_key(key):
                bridge._phase6_commit_box_body_physical_piece_profile(app, key, profiles, notify=notify)
            else:
                app.designer_workspace.stash_profiles(key, profiles)
            return
        if bridge._phase6_is_derived_physical_part_key(key):
            bridge._phase6_sync_authoritative_derived_parts(app)
            return
        if key == 'box_body':
            if getattr(app, '_phase6_sync_ready', False):
                app._sync_dwd_with_top_whd()
            values = bridge.read_box_body_profile(app.state.profiles_vault['箱身'], app._phase6_input_snapshot)
            values['h'] = app._phase6_box_whd['h']
            if app._phase6_input_snapshot.get('receiving_quantity_box') and app._phase6_input_snapshot.get('active_mode') == 'quantity':
                values.update({axis: float(app._phase6_input_snapshot['receiving_quantity_box'][axis]) for axis in ('w', 'h', 'd')})
            bridge._phase6_store_editor_values(app, values, notify=notify)
            app._phase6_input_snapshot['endcap_fw'] = bridge.deepcopy(app._phase6_endcap_fw_state)
            bridge._phase6_rebuild_linked_endcaps(app)
            return
        profiles = {'X': bridge.clone_profile(app.state.profiles.get('X', [])), 'Y': bridge.clone_profile(app.state.profiles.get('Y', []))}
        app.designer_workspace.stash_profiles(key, profiles)
        if key in bridge.ENDCAP_FW_PARTS:
            x = {str(seg.get('phase6_key')): seg for seg in profiles.get('X', ()) if seg.get('phase6_key')}
            y = {str(seg.get('phase6_key')): seg for seg in profiles.get('Y', ()) if seg.get('phase6_key')}
            required_x = {'yl1', 'endcap_w_core', 'yr1'}
            flat_x = len(profiles.get('X', ())) == 1 and profiles['X'][0].get('phase6_key') == 'endcap_w_flat'
            if not required_x.issubset(x) and (not flat_x):
                raise ValueError('封頭/封尾 X 折彎資料不完整')
            fw_item = app._phase6_endcap_fw_state.setdefault(key, {'follow_box': True, 'value': bridge._num(app._phase6_input_snapshot.get('fw', 25), 25)})
            if 'fw' in y:
                edited_fw = bridge.engine_segment_length_to_ui(y['fw']) if bridge.cabinet_family_policy.endcap_fw_profile_uses_material_dimensions(app._phase6_input_snapshot) else bridge._ui_len(y['fw'].get('len'))
                effective_before = bridge.resolve_endcap_fw(app._phase6_input_snapshot, key, state=app._phase6_endcap_fw_state)
                if abs(float(edited_fw) - float(effective_before)) > 1e-09:
                    bridge.commit_endcap_fw(app._phase6_endcap_fw_state, key, edited_fw, box_fw=bridge._num(app._phase6_input_snapshot.get('fw', 25), 25))
            app._phase6_input_snapshot['endcap_fw'] = bridge.deepcopy(app._phase6_endcap_fw_state)
            canonical_y_keys = {'ytop1', 'fw', 'endcap_d_core', 'ybottom1'}
            if canonical_y_keys.issubset(y):
                values = bridge.read_endcap_xy_profiles(profiles, app._phase6_input_snapshot)
                values.pop('fw', None)
            else:
                values = {} if flat_x else {'yl1': bridge._ui_len(x['yl1'].get('len')), 'yr1': bridge._ui_len(x['yr1'].get('len'))}
            if app._phase6_input_snapshot.get('receiving_quantity_box') and app._phase6_input_snapshot.get('active_mode') == 'quantity':
                values.update({axis: float(app._phase6_input_snapshot['receiving_quantity_box'][axis]) for axis in ('w', 'h', 'd')})
            bridge._phase6_store_editor_values(app, values, notify=notify)
            if 'w' in values:
                app._phase6_box_whd['w'] = float(values['w']) if app._phase6_input_snapshot.get('receiving_quantity_box') else bridge.original.get_int(values['w'])
            if 'd' in values:
                app._phase6_box_whd['d'] = float(values['d']) if app._phase6_input_snapshot.get('receiving_quantity_box') else bridge.original.get_int(values['d'])
            w_text = str(app._phase6_box_whd['w'])
            d_text = str(app._phase6_box_whd['d'])
            if app.v_w.get() != w_text:
                app.v_w.set(w_text)
            if app.v_d.get() != d_text:
                app.v_d.set(d_text)
            bridge._phase6_rebuild_linked_endcaps(app)
            legacy = bridge.build_endcap_profile(app._phase6_input_snapshot)
            app.state.profiles_vault['封頭'] = bridge.clone_profile(legacy)
            app.state.profiles_vault['封尾'] = bridge.clone_profile(legacy)
        else:
            bridge._phase6_store_editor_values(app, bridge.read_standard_part_profiles(key, profiles, app._phase6_input_snapshot), notify=notify)

    def activate_part(self, key, initial=False):
        app = self.app

        bridge = __import__('fold_designer_bridge')
        navigation = bridge._phase6_workspace_navigation(app)
        if not navigation.has_part(key):
            return
        from gui_modules.application.custom_part_controls import build_custom_part_editor
        custom = getattr(app.designer_workspace, "custom_part", lambda _: None)(key)
        custom_frame = getattr(app, "_custom_part_editor", None)
        if custom is not None:
            before_signature=bridge._phase6_manufacturing_state_signature(app)
            plan = navigation.plan_activation(key, initial=initial, leaving_non_single_view=True)
            if plan.save_outgoing:
                self.save_current_part()
            pending = getattr(app, "_job", None)
            if pending:
                app.root.after_cancel(pending)
                app._job = None
            bridge._phase6_clear_navigation_residue(app)
            bridge._phase6_hide_corner_data_canvas(app)
            navigation.begin_activation(plan)
            navigation.finish_activation()
            app._phase6_3d_display_mode = "single"
            if custom_frame is not None:
                custom_frame.destroy()
            for name in ("input_content_host", "assembly_parts_panel", "corner_data_panel", "settings_center"):
                widget = getattr(app, name, None)
                if widget is not None and widget.winfo_manager():
                    widget.pack_forget()
            from phase6_custom_fold_profiles import build_custom_part_profiles, custom_part_spec
            from ae_engine.custom_fold_manufacturing import custom_fold_feature_context
            def install_profiles(reset=False):
                snapshot={**app._phase6_input_snapshot,**app.designer_workspace.snapshot()}
                profiles=None if reset else app.designer_workspace.profiles_for(key)
                profiles=profiles or build_custom_part_profiles(snapshot,key)
                app.designer_workspace.stash_profiles(key,profiles)
                app.state.profiles.update({axis:bridge.clone_profile(profiles[axis]) for axis in ("X","Y")})
                app.state.struct_mode="standard"
                app.state.phase6_fold_ui_profiles=None
                app.state.phase6_fold_ui_tabs=[app.designer_workspace.custom_part(key)["fold_axis"]]
                app.state.active_bend=app.state.phase6_fold_ui_tabs[0]
                app.state.enable_y=True
                app._phase6_input_snapshot["custom_parts"]=app.designer_workspace.snapshot()["custom_parts"]
                app._load_part_holes(key)
            install_profiles()
            canvas = app.renderer.canvas.get_tk_widget()
            canvas.pack(fill=bridge.original.tk.BOTH,expand=True)
            prior_metadata=dict(custom)
            def changed():
                nonlocal prior_metadata
                before=prior_metadata
                current=app.designer_workspace.custom_part(key)
                geometry_changed=any(current[name]!=before[name] for name in ("fold_axis","transverse_length"))
                app.part_var.set(current["display_name"])
                if geometry_changed:
                    install_profiles(reset=True)
                app._phase6_input_snapshot["custom_parts"]=app.designer_workspace.snapshot()["custom_parts"]
                prior_metadata=dict(current)
                app._refresh_part_buttons()
                if geometry_changed:
                    app.submit_update_intent("geometry",commit=True)
                else:
                    bridge._phase6_publish_live_state(app,force=True)
            def holes():
                host=getattr(app._scene_query_callback,"__self__",None)
                if host is None or not hasattr(host,"_open_unified_hole_editor"):
                    raise ValueError("目前未連接既有 Hole Editor")
                snapshot={**app._phase6_input_snapshot,**app.designer_workspace.snapshot()}
                features=app.designer_workspace.features_for(key)
                spec=custom_part_spec(snapshot,key,profiles=app.designer_workspace.profiles_for(key))
                surface,width,height,guide=custom_fold_feature_context(spec)
                def commit():
                    app.designer_workspace.stash_features(key,features)
                    app._load_part_holes(key)
                    app.submit_update_intent("geometry",commit=True)
                win=host._open_unified_hole_editor(key,app.designer_workspace.custom_part(key)["display_name"],
                    surface,width,height,reference_guide=guide,feature_list_override=features,
                    sync_callback=commit)
                return win or getattr(host,"last_unified_hole_editor",None)
            frame = build_custom_part_editor(canvas.master,descriptor=custom,
                update_part=lambda **values:navigation.update_custom_part(key,**values),
                on_changed=changed,open_holes=holes)
            frame.pack(fill=bridge.original.tk.X,before=canvas)
            app._custom_part_editor=frame
            app.part_var.set(custom["display_name"])
            app._refresh_part_buttons()
            app.remove_part_button.configure(state="normal")
            after_signature=bridge._phase6_manufacturing_state_signature(app)
            app.submit_update_intent("display" if before_signature==after_signature else "geometry",commit=True)
            return
        if custom_frame is not None:
            custom_frame.destroy()
            app._custom_part_editor = None
        bridge._phase6_clear_navigation_residue(app)
        bridge._phase6_hide_corner_data_canvas(app)
        if bridge._phase6_is_box_body_physical_piece_key(key):
            app._phase6_box_body_active_piece_key = str(key)
        before_signature = None
        if not initial:
            try:
                before_signature = bridge._phase6_manufacturing_state_signature(app)
            except Exception:
                before_signature = None
        was_non_single = str(getattr(app, '_phase6_3d_display_mode', 'single') or 'single') != 'single'
        plan = navigation.plan_activation(key, initial=initial, leaving_non_single_view=was_non_single)
        if not initial:
            app._phase6_3d_display_mode = 'single'
            diagnostics = getattr(app, 'assembly_diagnostics_frame', None)
            if diagnostics is not None and diagnostics.winfo_manager():
                diagnostics.pack_forget()
        if not initial and getattr(app, '_phase6_pending_settings', None):
            app.flush_pending_settings()
        if plan.noop:
            return
        pending = getattr(app, '_job', None)
        if pending:
            try:
                app.root.after_cancel(pending)
            except Exception:
                pass
            app._job = None
        if plan.save_outgoing:
            self.save_current_part()
            pending = getattr(app, '_job', None)
            if pending:
                try:
                    app.root.after_cancel(pending)
                except Exception:
                    pass
                app._job = None
        bridge._phase6_mount_shared_content(app, 'single')
        canvas_widget = app.renderer.canvas.get_tk_widget()
        navigation.begin_activation(plan)
        try:
            bridge._navigation_view_project_active_part_selector(app, key=key, label=bridge._phase6_part_label('box_body') if bridge._phase6_is_box_body_physical_piece_key(key) else bridge._phase6_part_label(key), removable=key != 'box_body' and (not bridge._phase6_is_derived_physical_part_key(key)), refresh_part_button_states=getattr(app, '_refresh_part_button_states', None))
            if key == 'box_body':
                app.state.phase6_fold_ui_profiles = {'X': app.state.profiles_vault['箱身']}
                app.state.phase6_fold_ui_tabs = ['X']
                app.state.phase6_fold_ui_vault_key = '箱身'
                app.state.struct_mode = 'vault'
                app.state.active_bend = 'X'
                target_mode = 'vault'
            else:
                app.state.phase6_fold_ui_profiles = None
                app.state.phase6_fold_ui_vault_key = None
                if key in {'head', 'tail'}:
                    default_profiles = bridge.build_endcap_xy_profiles(app._phase6_input_snapshot, part_key=key)
                elif bridge._phase6_is_derived_physical_part_key(key):
                    default_profiles = app.designer_workspace.profiles_for(key, {}) or {}
                else:
                    default_profiles = bridge.build_standard_part_profiles(app._phase6_input_snapshot, key)
                profiles = app.designer_workspace.profiles_for(key)
                if profiles is None:
                    profiles = default_profiles
                    navigation.stash_profiles(key, profiles)
                app.state.profiles['X'] = bridge.clone_profile(profiles.get('X', []))
                app.state.profiles['Y'] = bridge.clone_profile(profiles.get('Y', []))
                app.state.phase6_fold_ui_tabs = bridge._phase6_fold_tabs_for_part(app._phase6_input_snapshot, key)
                app.state.struct_mode = 'standard'
                app.state.active_bend = app.state.phase6_fold_ui_tabs[0] if app.state.phase6_fold_ui_tabs else 'X'
                app.state.enable_y = bool(app.state.profiles['Y'])
                if bool(app.v_ey.get()) != app.state.enable_y:
                    app.v_ey.set(app.state.enable_y)
                target_mode = 'standard'
            if app.v_mode.get() != target_mode:
                app.v_mode.set(target_mode)
            elif target_mode == 'standard' and app.state.phase6_fold_ui_tabs is None and (list(getattr(app.bend_ui, 'tabs', ())) == ['X', 'Y']):
                try:
                    if app.bend_ui.nb.index('current') != 0:
                        app.bend_ui.nb.select(0)
                except Exception:
                    pass
                app.bend_ui.refresh_active_profile()
            else:
                app.bend_ui.rebuild_tabs()
            for var, value in ((app.v_w, app._phase6_box_whd['w']), (app.v_h, app._phase6_box_whd['h']), (app.v_d, app._phase6_box_whd['d'])):
                text = str(value)
                if var.get() != text:
                    var.set(text)
            app._load_part_holes(key)
        finally:
            navigation.finish_activation()
        bridge._navigation_view_finalize_single_part_layout(app, settings_context='box_body' if bridge._phase6_is_box_body_physical_piece_key(key) else key, render_settings_context=lambda context: bridge._phase6_render_settings_context(app, context), pack_right_panel=lambda widget: bridge._phase6_pack_right_panel_above_canvas(app, widget), render_active_drawing_edge_controls=lambda: bridge._phase6_render_active_drawing_edge_controls(app), tk_both=bridge.original.tk.BOTH)
        try:
            after_signature = bridge._phase6_manufacturing_state_signature(app)
        except Exception:
            after_signature = None
        reason = 'display' if not initial and before_signature is not None and (before_signature == after_signature) else 'geometry'
        submit = getattr(app, 'submit_update_intent', None)
        if callable(submit):
            submit(reason, commit=True)
        else:
            app.do_update()
        bridge._phase6_refresh_persistent_structure_controls(app)
        bridge._phase6_refresh_box_body_piece_selector(app)
        bridge._phase6_refresh_receiving_set_bay_control(app)
        bridge._phase6_refresh_back_panel_mode_control(app)
        bridge._phase6_refresh_content_switch(app)