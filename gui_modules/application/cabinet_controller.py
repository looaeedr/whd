"""Cabinet-family/runtime controller extracted from gui.py.

This module coordinates existing host adapters and authoritative services only.
It does not own project schema, workspace physical identity, manufacturing
geometry, or committed settings.
"""
from copy import deepcopy
import tkinter as tk
from tkinter import messagebox

from ae_engine import manufacturing_api
from ae_engine.contracts import ManufacturingContext
from phase6_endcap_semantics import (
    assembly_intent_label,
    assembly_intent_value,
    normalize_endcap_bottom_wrap_state,
)


def _inherit_known_corner_state_into_custom(self):
    """Use the certified Engine draft before copying known corners to Custom."""
    # The current Custom label resolves to the same canonical family as the
    # original known-corner lookup. Do not re-derive certified corner values
    # or modify a live part before all source corners are validated.
    family = self._current_cabinet_type_name()
    next_state, next_pairs = manufacturing_api.propose_operator_known_model_corner_draft(
        self.manual_corner_state, self.manual_corner_pair_same,
        baseline_model=family, cabinet_family=family, reset_all=True,
    )
    # Preserve nested GUI aliases (e.g. open Hole Editor / settings widgets).
    for part_key, updated in next_state.items():
        existing = self.manual_corner_state[part_key]
        if existing != updated:
            existing.clear()
            existing.update(updated)
    for part_key, updated in next_pairs.items():
        existing = self.manual_corner_pair_same[part_key]
        if existing != updated:
            existing.clear()
            existing.update(updated)

def _capture_cabinet_family_runtime(self):
    # Validate physical UI sources *before* any workspace/profile mutation.
    # The Engine-owned Door grid getter checks live cells; this final public
    # source check prevents corrupt bool/NaN data being turned into a deleted
    # Door layout by the legacy fallback.
    multi_door_enabled = manufacturing_api.normalize_operator_settings_boolean(
        self.multi_door_enabled_var.get()
    )
    layout = []
    if getattr(self, "door_layout_columns", None):
        layout = [
            [
                manufacturing_api.normalize_operator_source_dimension(width, field="w"),
                [
                    manufacturing_api.normalize_operator_source_dimension(height, field="h")
                    for height in heights
                ],
            ]
            for width, heights in self.get_door_layout_columns()
        ]

    nameplate_datum = manufacturing_api.normalize_operator_door_nameplate_center_datum_top(
        getattr(self, "door_nameplate_center_datum_top", None)
    )

    # The family preset itself must carry a real canonical Box Body profile.
    # Startup used to capture None here, which later restored a profile-less
    # family and reopened the legacy fixed-segment manufacturing fallback.
    box_profile = self.workspace_controller.box_body_profile()
    if box_profile is None:
        profile_source = {
            key: var.get() for key, var in self._setting_var_map().items()
        }
        profile_source["model"] = self._current_cabinet_type_name()
        box_profile = manufacturing_api.build_box_body_fold_profile(profile_source)
        if not box_profile:
            raise ValueError("canonical Box Body Fold Profile materialization failed")
        self.workspace_controller.set_box_body_profile(box_profile)
    elif not box_profile:
        raise ValueError("canonical Box Body Fold Profile is empty")

    return {
        "settings": {key: var.get() for key, var in self._setting_var_map().items()},
        "corner_state": self._serialize_manual_corner_state(),
        "corner_pair_same": deepcopy(self.manual_corner_pair_same),
        "endcap_bottom_wrap": deepcopy(getattr(self, "endcap_bottom_wrap_state", {})),
        "box_body_structure": self.workspace_controller.box_body_structure_state(),
        "box_body_profile": self.workspace_controller.box_body_profile(),
        "assembly_joint_state": deepcopy(getattr(self, "assembly_joint_state", {}) or {}),
        "multi_door_enabled": multi_door_enabled,
        "door_layout_columns": layout,
        "door_layout_scope": str(getattr(self, "door_layout_scope", "main") or "main"),
        "door_handle_edges": deepcopy(getattr(self, "door_layout_handle_edges", {}) or {}),
        "receiving_inner_doors": deepcopy(getattr(self, "receiving_inner_doors", []) or []),
        "door_nameplate_center_datum_top": nameplate_datum,
    }

def _restore_cabinet_family_runtime(self, state):
    state = dict(state or {})
    # Validate all serialized physical switches before mutating live widgets.
    multi_door_enabled = manufacturing_api.normalize_operator_settings_boolean(
        state["multi_door_enabled"] if "multi_door_enabled" in state else False
    )
    # A Door cell is physical manufacturing source. Validate the complete
    # serialized grid before *any* Settings/Corner/Workspace mutation. Never
    # float(True) into a manufactured 1-mm door when the GUI restores a preset.
    layout = []
    for row in state.get("door_layout_columns") or ():
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            raise ValueError("已保存門格格式無效")
        width, heights = row
        if not isinstance(heights, (list, tuple)) or not heights:
            raise ValueError("已保存門格每欄至少需要一層高度")
        layout.append((
            manufacturing_api.normalize_operator_source_dimension(width, field="w"),
            [
                manufacturing_api.normalize_operator_source_dimension(height, field="h")
                for height in heights
            ],
        ))
    nameplate_datum = manufacturing_api.normalize_operator_door_nameplate_center_datum_top(
        state.get("door_nameplate_center_datum_top")
    )
    # Decode saved sources only via public Engine rules. Physical dimensions
    # and explicit output switches reject malformed data before GUI mutation;
    # historic nonphysical Fold numeric defaults retain Engine's skip-invalid
    # compatibility instead of GUI float(True) == 1 mm.
    raw_settings = dict(state.get("settings") or {})
    physical = {
        key: manufacturing_api.normalize_operator_source_dimension(raw, field=key)
        for key, raw in raw_settings.items()
        if key in manufacturing_api.PHYSICAL_SNAPSHOT_SOURCE_KEYS
    }
    stock = (
        {"draw_stock": manufacturing_api.normalize_operator_settings_boolean(
            raw_settings["draw_stock"]
        )} if "draw_stock" in raw_settings else {}
    )
    other_raw = {
        key: raw for key, raw in raw_settings.items()
        if key not in physical and key != "draw_stock"
    }
    other = manufacturing_api.normalize_operator_settings_updates(
        {key: 0.0 for key in other_raw}, other_raw,
    )
    self._apply_fold_designer_live_settings(
        {**physical, **stock, **other}, recalculate=False,
    )
    self._apply_manual_corner_snapshot(state.get("corner_state"), state.get("corner_pair_same"))
    if state.get("endcap_bottom_wrap") is not None:
        self.endcap_bottom_wrap_state = normalize_endcap_bottom_wrap_state({
            "model": self._current_cabinet_type_name(),
            "endcap_bottom_wrap": state.get("endcap_bottom_wrap"),
        })
    joint_state = state.get("assembly_joint_state")
    if isinstance(joint_state, dict) and joint_state:
        self.assembly_joint_state = manufacturing_api.migrate_operator_assembly_joint_snapshot(deepcopy(joint_state))
        stable = assembly_intent_value(self.assembly_joint_state.get("assembly_type", "INSERT_OVERLAY"))
        self.box_assembly_type_var.set(assembly_intent_label(stable))
    self.multi_door_enabled_var.set(multi_door_enabled)
    if layout:
        self.set_door_layout_columns(layout)
    else:
        self.door_layout_columns = []
    self.door_layout_scope = str(state.get("door_layout_scope") or "main")
    self.door_layout_handle_edges = deepcopy(dict(state.get("door_handle_edges") or {}))
    self.receiving_inner_doors = deepcopy(state.get("receiving_inner_doors") or [])
    self.door_nameplate_center_datum_top = nameplate_datum
    self.workspace_controller.set_box_body_structure_state(state.get("box_body_structure"))
    self.workspace_controller.set_box_body_profile(state.get("box_body_profile"))

def _apply_cabinet_family_for_current_model(self):
    """Apply an explicit model switch without remembering known-family edits.

    Known models always load their own preset.  ``自訂`` is the sole
    exception: entering custom leaves the current operator values in place
    as the starting point.  Project/3D snapshot restoration uses the
    baseline commit guard and therefore does not run this fresh-preset path.
    """
    raw_model = manufacturing_api.operator_normalize_custom_model_name(
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
    if manufacturing_api.is_unknown_operator_model(raw_model):
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
        values = manufacturing_api.operator_apply_fresh_family_defaults(base_settings, new_type)
        receiving_datum = manufacturing_api.normalize_operator_door_nameplate_center_datum_top(
            values["door_nameplate_center_datum_top"]
        )
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
        self.door_nameplate_center_datum_top = receiving_datum
        structure = manufacturing_api.operator_resolve_box_body_structure_state(
            new_type, self.workspace_controller.box_body_structure_state()
        )
        self.workspace_controller.set_box_body_structure_state(structure)
        self.endcap_bottom_wrap_state = normalize_endcap_bottom_wrap_state({"model": new_type})
        bottom = manufacturing_api.operator_endcap_bottom_selection(new_type)
        for part in ("head", "tail"):
            self.manual_corner_state[part]["bottom_left"] = bottom
            self.manual_corner_state[part]["bottom_right"] = bottom
            self.manual_corner_pair_same[part]["bottom"] = True
        snap = self._make_original_fold_designer_snapshot()
        # First Family selection owns a real NFB source immediately, not a
        # hidden editor-only model draft. Persist its actual Set/Bay source in
        # the existing workspace so opening FoldDesigner/assembly sees the
        # same committed inner-door holes, BasePlate and derived fixing ears.
        # Public Engine owns the native CSV source and single-Set/Bay identity.
        # Known-Family selection is a new cabinet. Do not inherit an old
        # edited Bay from a previous Receiving session through workspace.
        snap["receiving_layout"] = manufacturing_api.operator_new_receiving_layout(
            width=snap["w"], height=snap["h"], depth=snap["d"],
        )
        snap["active_mode"] = "set_bay"
        initial = manufacturing_api.operator_seed_fresh_receiving_nfb_source(snap)
        box_profile = manufacturing_api.build_box_body_fold_profile(snap)
        workspace = self.workspace_controller.workspace_snapshot()
        workspace["receiving_layout"] = deepcopy(initial["receiving_layout"])
        # A submitted default Bay without its matching physical CUTTING in
        # Workspace is only half initialized: first view looks empty, then a
        # later mode rollback suddenly inserts a new ProfileFeature. Commit
        # the *same* real CSV inner-door source on the original first switch.
        workspace["part_features"] = deepcopy(initial.get("part_features") or {})
        workspace["box_body_profile"] = box_profile
        workspace["box_body_structure"] = structure
        self._store_fold_designer_workspace(workspace)

    self._active_cabinet_type = new_type
    owner = getattr(self, "_derived_cache_owner", None)
    if owner is not None:
        owner.invalidate("geometry")
    return previous != new_type


def on_baseline_changed(self):
    # A known Vault baseline must not change committed Corner/Family state
    # when its current physical plate thickness is invalid. Check the raw
    # operator value through the existing public Engine before any GUI effects.
    raw_model = self.baseline_var.get()
    if (
        raw_model
        and not manufacturing_api.is_unknown_operator_model(raw_model)
        and manufacturing_api.resolve_live_cabinet_family({}, raw_model) == "金庫型"
        and not getattr(self, "_fold_designer_baseline_commit_guard", False)
    ):
        try:
            manufacturing_api.normalize_operator_source_dimension(
                self.t_var.get(), field="t",
            )
        except (TypeError, ValueError, tk.TclError) as exc:
            messagebox.showerror("基準檔載入出錯", f"無法讀取基準檔參數: {exc}")
            return
    self._reset_manual_corner_parameter_locks()
    owner = getattr(self, "_derived_cache_owner", None)
    if owner is not None:
        owner.invalidate("baseline")
    val = self.baseline_var.get()
    previous = str(getattr(self, "_baseline_last_value", "") or "").strip()
    self._apply_cabinet_family_for_current_model()
    if manufacturing_api.is_unknown_operator_model(val) and previous and not manufacturing_api.is_unknown_operator_model(previous):
        self._inherit_known_corner_state_into_custom()
    elif val and not manufacturing_api.is_unknown_operator_model(val) and val != previous:
        self._enforce_known_model_corner_types(reset_all=True)
    current_intent = self._current_box_assembly_type()
    assembly_var = getattr(self, "box_assembly_type_var", None)
    if assembly_var is not None:
        label = assembly_intent_label(current_intent)
        if assembly_var.get() != label:
            assembly_var.set(label)
    cb_assembly = getattr(self, "cb_box_assembly", None)
    if cb_assembly is not None:
        cb_assembly.configure(state=("readonly" if manufacturing_api.is_unknown_operator_model(val) else "disabled"))
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
    if manufacturing_api.is_unknown_operator_model(val):
        # 自訂沒有 baseline DXF；保留使用者輸入的折彎尺寸。
        self._request_phase6_update("baseline")
        return
    if self._current_cabinet_type_name() == "受電箱":
        # 受電箱第一階段使用公式/Family policy，沒有自己的 baseline DXF。
        self._request_phase6_update("baseline")
        return
    try:
        t_val = self.t_var.get()  # Raw T; public Engine validates before parsing DXF.
        
        # 1. 載入封頭尾基準檔分析折彎參數
        baseline_folds = manufacturing_api.read_operator_baseline_fold_defaults(
            val, thickness=t_val,
        )
        p = baseline_folds["endcap"]
        
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
        pd = baseline_folds["door"]
        if pd is not None:
            self.door_fold_l_var.set(f"{pd['door_fold_l']:.1f}".replace(".0", ""))
            self.door_fold_r_var.set(f"{pd['door_fold_r']:.1f}".replace(".0", ""))
            self.door_fold_t_var.set(f"{pd['door_fold_t']:.1f}".replace(".0", ""))
            self.door_fold_b_var.set(f"{pd['door_fold_b']:.1f}".replace(".0", ""))
    except Exception as e:
        messagebox.showerror("基準檔載入出錯", f"無法讀取基準檔參數: {e}")

    # Known-family return must publish the rebuilt Box Body, not just restore
    # dimension widgets. Receiving/custom paths request their own redraw above;
    # Vault reaches this point after its baseline features have been loaded.
    self._request_phase6_update("baseline")

    # STOCK 開關變動時也觸發重繪 (Checkbutton 已用 command 綁定，此處不需重複)

def get_float_values(self):
    """Keep the raw 25 GUI numeric inputs until Engine validates their meaning.

    Physical W/H/D/T/FW must be positive; remaining signed Fold/Gap/BasePlate
    inputs use original Engine finite numeric compatibility. Never return a
    partial manufacturing candidate when a field is malformed.
    """
    raw = {
        "w": self.w_var.get(),
        "h": self.h_var.get(),
        "d": self.d_var.get(),
        "fw": self.fw_z_var.get(),
        "t": self.t_var.get(),
        "zl1": self.zl1_var.get(),
        "zl2": self.zl2_var.get(),
        "zr1": self.zr1_var.get(),
        "zr2": self.zr2_var.get(),
        "z_comp": self.z_comp_var.get(),
        "yl1": self.yl1_var.get(),
        "yr1": self.yr1_var.get(),
        "ytop1": self.ytop1_var.get(),
        "ybottom1": self.ybottom1_var.get(),
        "door_gap_w": self.door_gap_w_var.get(),
        "door_gap_h": self.door_gap_h_var.get(),
        "door_fold_l": self.door_fold_l_var.get(),
        "door_fold_r": self.door_fold_r_var.get(),
        "door_fold_t": self.door_fold_t_var.get(),
        "door_fold_b": self.door_fold_b_var.get(),
        "base_plate_shrink_top": self.base_plate_shrink_top_var.get(),
        "base_plate_shrink_bottom": self.base_plate_shrink_bottom_var.get(),
        "base_plate_shrink_left": self.base_plate_shrink_left_var.get(),
        "base_plate_shrink_right": self.base_plate_shrink_right_var.get(),
        "base_plate_bend": self.base_plate_bend_var.get(),
    }
    physical = manufacturing_api.normalize_operator_source_dimensions(raw)
    other = {key: value for key, value in raw.items() if key not in physical}
    accepted = manufacturing_api.normalize_operator_settings_updates(
        {key: 0.0 for key in other}, other,
    )
    if len(accepted) != len(other):
        invalid = next(key for key in other if key not in accepted)
        raise ValueError(f"請輸入有效的數字格式：{invalid}")
    return {**physical, **accepted}


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

    marking = manufacturing_api.project_indicator_box_marking_layout(layer_groups)
    self.ib_hole_start_x_var.set(f"{marking.start_x:.1f}".replace(".0", ""))
    self.ib_hole_pitch_var.set(f"{int(marking.pitch)}")
    self.ib_hole_count_var.set(str(marking.count))
    self.ib_hole_y_var.set(f"{marking.first_row_y:.1f}".replace(".0", ""))
