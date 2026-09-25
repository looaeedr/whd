"""T7 application state synchronization and UI-adapter initialization.

This module initializes and synchronizes host-side UI adapters only. Committed
settings remain owned by SettingsService, physical workspace state remains owned
by Phase6WorkspaceController, and project state remains owned by
Phase6ProjectController.
"""


import tkinter as tk
from copy import deepcopy

import ae_engine.ae as ae
from ae_engine.assembly_joint import migrate_legacy_snapshot_joints
from ae_engine.corner_type_ui import (
    apply_box_assembly_type,
    assembly_type_from_corner_state,
    new_manual_corner_pair_same_state,
    new_manual_corner_state,
)
from ae_engine.sheetmetal_geometry import CornerTypeId, normalize_corner_selection
from phase6_endcap_semantics import (
    ASSEMBLY_TYPE_LABELS,
    normalize_endcap_bottom_wrap_state,
    normalize_endcap_fw_state,
)
from phase6_settings_center import load_corner_defaults_from_ini, ui_text_size_label
from phase6_sync_envelope import stable_fingerprint


class Phase6DerivedCacheOwner:
    """Own invalidation for GUI-derived geometry without touching immutable DXF source cache."""

    PRODUCTS = ("door_layout", "box_body_faces", "authoritative_render")
    _REASON_PRODUCTS = {
        "geometry": frozenset(PRODUCTS),
        "assembly": frozenset({"box_body_faces", "authoritative_render"}),
        "family-structure": frozenset(PRODUCTS),
        "baseline": frozenset(PRODUCTS),
        "display": frozenset(),
        "annotation": frozenset(),
        "camera": frozenset(),
    }

    def __init__(self):
        self._caches = {name: {} for name in self.PRODUCTS}
        self._invalidations = {name: 0 for name in self.PRODUCTS}

    def cache(self, product):
        return self._caches[str(product)]

    def invalidate(self, reason, changed_keys=()):
        reason = str(reason or "geometry")
        products = self._REASON_PRODUCTS.get(reason)
        if products is None:
            # Unknown state mutation fails closed at the derived layer only.
            products = frozenset(self.PRODUCTS)
        for product in products:
            cache = self._caches[product]
            if cache:
                cache.clear()
            self._invalidations[product] += 1
        return tuple(sorted(products))

    def metrics_snapshot(self):
        return dict(self._invalidations)


def _init_primary_and_door_state(self, settings):
    # Tk variables 是 UI adapter；committed runtime 由 SettingsService 持有。
    settings = self.settings_service.snapshot()
    self.ui_text_size_var = tk.StringVar(value=ui_text_size_label(settings.get("ui_text_size", "small")))

    # 基礎設定（仍保留在主 GUI，並與 3D 設定中心雙向連動）
    self.w_var = tk.StringVar(value=self._fold_designer_number_text(settings["w"]))
    self.h_var = tk.StringVar(value=self._fold_designer_number_text(settings["h"]))
    self.d_var = tk.StringVar(value=self._fold_designer_number_text(settings["d"]))
    
    # 連動的 FW (邊框寬度)
    fw_value = float(settings["fw"])
    fw_init_val = str(int(fw_value) if fw_value.is_integer() else fw_value)
    self.fw_z_var = tk.StringVar(value=fw_init_val)
    self.fw_head_var = tk.StringVar(value=fw_init_val)
    self.fw_tail_var = tk.StringVar(value=fw_init_val)
    self.endcap_fw_state = normalize_endcap_fw_state({"fw": fw_value})
    self.endcap_bottom_wrap_state = normalize_endcap_bottom_wrap_state({
        "model": self.baseline_var.get() if hasattr(self, "baseline_var") else "",
    })
    self.fw_head_follow_var = tk.BooleanVar(value=True)
    self.fw_tail_follow_var = tk.BooleanVar(value=True)
    self.cb_fw_head = None
    self.cb_fw_tail = None
    
    # 進階設定
    self.t_var = tk.StringVar(value=self._fold_designer_number_text(settings["t"]))
    
    # 箱身 z 參數
    self.zl1_var = tk.StringVar(value=self._fold_designer_number_text(settings["zl1"]))
    self.zl2_var = tk.StringVar(value=self._fold_designer_number_text(settings["zl2"]))
    self.zr1_var = tk.StringVar(value=self._fold_designer_number_text(settings["zr1"]))
    self.zr2_var = tk.StringVar(value=self._fold_designer_number_text(settings["zr2"]))
    self.z_comp_var = tk.StringVar(value=self._fold_designer_number_text(settings["z_comp"]))
    
    # 封頭尾 y 參數
    self.yl1_var = tk.StringVar(value=self._fold_designer_number_text(settings["yl1"]))
    self.yr1_var = tk.StringVar(value=self._fold_designer_number_text(settings["yr1"]))
    self.ytop1_var = tk.StringVar(value=self._fold_designer_number_text(settings["ytop1"]))
    self.ybottom1_var = tk.StringVar(value=self._fold_designer_number_text(settings["ybottom1"]))
    
    # 門參數
    self.door_gap_w_var = tk.StringVar(value=self._fold_designer_number_text(settings["door_gap_w"]))
    self.door_gap_h_var = tk.StringVar(value=self._fold_designer_number_text(settings["door_gap_h"]))
    self.door_fold_l_var = tk.StringVar(value=self._fold_designer_number_text(settings["door_fold_l"]))
    self.door_fold_r_var = tk.StringVar(value=self._fold_designer_number_text(settings["door_fold_r"]))
    self.door_fold_t_var = tk.StringVar(value=self._fold_designer_number_text(settings["door_fold_t"]))
    self.door_fold_b_var = tk.StringVar(value=self._fold_designer_number_text(settings["door_fold_b"]))

    # 多門配置：W/H 仍是整盤尺寸；這裡只描述各欄起始寬與由上到下的起始高度。
    self.multi_door_enabled_var = tk.BooleanVar(value=False)
    self.door_layout_selected_var = tk.StringVar(value="0:0")
    self.door_layout_columns = []
    # UI adapter only. Authoritative inner-door enable state remains
    # self.receiving_inner_doors; these vars are rebuilt from that state.
    self.door_layout_inner_door_vars = {}
    self.door_layout_inner_door_offset_vars = {}
    self.door_layout_inner_door_offset_entries = {}
    # Family-authoritative inner-door presence/config. Geometry spans are
    # deliberately not invented here; T04 frame parts consume explicit
    # spans once a family/caller owns them.
    self.receiving_inner_doors = []
    self.door_layout_scope = "main"
    self.door_layout_handle_edges = {}
    self.door_nameplate_center_datum_top = None
    # 多門每一格各自保存孔位與門指示燈設定；單門仍沿用 surface_features["door"]。
    self.door_layout_features = {}
    self.door_layout_indicator_states = {}
    # Indicator-Box assembly holes belong to the Door cell that owns the box.
    self.door_layout_indicator_box_features = {}
    self.door_layout_indicator_door_features = {}
    self._derived_cache_owner = getattr(self, "_derived_cache_owner", None) or Phase6DerivedCacheOwner()
    self._door_layout_baseline_cache = self._derived_cache_owner.cache("door_layout")
    self.door_layout_width_entries = {}
    self.door_layout_height_entries = {}
    self.door_layout_entry_windows = []
    self.door_layout_cell_bounds = {}
    self._door_layout_last_click = None  # ((column_index, row_index), event_time_ms)

    # 箱身三面編輯：使用者座標直接使用 WHD，不暴露展開/板厚補償座標。
    self.box_body_face_selected_var = tk.StringVar(value="back")
    # Multi-piece BoxBody stays one top-level 2D tab; this nested selection
    # chooses the physical child whose authoritative unfold is displayed.
    self.box_body_piece_2d_selected_var = tk.StringVar(value="")
    self._box_body_piece_2d_tab_keys = ()
    self._box_body_piece_2d_tab_map = {}
    self._box_body_piece_2d_tab_guard = False
    self.box_body_face_features = {"left": [], "back": [], "right": []}
    self.box_body_face_bounds = {}
    self._box_body_face_last_click = None  # (face_key, event_time_ms)
    self.last_box_body_face_overview = {}
    self._box_body_baseline_face_cache = self._derived_cache_owner.cache("box_body_faces")
    


def _init_base_results_and_corner_state(self, settings):
    # 底板參數
    self.base_plate_entries = []
    base_shrinks = [float(settings[k]) for k in (
        "base_plate_shrink_top", "base_plate_shrink_bottom",
        "base_plate_shrink_left", "base_plate_shrink_right",
    )]
    base_same = max(base_shrinks) - min(base_shrinks) < 1e-9
    self.base_plate_all_same_var = tk.BooleanVar(value=base_same)
    self.base_plate_shrink_same_var = tk.StringVar(value=self._fold_designer_number_text(base_shrinks[0]))
    self.base_plate_shrink_top_var = tk.StringVar(value=self._fold_designer_number_text(settings["base_plate_shrink_top"]))
    self.base_plate_shrink_bottom_var = tk.StringVar(value=self._fold_designer_number_text(settings["base_plate_shrink_bottom"]))
    self.base_plate_shrink_left_var = tk.StringVar(value=self._fold_designer_number_text(settings["base_plate_shrink_left"]))
    self.base_plate_shrink_right_var = tk.StringVar(value=self._fold_designer_number_text(settings["base_plate_shrink_right"]))
    self.base_plate_bend_var = tk.StringVar(value=self._fold_designer_number_text(settings["base_plate_bend"]))
    
    # 計算結果顯示用變數
    self.result_z_var = tk.StringVar(value="-")
    self.result_z_h_var = tk.StringVar(value="-")
    self.result_y_w_var = tk.StringVar(value="-")
    self.result_y_d_var = tk.StringVar(value="-")
    self.result_door_w_var = tk.StringVar(value="-")
    self.result_door_h_var = tk.StringVar(value="-")
    self.result_base_plate_w_var = tk.StringVar(value="-")
    self.result_base_plate_h_var = tk.StringVar(value="-")
    
    # 輸出選項：STOCK 開關
    self.draw_stock_var = tk.BooleanVar(value=bool(settings["draw_stock"]))
    # 輸出零件選擇
    self.export_z_var    = tk.BooleanVar(value=True)
    self.export_head_var = tk.BooleanVar(value=True)
    self.export_tail_var = tk.BooleanVar(value=True)
    self.export_door_var = tk.BooleanVar(value=True)
    self.export_base_plate_var = tk.BooleanVar(value=True)
    self.export_ib_var   = tk.BooleanVar(value=False)
    self.export_ib_door_var = tk.BooleanVar(value=False)
    # Canonical fresh-start model. The primary direct-3D launch has no legacy
    # baseline Combobox to choose the first model later, so startup state itself
    # must already agree with the active cabinet family.
    self.baseline_var    = tk.StringVar(master=self.root, value="金庫型")
    self._active_cabinet_type = "金庫型"
    # Known-model switches always re-apply the target preset.  This map
    # stores immutable startup presets only; it must never become a
    # per-family "remember my last edits" session cache.
    self._cabinet_family_defaults = {}

    # 箱身組合方式是封頭/封尾上方截角的唯一類型來源。
    self.box_assembly_type_var = tk.StringVar(value=ASSEMBLY_TYPE_LABELS[CornerTypeId.INSERT_OVERLAY])
    self.cb_box_assembly = None
    self.assembly_joint_state = migrate_legacy_snapshot_joints({
        "assembly_type": "INSERT_OVERLAY",
        "existing_parts": ["box_body", "head", "tail"],
    })

    # 自訂：截角型式只在此模式可手動選；金庫型永遠使用固定 Factory mapping。
    manual_corner_parts = ["head", "tail", "door", "base_plate", "indicator_box", "indicator_door"]
    self.manual_corner_state = new_manual_corner_state(manual_corner_parts)
    # Normal shop-floor case: top pair is the same, bottom pair is the same.
    # Four physical-corner values are still retained underneath for exceptions.
    self.manual_corner_pair_same = new_manual_corner_pair_same_state(manual_corner_parts)
    self.manual_active_corner_var = tk.StringVar(value="top")
    self.manual_top_same_var = tk.BooleanVar(master=self.root, value=True)
    self.manual_bottom_same_var = tk.BooleanVar(master=self.root, value=True)
    self.manual_corner_type_var = tk.StringVar(value=CornerTypeId.CROSS.value)
    self.manual_corner_cross_mode_var = tk.StringVar(value="標準")
    self.manual_corner_direction_var = tk.StringVar(value="寬")
    self.manual_corner_amount_var = tk.StringVar(value="1")
    self.manual_corner_secondary_retain_var = tk.StringVar(value="0.5")
    self.manual_corner_secondary_depth_var = tk.StringVar(value="2")
    self._manual_corner_param_guard = False
    # UI-only safety state: fine corner parameters are collapsed/locked by default.
    # This state is intentionally NOT serialized into .p6fold.
    self._manual_corner_param_unlocked = {}
    self.corner_type_panel = None
    self.corner_type_preview_canvas = None
    self.corner_type_small_canvases = {}
    saved_corner_state, saved_corner_pairs = load_corner_defaults_from_ini(ae)
    self._apply_manual_corner_snapshot(saved_corner_state, saved_corner_pairs)
    # The box-level assembly semantic is authoritative.  Old/default INI
    # snapshots may contain only CROSS end-cap corners; normalize them once
    # here so the state shown in 2D and consumed by manufacturing is the
    # same state.  Valid legacy INSERT/OVERLAY/INSERT_OVERLAY values are
    # preserved by assembly_type_from_corner_state().
    initial_assembly = assembly_type_from_corner_state(self.manual_corner_state)
    apply_box_assembly_type(
        self.manual_corner_state, self.manual_corner_pair_same, initial_assembly,
        reset_bottom_defaults=True,
    )
    self.box_assembly_type_var.set(ASSEMBLY_TYPE_LABELS[initial_assembly])



def _init_indicator_and_feature_state(self, settings):
    # 指示燈盒子相關變數
    self.is_indicator_box_var = tk.BooleanVar(value=False)
    self.is_indicator_door_var = tk.BooleanVar(value=False)
    self.indicator_g_var = tk.StringVar(value="2")
    self.indicator_l_var = tk.StringVar(value="1")
    self.indicator_layer_g_vars = [tk.StringVar(value="2") for _ in range(6)]
    self.ib_hole_start_x_var = tk.StringVar(value="172.5")
    self.ib_hole_pitch_var = tk.StringVar(value="150")
    self.ib_hole_count_var = tk.StringVar(value="2")
    self.ib_hole_y_var = tk.StringVar(value="178.5")
    
    # 外門指示燈相關變數
    self.is_door_indicator_var = tk.BooleanVar(value=False)
    self.door_indicator_l_var = tk.StringVar(value="1")
    self.door_indicator_layer_g_vars = [tk.StringVar(value="2") for _ in range(6)]
    self.door_indicator_offset_x = 0.0
    self.door_indicator_offset_y = 0.0
    self.drag_active = False
    self.is_box_dist_var = tk.BooleanVar(value=False)
    
    # 左側指示燈盒子結果變數
    self.result_ib_w_var = tk.StringVar(value="-")
    self.result_ib_h_var = tk.StringVar(value="-")
    self.result_ib_door_w_var = tk.StringVar(value="-")
    self.result_ib_door_h_var = tk.StringVar(value="-")
    
    # 封頭/封尾開孔清單
    self.head_holes = []
    self.tail_holes = []
    # Generic unfolded-surface features for every other panel/frame.
    self.surface_features = {
        "box_body": [],
        "door": [],
        "base_plate": [],
        "indicator_box": [],
        "indicator_door": [],
        "head": [],
        "tail": [],
    }

    # 使用者提供的原始折彎/3D 設計器：只做資料橋接，不取代 Phase6 renderer/geometry。
    self.fold_designer_window = None
    self.fold_designer_app = None
    # Workspace presence / active part / profile stash are owned by
    # Phase6WorkspaceController.  Legacy attribute names below are
    # compatibility properties only; no second backing state is created.
    # Hidden auxiliary parts (indicator box / small door) have no top-level
    # preview Notebook tab.  When one is returned from the 3D designer,
    # keep it as the manual CornerType context until the user selects a
    # visible preview tab.
    self._manual_corner_part_override = None


def init_variables(self):
    settings = self.settings_service.snapshot()
    _init_primary_and_door_state(self, settings)
    _init_base_results_and_corner_state(self, settings)
    _init_indicator_and_feature_state(self, settings)


def setting_var_map(self):
    """Tk variables backed by the single Phase6 runtime settings state."""
    return {
        "w": self.w_var, "h": self.h_var, "d": self.d_var,
        "t": self.t_var, "fw": self.fw_z_var, "draw_stock": self.draw_stock_var,
        "zl1": self.zl1_var, "zl2": self.zl2_var, "zr1": self.zr1_var, "zr2": self.zr2_var,
        "z_comp": self.z_comp_var,
        "yl1": self.yl1_var, "yr1": self.yr1_var,
        "ytop1": self.ytop1_var, "ybottom1": self.ybottom1_var,
        "door_gap_w": self.door_gap_w_var, "door_gap_h": self.door_gap_h_var,
        "door_fold_l": self.door_fold_l_var, "door_fold_r": self.door_fold_r_var,
        "door_fold_t": self.door_fold_t_var, "door_fold_b": self.door_fold_b_var,
        "base_plate_shrink_top": self.base_plate_shrink_top_var,
        "base_plate_shrink_bottom": self.base_plate_shrink_bottom_var,
        "base_plate_shrink_left": self.base_plate_shrink_left_var,
        "base_plate_shrink_right": self.base_plate_shrink_right_var,
        "base_plate_bend": self.base_plate_bend_var,
    }


def collect_main_setting_values(self):
    values = self.settings_service.snapshot().as_dict()
    for key, var in self._setting_var_map().items():
        try:
            if isinstance(var, tk.BooleanVar):
                values[key] = bool(var.get())
            else:
                values[key] = float(var.get())
        except (TypeError, ValueError, tk.TclError):
            pass
    return self.settings_service.update(values).as_dict()


def serialize_corner_selection(raw_selection):
    selection = normalize_corner_selection(raw_selection)
    raw = {
        "type_id": selection.type_id.value,
        "rotation_quadrants": 0,
    }
    if selection.cross_mode is not None:
        raw["cross_mode"] = selection.cross_mode.value
    if selection.direction is not None:
        raw["direction"] = selection.direction.value
    if selection.amount_t is not None:
        raw["amount_t"] = float(selection.amount_t)
    if selection.secondary_retain_t is not None:
        raw["secondary_retain_t"] = float(selection.secondary_retain_t)
    if selection.secondary_depth_t is not None:
        raw["secondary_depth_t"] = float(selection.secondary_depth_t)
    return raw


def serialize_manual_corner_state(self):
    result = {}
    for part_key, corners in self.manual_corner_state.items():
        result[part_key] = {
            corner_key: self._serialize_corner_selection(raw_selection)
            for corner_key, raw_selection in corners.items()
        }
    return result


def phase6_external_sync_envelope(self, delta):
    state = {"settings": self.settings_service.snapshot().as_dict()}
    fingerprint = stable_fingerprint(state)
    if fingerprint == getattr(self, "_phase6_main_sync_fingerprint", None):
        return None
    revision = int(getattr(self, "_phase6_main_sync_revision", 0) or 0) + 1
    self._phase6_main_sync_revision = revision
    self._phase6_main_sync_fingerprint = fingerprint
    return {
        "origin": "main_gui",
        "revision": revision,
        "transaction_id": f"main_gui:{revision}",
        "delta": deepcopy(dict(delta or {})),
        "fingerprint": fingerprint,
    }


def on_main_setting_var_changed(self, key, var):
    if getattr(self, "_settings_sync_guard", False):
        return
    try:
        value = bool(var.get()) if isinstance(var, tk.BooleanVar) else float(var.get())
    except (TypeError, ValueError, tk.TclError):
        return
    scheduler = self._phase6_update_scheduler
    scheduler.begin()
    try:
        self.settings_service.update({key: value})
        if key == "fw":
            self._settings_sync_guard = True
            try:
                for part in ("head", "tail"):
                    state = self.endcap_fw_state.setdefault(part, {"follow_box": True, "value": value})
                    if bool(state.get("follow_box", True)):
                        state["value"] = float(value)
                self._sync_endcap_fw_controls()
            finally:
                self._settings_sync_guard = False
        scheduler.mark_dirty(f"setting:{key}")
        designer = getattr(self, "fold_designer_app", None)
        if not getattr(self, "_fold_designer_live_sync_guard", False) and designer is not None:
            try:
                if hasattr(designer, "apply_external_sync"):
                    envelope = self._phase6_external_sync_envelope({"settings": {key: value}})
                    if envelope is not None:
                        designer.apply_external_sync(envelope)
                elif hasattr(designer, "apply_external_settings"):
                    designer.apply_external_settings({key: value})
            except tk.TclError:
                pass
    finally:
        scheduler.end()
