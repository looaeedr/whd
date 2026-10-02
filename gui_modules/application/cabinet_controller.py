"""Cabinet-family/runtime controller extracted from gui.py.

This module coordinates existing host adapters and authoritative services only.
It does not own project schema, workspace physical identity, manufacturing
geometry, or committed settings.
"""
from copy import deepcopy
import tkinter as tk
from tkinter import messagebox

import ae_engine.ae as ae
from ae_engine import manufacturing_api
from ae_engine.contracts import ManufacturingContext
from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.corner_type_ui import is_unknown_model, normalize_custom_model_name
from phase6_endcap_semantics import (
    assembly_intent_label,
    assembly_intent_value,
    normalize_endcap_bottom_wrap_state,
)
from ae_engine.assembly_joint import migrate_legacy_snapshot_joints
from phase6_fold_profiles import build_box_body_profile


def _inherit_known_corner_state_into_custom(self):
    """把目前已知固定板件的實際截角狀態複製成自訂起點。"""
    copied = self._known_corner_state_for_current_family(self.manual_corner_state.keys())
    for part_key, corners in copied.items():
        if part_key not in self.manual_corner_state:
            continue
        self.manual_corner_state[part_key].update(corners)
        if part_key in self.manual_corner_pair_same:
            self.manual_corner_pair_same[part_key]["top"] = True
            self.manual_corner_pair_same[part_key]["bottom"] = True

def _capture_cabinet_family_runtime(self):
    # The family preset itself must carry a real canonical Box Body profile.
    # Startup used to capture None here, which later restored a profile-less
    # family and reopened the legacy fixed-segment manufacturing fallback.
    box_profile = self.workspace_controller.box_body_profile()
    if box_profile is None:
        profile_source = {
            key: var.get() for key, var in self._setting_var_map().items()
        }
        profile_source["model"] = self._current_cabinet_type_name()
        box_profile = build_box_body_profile(profile_source)
        if not box_profile:
            raise ValueError("canonical Box Body Fold Profile materialization failed")
        self.workspace_controller.set_box_body_profile(box_profile)
    elif not box_profile:
        raise ValueError("canonical Box Body Fold Profile is empty")

    layout = []
    if getattr(self, "door_layout_columns", None):
        try:
            layout = [[float(width), [float(v) for v in heights]] for width, heights in self.get_door_layout_columns()]
        except Exception:
            layout = []
    return {
        "settings": {key: var.get() for key, var in self._setting_var_map().items()},
        "corner_state": self._serialize_manual_corner_state(),
        "corner_pair_same": deepcopy(self.manual_corner_pair_same),
        "endcap_bottom_wrap": deepcopy(getattr(self, "endcap_bottom_wrap_state", {})),
        "box_body_structure": self.workspace_controller.box_body_structure_state(),
        "box_body_profile": self.workspace_controller.box_body_profile(),
        "assembly_joint_state": deepcopy(getattr(self, "assembly_joint_state", {}) or {}),
        "multi_door_enabled": bool(self.multi_door_enabled_var.get()),
        "door_layout_columns": layout,
        "door_layout_scope": str(getattr(self, "door_layout_scope", "main") or "main"),
        "door_handle_edges": deepcopy(getattr(self, "door_layout_handle_edges", {}) or {}),
        "receiving_inner_doors": deepcopy(getattr(self, "receiving_inner_doors", []) or []),
        "door_nameplate_center_datum_top": getattr(self, "door_nameplate_center_datum_top", None),
    }

def _restore_cabinet_family_runtime(self, state):
    state = dict(state or {})
    values = {}
    for key, raw in dict(state.get("settings") or {}).items():
        try:
            values[key] = bool(raw) if key == "draw_stock" else float(raw)
        except (TypeError, ValueError):
            continue
    self._apply_fold_designer_live_settings(values, recalculate=False)
    self._apply_manual_corner_snapshot(state.get("corner_state"), state.get("corner_pair_same"))
    if state.get("endcap_bottom_wrap") is not None:
        self.endcap_bottom_wrap_state = normalize_endcap_bottom_wrap_state({
            "model": self._current_cabinet_type_name(),
            "endcap_bottom_wrap": state.get("endcap_bottom_wrap"),
        })
    joint_state = state.get("assembly_joint_state")
    if isinstance(joint_state, dict) and joint_state:
        self.assembly_joint_state = migrate_legacy_snapshot_joints(deepcopy(joint_state))
        stable = assembly_intent_value(self.assembly_joint_state.get("assembly_type", "INSERT_OVERLAY"))
        self.box_assembly_type_var.set(assembly_intent_label(stable))
    self.multi_door_enabled_var.set(bool(state.get("multi_door_enabled", False)))
    layout = list(state.get("door_layout_columns") or [])
    if layout:
        self.set_door_layout_columns([(float(row[0]), [float(v) for v in row[1]]) for row in layout])
    else:
        self.door_layout_columns = []
    self.door_layout_scope = str(state.get("door_layout_scope") or "main")
    self.door_layout_handle_edges = deepcopy(dict(state.get("door_handle_edges") or {}))
    self.receiving_inner_doors = deepcopy(state.get("receiving_inner_doors") or [])
    datum = state.get("door_nameplate_center_datum_top")
    self.door_nameplate_center_datum_top = None if datum is None else float(datum)
    self.workspace_controller.set_box_body_structure_state(state.get("box_body_structure"))
    self.workspace_controller.set_box_body_profile(state.get("box_body_profile"))

def _apply_cabinet_family_for_current_model(self):
    """Apply an explicit model switch without remembering known-family edits.

    Known models always load their own preset.  ``自訂`` is the sole
    exception: entering custom leaves the current operator values in place
    as the starting point.  Project/3D snapshot restoration uses the
    baseline commit guard and therefore does not run this fresh-preset path.
    """
    raw_model = normalize_custom_model_name(
        self.baseline_var.get() if getattr(self, "baseline_var", None) is not None else ""
    )
    new_type = self._current_cabinet_type_name()
    previous = str(getattr(self, "_active_cabinet_type", "金庫型") or "金庫型")

    # Project load / 3D live-state application owns the complete snapshot.
    # Do not wash saved values through a fresh family preset in that path.
    if getattr(self, "_fold_designer_baseline_commit_guard", False):
        self._active_cabinet_type = new_type
        return previous != new_type

    # Custom is intentionally not another family preset.  It inherits the
    # current values exactly; later edits become the custom starting state.
    if is_unknown_model(raw_model):
        self._active_cabinet_type = new_type
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate("geometry")
        return previous != new_type

    if new_type == "金庫型":
        defaults = deepcopy(
            dict(getattr(self, "_cabinet_family_defaults", {}) or {}).get("金庫型")
            or {}
        )
        if defaults:
            self._restore_cabinet_family_runtime(defaults)
    elif new_type == "受電箱":
        # Start from immutable/startup settings, never from the last edited
        # Receiving runtime.  The family policy then overlays its canonical
        # receiving defaults (800/1600/350, FW 29, structure, etc.).
        vault_defaults = deepcopy(
            dict(getattr(self, "_cabinet_family_defaults", {}) or {}).get("金庫型")
            or {}
        )
        base_settings = dict(vault_defaults.get("settings") or self.settings_service.snapshot().as_dict())
        values = cabinet_family_policy.apply_fresh_family_defaults(base_settings, new_type)
        self._apply_fold_designer_live_settings(values, recalculate=False)
        self._set_box_assembly_type(values["assembly_type"], recalculate=False, notify_designer=False)
        self.multi_door_enabled_var.set(bool(values.get("multi_door_enabled", True)))
        self.set_door_layout_columns([
            (float(row[0]), [float(v) for v in row[1]])
            for row in values.get("door_layout_columns", ())
        ])
        self.door_layout_scope = str(values.get("door_layout_scope") or "receiving-main")
        self.door_layout_handle_edges = deepcopy(dict(values.get("door_handle_edges") or {}))
        self.receiving_inner_doors = deepcopy(values.get("inner_doors") or [])
        self.door_nameplate_center_datum_top = float(values["door_nameplate_center_datum_top"])
        structure = cabinet_family_policy.resolve_box_body_structure_state(
            new_type, self.workspace_controller.box_body_structure_state()
        )
        self.workspace_controller.set_box_body_structure_state(structure)
        self.endcap_bottom_wrap_state = normalize_endcap_bottom_wrap_state({"model": new_type})
        bottom = cabinet_family_policy.endcap_bottom_selection(new_type)
        for part in ("head", "tail"):
            self.manual_corner_state[part]["bottom_left"] = bottom
            self.manual_corner_state[part]["bottom_right"] = bottom
            self.manual_corner_pair_same[part]["bottom"] = True
        snap = self._make_original_fold_designer_snapshot()
        box_profile = build_box_body_profile(snap)
        workspace = self.workspace_controller.workspace_snapshot()
        workspace["box_body_profile"] = box_profile
        workspace["box_body_structure"] = structure
        self._store_fold_designer_workspace(workspace)

    self._active_cabinet_type = new_type
    owner = getattr(self, "_derived_cache_owner", None)
    if owner is not None:
        owner.invalidate("geometry")
    return previous != new_type


def on_baseline_changed(self):
    self._reset_manual_corner_parameter_locks()
    owner = getattr(self, "_derived_cache_owner", None)
    if owner is not None:
        owner.invalidate("baseline")
    val = self.baseline_var.get()
    previous = str(getattr(self, "_baseline_last_value", "") or "").strip()
    self._apply_cabinet_family_for_current_model()
    if is_unknown_model(val) and previous and not is_unknown_model(previous):
        self._inherit_known_corner_state_into_custom()
    elif val and not is_unknown_model(val) and val != previous:
        self._enforce_known_model_corner_types(reset_all=True)
    current_intent = self._current_box_assembly_type()
    assembly_var = getattr(self, "box_assembly_type_var", None)
    if assembly_var is not None:
        label = assembly_intent_label(current_intent)
        if assembly_var.get() != label:
            assembly_var.set(label)
    cb_assembly = getattr(self, "cb_box_assembly", None)
    if cb_assembly is not None:
        cb_assembly.configure(state=("readonly" if is_unknown_model(val) else "disabled"))
    self._baseline_last_value = str(val or "").strip()
    self.refresh_corner_type_panel()
    designer = getattr(self, "fold_designer_app", None)
    if designer is not None and hasattr(designer, "apply_external_model"):
        try:
            designer.apply_external_model(val)
        except tk.TclError:
            pass
    if getattr(self, "_fold_designer_baseline_commit_guard", False):
        # 3D 確定 only changes the baseline/corner transaction. Do not let
        # the legacy baseline handler overwrite already-edited fold values.
        return
    if not val:
        return
    if is_unknown_model(val):
        # 自訂沒有 baseline DXF；保留使用者輸入的折彎尺寸。
        self._request_phase6_update("baseline")
        return
    if self._current_cabinet_type_name() == "受電箱":
        # 受電箱第一階段使用公式/Family policy，沒有自己的 baseline DXF。
        self._request_phase6_update("baseline")
        return
    try:
        t_val = float(self.t_var.get()) if self.t_var.get() else 2.0
        
        # 1. 載入封頭尾基準檔分析折彎參數
        geom = ae.get_stretched_end_cap_data(val, 500, 500, 150, t_val, FW_val=None, is_tail=False)
        p = geom.params
        
        self.yl1_var.set(f"{p['yl1']:.1f}".replace(".0", ""))
        self.yr1_var.set(f"{p['yr1']:.1f}".replace(".0", ""))
        self.ytop1_var.set(f"{p['ytop1']:.1f}".replace(".0", ""))
        self.ybottom1_var.set(f"{p['ybottom1']:.1f}".replace(".0", ""))
        # 基準檔更新箱身 FW；封頭尾只有仍在「跟隨箱身」時同步。
        fw_val = f"{p['fw']:.1f}".replace(".0", "")
        self.fw_z_var.set(fw_val)
        box_fw = float(p['fw'])
        for part in ("head", "tail"):
            state = self.endcap_fw_state.setdefault(part, {"follow_box": True, "value": box_fw})
            if bool(state.get("follow_box", True)):
                state["value"] = box_fw
        self._sync_endcap_fw_controls()
        
        # 2. 箱身主結構固定由 StripFoldChain 公式控制。
        # 箱身.dxf 只映射固定加工特徵，不反推/覆寫 zl1/zl2/zr1/zr2/z_comp。

        # 3. 檢查並加載目前型號的門基準；GUI 不自行組 baseline 路徑。
        if ae.has_baseline_part(val, "門.dxf"):
            try:
                door_fw = self._door_material_frame_width(
                    self.fw_z_var.get(), t_val, model_name=val
                )
                geom_door = ae.get_stretched_door_data(
                    val, 500, 500, t_val, door_fw
                )
                pd = geom_door.params
                self.door_fold_l_var.set(f"{pd['door_fold_l']:.1f}".replace(".0", ""))
                self.door_fold_r_var.set(f"{pd['door_fold_r']:.1f}".replace(".0", ""))
                self.door_fold_t_var.set(f"{pd['door_fold_t']:.1f}".replace(".0", ""))
                self.door_fold_b_var.set(f"{pd['door_fold_b']:.1f}".replace(".0", ""))
            except Exception as door_err:
                self.door_fold_l_var.set("19")
                self.door_fold_r_var.set("15")
                self.door_fold_t_var.set("15")
                self.door_fold_b_var.set("15")
    except Exception as e:
        messagebox.showerror("基準檔載入出錯", f"無法讀取基準檔參數: {e}")

    # STOCK 開關變動時也觸發重繪 (Checkbutton 已用 command 綁定，此處不需重複)

def get_float_values(self):
    """
    取得所有浮點數輸入值，若輸入有誤則拋出 Exception
    """
    try:
        return {
            'w': float(self.w_var.get()),
            'h': float(self.h_var.get()),
            'd': float(self.d_var.get()),
            'fw': float(self.fw_z_var.get()),
            't': float(self.t_var.get()),
            'zl1': float(self.zl1_var.get()),
            'zl2': float(self.zl2_var.get()),
            'zr1': float(self.zr1_var.get()),
            'zr2': float(self.zr2_var.get()),
            'z_comp': float(self.z_comp_var.get()),
            'yl1': float(self.yl1_var.get()),
            'yr1': float(self.yr1_var.get()),
            'ytop1': float(self.ytop1_var.get()),
            'ybottom1': float(self.ybottom1_var.get()),
            'door_gap_w': float(self.door_gap_w_var.get()),
            'door_gap_h': float(self.door_gap_h_var.get()),
            'door_fold_l': float(self.door_fold_l_var.get()),
            'door_fold_r': float(self.door_fold_r_var.get()),
            'door_fold_t': float(self.door_fold_t_var.get()),
            'door_fold_b': float(self.door_fold_b_var.get()),
            'base_plate_shrink_top': float(self.base_plate_shrink_top_var.get()),
            'base_plate_shrink_bottom': float(self.base_plate_shrink_bottom_var.get()),
            'base_plate_shrink_left': float(self.base_plate_shrink_left_var.get()),
            'base_plate_shrink_right': float(self.base_plate_shrink_right_var.get()),
            'base_plate_bend': float(self.base_plate_bend_var.get()),
        }
    except ValueError:
        raise ValueError("請輸入有效的數字格式")

def _active_indicator_box_groups_for_results(self):
    """Return groups only when the currently relevant Door really uses an Indicator Box.

    Single-Door follows the explicit Indicator-Box toggle. Multi-Door follows
    only the currently selected cell, so an unrelated cell cannot leak box
    dimensions into the result panel.
    """
    if self.multi_door_enabled_var.get():
        key = str(self.door_layout_selected_var.get() or "")
        state = self.door_layout_indicator_states.get(key)
        if not state:
            return None
        state = self._normalize_door_indicator_state(state)
        if state.get("mode") != "indicator_box":
            return None
        layers = max(1, min(6, int(state.get("layers", 1))))
        groups = tuple(int(v) for v in list(state.get("groups", ()))[:layers])
    else:
        if not self.is_indicator_box_var.get():
            return None
        layers = max(1, min(6, int(self.indicator_l_var.get())))
        groups = tuple(int(self.indicator_layer_g_vars[i].get()) for i in range(layers))
    if not groups or any(value <= 0 for value in groups):
        return None
    return groups

def _has_any_indicator_box(self):
    """True only when at least one real Door/cell is configured as Indicator Box."""
    if not self.multi_door_enabled_var.get():
        return bool(self.is_indicator_box_var.get())
    try:
        keys = [self._door_layout_cell_key(cell) for cell in self.get_door_layout_cells()]
    except Exception:
        keys = list(getattr(self, "door_layout_indicator_states", {}).keys())
    for key in keys:
        state = self._normalize_door_indicator_state(
            getattr(self, "door_layout_indicator_states", {}).get(key)
        )
        if state.get("mode") == "indicator_box":
            return True
    return False

def _clear_indicator_box_result_values(self):
    self.result_ib_w_var.set("-")
    self.result_ib_h_var.set("-")
    self.result_ib_door_w_var.set("-")
    self.result_ib_door_h_var.set("-")

def _refresh_indicator_box_result_values(self, val):
    """Refresh box/small-door dimensions from actual Indicator-Box state only."""
    self._clear_indicator_box_result_values()
    layer_groups = self._active_indicator_box_groups_for_results()
    if layer_groups is None:
        return

    g_max = max(layer_groups)
    indicator_ctx = ManufacturingContext()
    ib_w, ib_h = manufacturing_api.indicator_box_unfolded_size(
        layer_groups, thickness=val['t'], context=indicator_ctx
    )
    ib_door_w, ib_door_h = manufacturing_api.indicator_small_door_unfolded_size(
        layer_groups, thickness=val['t'], context=indicator_ctx
    )
    self.result_ib_w_var.set(f"{ib_w:.2f} mm")
    self.result_ib_h_var.set(f"{ib_h:.2f} mm")
    self.result_ib_door_w_var.set(f"{ib_door_w:.2f} mm")
    self.result_ib_door_h_var.set(f"{ib_door_h:.2f} mm")
    self.indicator_g_var.set(str(g_max))

    x_left_light = 171.0
    x_right_light = 171.0 + 90.0 * max(0, g_max - 1)
    if g_max <= 1:
        hc = 1
    elif g_max <= 3:
        hc = 2
    elif g_max <= 5:
        hc = 3
    else:
        hc = 4
    if hc > 1:
        max_pitch = (x_right_light - x_left_light) / (hc - 1)
        hp = max(50.0, float(int(max_pitch // 50) * 50))
        x_mid = (x_left_light + x_right_light) / 2.0
        hx = x_mid - (hc - 1) * hp / 2.0
    else:
        hp = 150.0
        hx = 191.0 if g_max == 1 else 172.5
    self.ib_hole_start_x_var.set(f"{hx:.1f}".replace(".0", ""))
    self.ib_hole_pitch_var.set(f"{int(hp)}")
    self.ib_hole_count_var.set(str(hc))
    self.ib_hole_y_var.set("178.5")
