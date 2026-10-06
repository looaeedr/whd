"""Part-session orchestration for the Phase6 Fold Designer.

This owner sequences part save/activation only. Manufacturing formulas, workspace
state, navigation planning, and view projection remain in their existing owners.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Callable

import fold_designer_original as original
from ae_engine.cabinet_types import policy as cabinet_family_policy
from phase6_endcap_semantics import (
    ENDCAP_FW_PARTS,
    commit_endcap_fw,
    resolve_endcap_fw,
)
from phase6_fold_profiles import (
    _num,
    _phase6_fold_tabs_for_part,
    _ui_len,
    build_endcap_profile,
    build_endcap_xy_profiles,
    clone_profile,
    engine_segment_length_to_ui,
    read_box_body_profile,
    read_endcap_xy_profiles,
)
from phase6_manufacturing_adapter import (
    read_standard_part_profiles,
)
from phase6_manufacturing_geometry import _phase6_manufacturing_state_signature
from phase6_navigation_view_adapter import (
    finalize_single_part_layout,
    project_active_part_selector,
)
from phase6_settings_profile_projection import build_standard_part_profiles


@dataclass(frozen=True)
class PartSessionPorts:
    navigation: Callable[[], object]
    clear_navigation_residue: Callable[[], object]
    hide_corner_data_canvas: Callable[[], object]
    is_box_body_physical_piece_key: Callable[[object], bool]
    is_derived_physical_part_key: Callable[[object], bool]
    is_side_back_editable_piece_key: Callable[[object], bool]
    replace_mapping: Callable[[str, object], object]
    commit_box_body_physical_piece_profile: Callable[..., object]
    store_editor_values: Callable[..., object]
    sync_authoritative_derived_parts: Callable[[], object]
    rebuild_linked_endcaps: Callable[[], object]
    mount_shared_content: Callable[[str], object]
    part_label: Callable[[object], str]
    load_part_holes: Callable[[str], object]
    render_settings_context: Callable[[str], object]
    pack_right_panel: Callable[[object], object]
    render_active_drawing_edge_controls: Callable[[], object]
    refresh_persistent_structure_controls: Callable[[], object]
    refresh_box_body_piece_selector: Callable[[], object]
    refresh_receiving_set_bay_control: Callable[[], object]
    refresh_back_panel_mode_control: Callable[[], object]
    refresh_content_switch: Callable[[], object]


class Phase6PartSessionController:
    """Own save/switch sequencing without owning domain or view truth."""

    def __init__(self, app, ports: PartSessionPorts):
        self.app = app
        self.ports = ports

    def save_current_part(self, notify=True):
        app = self.app
        ports = self.ports
        if app.designer_workspace.switching:
            return
        key = app.designer_workspace.active_part
        if not key:
            return
        try:
            app.bend_ui.save()
        except Exception:
            return

        ports.replace_mapping(
            "_phase6_box_whd",
            {
                "w": original.get_int(app.v_w.get()),
                "h": original.get_int(app.v_h.get()),
                "d": original.get_int(app.v_d.get()),
            },
        )
        if ports.is_box_body_physical_piece_key(key):
            profiles = {
                "X": clone_profile(app.state.profiles.get("X", [])),
                "Y": clone_profile(app.state.profiles.get("Y", [])),
            }
            if ports.is_side_back_editable_piece_key(key):
                ports.commit_box_body_physical_piece_profile(
                    key, profiles, notify=notify
                )
            else:
                # W-split children are projections of aggregate BoxBody + width
                # allocation. Preserve only their current workspace view.
                app.designer_workspace.stash_profiles(key, profiles)
            return
        if ports.is_derived_physical_part_key(key):
            ports.sync_authoritative_derived_parts()
            return

        if key == "box_body":
            if getattr(app, "_phase6_sync_ready", False):
                app._sync_dwd_with_top_whd()
            values = read_box_body_profile(
                app.state.profiles_vault["箱身"], app._phase6_input_snapshot
            )
            values["h"] = app._phase6_box_whd["h"]
            ports.store_editor_values(values, notify=notify)
            app._phase6_input_snapshot["endcap_fw"] = deepcopy(
                app._phase6_endcap_fw_state
            )
            ports.rebuild_linked_endcaps()
            return

        profiles = {
            "X": clone_profile(app.state.profiles.get("X", [])),
            "Y": clone_profile(app.state.profiles.get("Y", [])),
        }
        app.designer_workspace.stash_profiles(key, profiles)
        if key in ENDCAP_FW_PARTS:
            x = {
                str(seg.get("phase6_key")): seg
                for seg in profiles.get("X", ())
                if seg.get("phase6_key")
            }
            y = {
                str(seg.get("phase6_key")): seg
                for seg in profiles.get("Y", ())
                if seg.get("phase6_key")
            }
            required_x = {"yl1", "endcap_w_core", "yr1"}
            flat_x = (
                len(profiles.get("X", ())) == 1
                and profiles["X"][0].get("phase6_key") == "endcap_w_flat"
            )
            if not required_x.issubset(x) and not flat_x:
                raise ValueError("封頭/封尾 X 折彎資料不完整")

            app._phase6_endcap_fw_state.setdefault(
                key,
                {
                    "follow_box": True,
                    "value": _num(app._phase6_input_snapshot.get("fw", 25), 25),
                },
            )
            if "fw" in y:
                edited_fw = (
                    engine_segment_length_to_ui(y["fw"])
                    if cabinet_family_policy.endcap_fw_profile_uses_material_dimensions(
                        app._phase6_input_snapshot
                    )
                    else _ui_len(y["fw"].get("len"))
                )
                effective_before = resolve_endcap_fw(
                    app._phase6_input_snapshot,
                    key,
                    state=app._phase6_endcap_fw_state,
                )
                if abs(float(edited_fw) - float(effective_before)) > 1e-9:
                    commit_endcap_fw(
                        app._phase6_endcap_fw_state,
                        key,
                        edited_fw,
                        box_fw=_num(
                            app._phase6_input_snapshot.get("fw", 25), 25
                        ),
                    )
            app._phase6_input_snapshot["endcap_fw"] = deepcopy(
                app._phase6_endcap_fw_state
            )

            canonical_y_keys = {"ytop1", "fw", "endcap_d_core", "ybottom1"}
            if canonical_y_keys.issubset(y):
                values = read_endcap_xy_profiles(
                    profiles, app._phase6_input_snapshot
                )
                values.pop("fw", None)
            else:
                values = (
                    {}
                    if flat_x
                    else {
                        "yl1": _ui_len(x["yl1"].get("len")),
                        "yr1": _ui_len(x["yr1"].get("len")),
                    }
                )
            ports.store_editor_values(values, notify=notify)

            if "w" in values:
                app._phase6_box_whd["w"] = original.get_int(values["w"])
            if "d" in values:
                app._phase6_box_whd["d"] = original.get_int(values["d"])
            w_text = str(app._phase6_box_whd["w"])
            d_text = str(app._phase6_box_whd["d"])
            if app.v_w.get() != w_text:
                app.v_w.set(w_text)
            if app.v_d.get() != d_text:
                app.v_d.set(d_text)

            ports.rebuild_linked_endcaps()
            legacy = build_endcap_profile(app._phase6_input_snapshot)
            app.state.profiles_vault["封頭"] = clone_profile(legacy)
            app.state.profiles_vault["封尾"] = clone_profile(legacy)
        else:
            ports.store_editor_values(
                read_standard_part_profiles(
                    key, profiles, app._phase6_input_snapshot
                ),
                notify=notify,
            )

    def activate_part(self, key, initial=False):
        app = self.app
        ports = self.ports
        navigation = ports.navigation()
        if not navigation.has_part(key):
            return
        ports.clear_navigation_residue()
        ports.hide_corner_data_canvas()
        if ports.is_box_body_physical_piece_key(key):
            app._phase6_box_body_active_piece_key = str(key)
        before_signature = None
        if not initial:
            try:
                before_signature = _phase6_manufacturing_state_signature(app)
            except Exception:
                before_signature = None

        was_non_single = (
            str(getattr(app, "_phase6_3d_display_mode", "single") or "single")
            != "single"
        )
        plan = navigation.plan_activation(
            key,
            initial=initial,
            leaving_non_single_view=was_non_single,
        )
        if not initial:
            app._phase6_3d_display_mode = "single"
            diagnostics = getattr(app, "assembly_diagnostics_frame", None)
            if diagnostics is not None and diagnostics.winfo_manager():
                diagnostics.pack_forget()
        if not initial and getattr(app, "_phase6_pending_settings", None):
            app.flush_pending_settings()
        if plan.noop:
            return

        self._cancel_pending_update()
        if plan.save_outgoing:
            app._save_current_part()
            self._cancel_pending_update()

        ports.mount_shared_content("single")
        # Resolve the canvas now, while keeping its widget unmapped until the
        # editor/settings layout has settled. This preserves predecessor order.
        app.renderer.canvas.get_tk_widget()

        navigation.begin_activation(plan)
        try:
            project_active_part_selector(
                app,
                key=key,
                label=(
                    ports.part_label("box_body")
                    if ports.is_box_body_physical_piece_key(key)
                    else ports.part_label(key)
                ),
                removable=(
                    key != "box_body"
                    and not ports.is_derived_physical_part_key(key)
                ),
                refresh_part_button_states=getattr(
                    app, "_refresh_part_button_states", None
                ),
            )

            if key == "box_body":
                app.state.phase6_fold_ui_profiles = {
                    "X": app.state.profiles_vault["箱身"]
                }
                app.state.phase6_fold_ui_tabs = ["X"]
                app.state.phase6_fold_ui_vault_key = "箱身"
                app.state.struct_mode = "vault"
                app.state.active_bend = "X"
                target_mode = "vault"
            else:
                app.state.phase6_fold_ui_profiles = None
                app.state.phase6_fold_ui_vault_key = None
                if key in {"head", "tail"}:
                    default_profiles = build_endcap_xy_profiles(
                        app._phase6_input_snapshot, part_key=key
                    )
                elif ports.is_derived_physical_part_key(key):
                    default_profiles = (
                        app.designer_workspace.profiles_for(key, {}) or {}
                    )
                else:
                    default_profiles = build_standard_part_profiles(
                        app._phase6_input_snapshot, key
                    )
                profiles = app.designer_workspace.profiles_for(key)
                if profiles is None:
                    profiles = default_profiles
                    navigation.stash_profiles(key, profiles)
                app.state.profiles["X"] = clone_profile(profiles.get("X", []))
                app.state.profiles["Y"] = clone_profile(profiles.get("Y", []))
                app.state.phase6_fold_ui_tabs = _phase6_fold_tabs_for_part(
                    app._phase6_input_snapshot, key
                )
                app.state.struct_mode = "standard"
                app.state.active_bend = (
                    app.state.phase6_fold_ui_tabs[0]
                    if app.state.phase6_fold_ui_tabs
                    else "X"
                )
                app.state.enable_y = bool(app.state.profiles["Y"])
                if bool(app.v_ey.get()) != app.state.enable_y:
                    app.v_ey.set(app.state.enable_y)
                target_mode = "standard"

            if app.v_mode.get() != target_mode:
                app.v_mode.set(target_mode)
            elif (
                target_mode == "standard"
                and app.state.phase6_fold_ui_tabs is None
                and list(getattr(app.bend_ui, "tabs", ())) == ["X", "Y"]
            ):
                try:
                    if app.bend_ui.nb.index("current") != 0:
                        app.bend_ui.nb.select(0)
                except Exception:
                    pass
                app.bend_ui.refresh_active_profile()
            else:
                app.bend_ui.rebuild_tabs()

            for var, value in (
                (app.v_w, app._phase6_box_whd["w"]),
                (app.v_h, app._phase6_box_whd["h"]),
                (app.v_d, app._phase6_box_whd["d"]),
            ):
                text = str(value)
                if var.get() != text:
                    var.set(text)
            ports.load_part_holes(key)
        finally:
            navigation.finish_activation()

        finalize_single_part_layout(
            app,
            settings_context=(
                "box_body"
                if ports.is_box_body_physical_piece_key(key)
                else key
            ),
            render_settings_context=ports.render_settings_context,
            pack_right_panel=ports.pack_right_panel,
            render_active_drawing_edge_controls=(
                ports.render_active_drawing_edge_controls
            ),
            tk_both=original.tk.BOTH,
        )

        try:
            after_signature = _phase6_manufacturing_state_signature(app)
        except Exception:
            after_signature = None
        reason = (
            "display"
            if (
                not initial
                and before_signature is not None
                and before_signature == after_signature
            )
            else "geometry"
        )
        submit = getattr(app, "submit_update_intent", None)
        if callable(submit):
            submit(reason, commit=True)
        else:
            app.do_update()
        ports.refresh_persistent_structure_controls()
        ports.refresh_box_body_piece_selector()
        ports.refresh_receiving_set_bay_control()
        ports.refresh_back_panel_mode_control()
        ports.refresh_content_switch()

    def _cancel_pending_update(self):
        app = self.app
        pending = getattr(app, "_job", None)
        if pending:
            try:
                app.root.after_cancel(pending)
            except Exception:
                pass
            app._job = None
