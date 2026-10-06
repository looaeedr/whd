# -*- coding: utf-8 -*-
"""Part-session orchestration extracted from the Phase6 Fold Designer bridge.

This owner keeps part activation/save sequencing together.  Manufacturing
formula ownership remains in the existing canonical modules; the Bridge only
keeps compatibility delegates.
"""
from __future__ import annotations

from typing import Any


class Phase6PartSessionOwner:
    """Own part activation/save session orchestration for the Phase6 editor."""

    def __init__(self, app: Any):
        self.app = app

    def save_current_part(self, notify=True):
        self = self.app

        bridge = __import__('fold_designer_bridge')
        if self.designer_workspace.switching:
            return
        key = self.designer_workspace.active_part
        if not key:
            return
        try:
            self.bend_ui.save()
        except Exception:
            return
        bridge._phase6_replace_mapping(self, '_phase6_box_whd', {'w': bridge.original.get_int(self.v_w.get()), 'h': bridge.original.get_int(self.v_h.get()), 'd': bridge.original.get_int(self.v_d.get())})
        if bridge._phase6_is_box_body_physical_piece_key(key):
            profiles = {'X': bridge.clone_profile(self.state.profiles.get('X', [])), 'Y': bridge.clone_profile(self.state.profiles.get('Y', []))}
            if bridge._phase6_is_side_back_editable_piece_key(key):
                bridge._phase6_commit_box_body_physical_piece_profile(self, key, profiles, notify=notify)
            else:
                self.designer_workspace.stash_profiles(key, profiles)
            return
        if bridge._phase6_is_derived_physical_part_key(key):
            bridge._phase6_sync_authoritative_derived_parts(self)
            return
        if key == 'box_body':
            if getattr(self, '_phase6_sync_ready', False):
                self._sync_dwd_with_top_whd()
            values = bridge.read_box_body_profile(self.state.profiles_vault['箱身'], self._phase6_input_snapshot)
            values['h'] = self._phase6_box_whd['h']
            bridge._phase6_store_editor_values(self, values, notify=notify)
            self._phase6_input_snapshot['endcap_fw'] = bridge.deepcopy(self._phase6_endcap_fw_state)
            bridge._phase6_rebuild_linked_endcaps(self)
            return
        profiles = {'X': bridge.clone_profile(self.state.profiles.get('X', [])), 'Y': bridge.clone_profile(self.state.profiles.get('Y', []))}
        self.designer_workspace.stash_profiles(key, profiles)
        if key in bridge.ENDCAP_FW_PARTS:
            x = {str(seg.get('phase6_key')): seg for seg in profiles.get('X', ()) if seg.get('phase6_key')}
            y = {str(seg.get('phase6_key')): seg for seg in profiles.get('Y', ()) if seg.get('phase6_key')}
            required_x = {'yl1', 'endcap_w_core', 'yr1'}
            flat_x = len(profiles.get('X', ())) == 1 and profiles['X'][0].get('phase6_key') == 'endcap_w_flat'
            if not required_x.issubset(x) and (not flat_x):
                raise ValueError('封頭/封尾 X 折彎資料不完整')
            fw_item = self._phase6_endcap_fw_state.setdefault(key, {'follow_box': True, 'value': bridge._num(self._phase6_input_snapshot.get('fw', 25), 25)})
            if 'fw' in y:
                edited_fw = bridge.engine_segment_length_to_ui(y['fw']) if bridge.cabinet_family_policy.endcap_fw_profile_uses_material_dimensions(self._phase6_input_snapshot) else bridge._ui_len(y['fw'].get('len'))
                effective_before = bridge.resolve_endcap_fw(self._phase6_input_snapshot, key, state=self._phase6_endcap_fw_state)
                if abs(float(edited_fw) - float(effective_before)) > 1e-09:
                    bridge.commit_endcap_fw(self._phase6_endcap_fw_state, key, edited_fw, box_fw=bridge._num(self._phase6_input_snapshot.get('fw', 25), 25))
            self._phase6_input_snapshot['endcap_fw'] = bridge.deepcopy(self._phase6_endcap_fw_state)
            canonical_y_keys = {'ytop1', 'fw', 'endcap_d_core', 'ybottom1'}
            if canonical_y_keys.issubset(y):
                values = bridge.read_endcap_xy_profiles(profiles, self._phase6_input_snapshot)
                values.pop('fw', None)
            else:
                values = {} if flat_x else {'yl1': bridge._ui_len(x['yl1'].get('len')), 'yr1': bridge._ui_len(x['yr1'].get('len'))}
            bridge._phase6_store_editor_values(self, values, notify=notify)
            if 'w' in values:
                self._phase6_box_whd['w'] = bridge.original.get_int(values['w'])
            if 'd' in values:
                self._phase6_box_whd['d'] = bridge.original.get_int(values['d'])
            w_text = str(self._phase6_box_whd['w'])
            d_text = str(self._phase6_box_whd['d'])
            if self.v_w.get() != w_text:
                self.v_w.set(w_text)
            if self.v_d.get() != d_text:
                self.v_d.set(d_text)
            bridge._phase6_rebuild_linked_endcaps(self)
            legacy = bridge.build_endcap_profile(self._phase6_input_snapshot)
            self.state.profiles_vault['封頭'] = bridge.clone_profile(legacy)
            self.state.profiles_vault['封尾'] = bridge.clone_profile(legacy)
        else:
            bridge._phase6_store_editor_values(self, bridge.read_standard_part_profiles(key, profiles, self._phase6_input_snapshot), notify=notify)

    def activate_part(self, key, initial=False):
        self = self.app

        bridge = __import__('fold_designer_bridge')
        navigation = bridge._phase6_workspace_navigation(self)
        if not navigation.has_part(key):
            return
        bridge._phase6_clear_navigation_residue(self)
        bridge._phase6_hide_corner_data_canvas(self)
        if bridge._phase6_is_box_body_physical_piece_key(key):
            self._phase6_box_body_active_piece_key = str(key)
        before_signature = None
        if not initial:
            try:
                before_signature = bridge._phase6_manufacturing_state_signature(self)
            except Exception:
                before_signature = None
        was_non_single = str(getattr(self, '_phase6_3d_display_mode', 'single') or 'single') != 'single'
        plan = navigation.plan_activation(key, initial=initial, leaving_non_single_view=was_non_single)
        if not initial:
            self._phase6_3d_display_mode = 'single'
            diagnostics = getattr(self, 'assembly_diagnostics_frame', None)
            if diagnostics is not None and diagnostics.winfo_manager():
                diagnostics.pack_forget()
        if not initial and getattr(self, '_phase6_pending_settings', None):
            self.flush_pending_settings()
        if plan.noop:
            return
        pending = getattr(self, '_job', None)
        if pending:
            try:
                self.root.after_cancel(pending)
            except Exception:
                pass
            self._job = None
        if plan.save_outgoing:
            self.save_current_part()
            pending = getattr(self, '_job', None)
            if pending:
                try:
                    self.root.after_cancel(pending)
                except Exception:
                    pass
                self._job = None
        bridge._phase6_mount_shared_content(self, 'single')
        canvas_widget = self.renderer.canvas.get_tk_widget()
        navigation.begin_activation(plan)
        try:
            bridge._navigation_view_project_active_part_selector(self, key=key, label=bridge._phase6_part_label('box_body') if bridge._phase6_is_box_body_physical_piece_key(key) else bridge._phase6_part_label(key), removable=key != 'box_body' and (not bridge._phase6_is_derived_physical_part_key(key)), refresh_part_button_states=getattr(self, '_refresh_part_button_states', None))
            if key == 'box_body':
                self.state.phase6_fold_ui_profiles = {'X': self.state.profiles_vault['箱身']}
                self.state.phase6_fold_ui_tabs = ['X']
                self.state.phase6_fold_ui_vault_key = '箱身'
                self.state.struct_mode = 'vault'
                self.state.active_bend = 'X'
                target_mode = 'vault'
            else:
                self.state.phase6_fold_ui_profiles = None
                self.state.phase6_fold_ui_vault_key = None
                if key in {'head', 'tail'}:
                    default_profiles = bridge.build_endcap_xy_profiles(self._phase6_input_snapshot, part_key=key)
                elif bridge._phase6_is_derived_physical_part_key(key):
                    default_profiles = self.designer_workspace.profiles_for(key, {}) or {}
                else:
                    default_profiles = bridge.build_standard_part_profiles(self._phase6_input_snapshot, key)
                profiles = self.designer_workspace.profiles_for(key)
                if profiles is None:
                    profiles = default_profiles
                    navigation.stash_profiles(key, profiles)
                self.state.profiles['X'] = bridge.clone_profile(profiles.get('X', []))
                self.state.profiles['Y'] = bridge.clone_profile(profiles.get('Y', []))
                self.state.phase6_fold_ui_tabs = bridge._phase6_fold_tabs_for_part(self._phase6_input_snapshot, key)
                self.state.struct_mode = 'standard'
                self.state.active_bend = self.state.phase6_fold_ui_tabs[0] if self.state.phase6_fold_ui_tabs else 'X'
                self.state.enable_y = bool(self.state.profiles['Y'])
                if bool(self.v_ey.get()) != self.state.enable_y:
                    self.v_ey.set(self.state.enable_y)
                target_mode = 'standard'
            if self.v_mode.get() != target_mode:
                self.v_mode.set(target_mode)
            elif target_mode == 'standard' and self.state.phase6_fold_ui_tabs is None and (list(getattr(self.bend_ui, 'tabs', ())) == ['X', 'Y']):
                try:
                    if self.bend_ui.nb.index('current') != 0:
                        self.bend_ui.nb.select(0)
                except Exception:
                    pass
                self.bend_ui.refresh_active_profile()
            else:
                self.bend_ui.rebuild_tabs()
            for var, value in ((self.v_w, self._phase6_box_whd['w']), (self.v_h, self._phase6_box_whd['h']), (self.v_d, self._phase6_box_whd['d'])):
                text = str(value)
                if var.get() != text:
                    var.set(text)
            self._load_part_holes(key)
        finally:
            navigation.finish_activation()
        bridge._navigation_view_finalize_single_part_layout(self, settings_context='box_body' if bridge._phase6_is_box_body_physical_piece_key(key) else key, render_settings_context=lambda context: bridge._phase6_render_settings_context(self, context), pack_right_panel=lambda widget: bridge._phase6_pack_right_panel_above_canvas(self, widget), render_active_drawing_edge_controls=lambda: bridge._phase6_render_active_drawing_edge_controls(self), tk_both=bridge.original.tk.BOTH)
        try:
            after_signature = bridge._phase6_manufacturing_state_signature(self)
        except Exception:
            after_signature = None
        reason = 'display' if not initial and before_signature is not None and (before_signature == after_signature) else 'geometry'
        submit = getattr(self, 'submit_update_intent', None)
        if callable(submit):
            submit(reason, commit=True)
        else:
            self.do_update()
        bridge._phase6_refresh_persistent_structure_controls(self)
        bridge._phase6_refresh_box_body_piece_selector(self)
        bridge._phase6_refresh_receiving_set_bay_control(self)
        bridge._phase6_refresh_back_panel_mode_control(self)
        bridge._phase6_refresh_content_switch(self)