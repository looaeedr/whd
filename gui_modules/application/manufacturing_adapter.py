# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""Manufacturing request adapters extracted from gui.py for #295/T7.

This module maps existing application/workspace state into established AE contract
objects and validation/export contexts.  AE/manufacturing modules remain the
geometry, formula, DXF and process authority.
"""
from copy import deepcopy

from ae_engine import manufacturing_api
from ae_engine.contracts import (
    BoxBodyPartSpec,
    DoorPartSpec,
    ManufacturingContext,
)
from ae_engine.sheetmetal_part_adapters import DoorFrameEdges
from phase6_fold_profiles import (
    engine_segment_length_to_ui,
    formed_box_body_fw_widths,
    profile_to_fold_segments,
)


def _endcap_profiles_for_assembly(values, stored_profiles, assembly_type, part_key):
    """Compatibility seam: Engine owns assembly-dependent X/Y Fold topology."""
    return manufacturing_api.endcap_profiles_for_assembly(
        values, stored_profiles, assembly_type, part_key,
    )

def _manufacturing_context(self, *, draw_stock=False):
    """GUI-owned execution context for the headless manufacturing boundary."""
    return ManufacturingContext(draw_stock=bool(draw_stock), overwrite=True)

def _box_body_part_spec_from_values(
    self, val, *, model_name, features, face_features,
    head_corner_policy=None, tail_corner_policy=None, fold_profile=None,
    structure_state=None, head_ybottom1=None, tail_ybottom1=None,
    snapshot=None,
):
    """Collect operator/workspace inputs; Engine builds the real BoxBodyPartSpec."""
    controller = self.workspace_controller
    endcap_y_profiles = {}
    for key, override in (("head", head_ybottom1), ("tail", tail_ybottom1)):
        if override is None:
            source = controller.profile_for(key) or {}
            endcap_y_profiles[key] = list(dict(source).get("Y", ()) or ())
    return manufacturing_api.build_box_body_operator_part_spec(
        val,
        model_name=model_name,
        features=features,
        face_features=face_features,
        head_corner_policy=head_corner_policy,
        tail_corner_policy=tail_corner_policy,
        fold_profile=(fold_profile if fold_profile is not None
                      else (controller.box_body_profile() or ())),
        structure_state=(controller.box_body_structure_state()
                         if structure_state is None else structure_state),
        source_part_features=getattr(
            controller, "part_features_snapshot", lambda: {}
        )(),
        endcap_y_profiles=endcap_y_profiles,
        head_ybottom1=head_ybottom1,
        tail_ybottom1=tail_ybottom1,
        snapshot=snapshot,
    )

def _box_body_part_spec(self, val):
    head_policy, tail_policy = self._box_body_corner_policies(val['fw'])
    return self._box_body_part_spec_from_values(
        val, model_name=self._baseline_source_model(),
        features=self.surface_features["box_body"],
        face_features=self.box_body_face_features,
        head_corner_policy=head_policy, tail_corner_policy=tail_policy,
        snapshot=val,
    )

def _end_cap_part_spec_from_values(
    self, val, *, model_name, is_tail, holes, corner_policy=None, fold_profiles=None,
    depth_comp_t=None, resolved_assembly_relief_cuts=(),
    box_body_formed_fw_left=None, box_body_formed_fw_right=None,
    box_body_structure_state=None, endcap_bottom_wrap_state=None, assembly_joints=None,
):
    """Collect operator/committed state; Engine owns physical EndCap PartSpec."""
    controller = getattr(self, "workspace_controller", None)
    if box_body_structure_state is None:
        getter = getattr(controller, "box_body_structure_state", None)
        box_body_structure_state = getter() if callable(getter) else {}
    assembly_joint_state = None
    if assembly_joints is None:
        assembly_joint_state = dict(
            getattr(self, "assembly_joint_state", {}) or {}
        )
        assembly_joints = assembly_joint_state.get("assembly_joints", ())
    if endcap_bottom_wrap_state is None:
        endcap_bottom_wrap_state = getattr(self, "endcap_bottom_wrap_state", None)
    return manufacturing_api.build_endcap_operator_part_spec(
        val, model_name=model_name, is_tail=is_tail, holes=holes,
        corner_policy=corner_policy, fold_profiles=fold_profiles,
        depth_comp_t=depth_comp_t,
        resolved_assembly_relief_cuts=resolved_assembly_relief_cuts,
        box_body_formed_fw_left=box_body_formed_fw_left,
        box_body_formed_fw_right=box_body_formed_fw_right,
        box_body_structure_state=box_body_structure_state,
        endcap_bottom_wrap_state=endcap_bottom_wrap_state,
        assembly_joints=assembly_joints,
        assembly_joint_state=assembly_joint_state,
    )

@staticmethod
def _phase6_relief_profile_signature(profile):
    return manufacturing_api.relief_profile_fingerprint(profile)


def _resolved_committed_assembly_relief_cuts(self, key, val, stored_profiles):
    """Collect current operator inputs; Engine owns committed relief replay."""
    state = deepcopy(getattr(self, "assembly_relief_state", {}) or {})
    if not bool(state.get("enabled")):
        # Preserve the historic uninitialized-BoxBody disabled short circuit.
        return ()
    controller = getattr(self, "workspace_controller", None)
    getter = getattr(controller, "box_body_profile", None)
    body_profile = (getter() if callable(getter) else ()) or ()
    structure_getter = getattr(controller, "box_body_structure_state", None)
    structure_state = (
        structure_getter() if callable(structure_getter) else {}
    )
    family_getter = getattr(self, "_baseline_source_model", None)
    family = str(family_getter() if callable(family_getter) else "")
    return manufacturing_api.resolve_operator_committed_relief_cuts(
        key, val, relief_state=state,
        joint_state=getattr(self, "assembly_joint_state", {}) or {},
        structure_state=structure_state,
        cabinet_family=family, box_body_profile=body_profile,
        part_profiles=stored_profiles,
    )

def _end_cap_part_spec(self, val, *, is_tail):
    key = "tail" if is_tail else "head"
    stored_profiles = self.workspace_controller.profile_for(key)
    local_val = dict(val)
    local_val["fw"] = self._effective_endcap_fw(key, val.get("fw", 25.0))
    stored_profiles = _endcap_profiles_for_assembly(
        local_val, stored_profiles, self._current_box_assembly_type(), key
    )
    resolved_cuts = self._resolved_committed_assembly_relief_cuts(key, local_val, stored_profiles)
    formed_fw_left, formed_fw_right = formed_box_body_fw_widths(
        self.workspace_controller.box_body_profile() or (), local_val.get("t", 0.0)
    )
    return self._end_cap_part_spec_from_values(
        local_val, model_name=self._baseline_source_model(), is_tail=is_tail,
        holes=(self.tail_holes if is_tail else self.head_holes),
        corner_policy=(
            self._manual_corner_policy(key, local_val['fw'])
        ),
        fold_profiles=stored_profiles,
        depth_comp_t=self._endcap_depth_comp_t_for_family(self._baseline_source_model()),
        resolved_assembly_relief_cuts=resolved_cuts,
        box_body_formed_fw_left=formed_fw_left,
        box_body_formed_fw_right=formed_fw_right,
        box_body_structure_state=self.workspace_controller.box_body_structure_state(),
    )

def _door_part_spec_from_values(
    self, val, *, model_name, features, indicator_hole=None, door_indicator=None,
    door_indicator_offset=(0.0, 0.0), use_box_distance=False, corner_policy=None,
    frame_edges=None, indicator_window_groups=None,
) -> DoorPartSpec:
    """GUI submits operator inputs; Engine owns canonical Door manufacturing spec."""
    return manufacturing_api.build_door_operator_part_spec(
        val,
        model_name=model_name,
        features=features,
        indicator_hole=indicator_hole,
        door_indicator=door_indicator,
        door_indicator_offset=door_indicator_offset,
        use_box_distance=use_box_distance,
        corner_policy=corner_policy,
        frame_edges=frame_edges,
        indicator_window_groups=indicator_window_groups,
        nameplate_center_datum_top=getattr(
            self, "door_nameplate_center_datum_top", None
        ),
    )

def _single_door_part_spec(self, val, *, indicator_hole=None, door_indicator=None):
    return self._door_part_spec_from_values(
        val,
        model_name=self._baseline_source_model(),
        features=self.surface_features["door"],
        indicator_hole=indicator_hole,
        door_indicator=door_indicator,
        door_indicator_offset=(self.door_indicator_offset_x, self.door_indicator_offset_y),
        use_box_distance=bool(self.is_box_dist_var.get()),
        corner_policy=(
            self._manual_corner_policy(
                'door', self._door_material_frame_width(val['fw'], val['t'])
            )
        ),
    )

def _door_layout_part_spec(self, cell, val):
    key = self._door_layout_cell_key(cell)
    state = self._door_layout_indicator_state_for_key(key)
    layers = max(1, min(6, int(state.get("layers", 1))))
    groups = tuple(int(v) for v in list(state.get("groups", [2] * 6))[:layers])
    mode = state.get("mode", "indicator" if state.get("enabled") else "none")
    door_val = dict(val)
    door_val["w"] = cell.start_width
    door_val["h"] = cell.start_height
    return self._door_part_spec_from_values(
        door_val,
        model_name=self._baseline_source_model(),
        frame_edges=cell.edges,
        features=self.door_layout_features.get(key, []),
        indicator_hole=(manufacturing_api.indicator_box_opening_size(groups, thickness=val['t'])
                        if mode == "indicator_box" else None),
        door_indicator=(groups if mode == "indicator" else None),
        door_indicator_offset=(float(state.get("offset_x", 0.0)), float(state.get("offset_y", 0.0))),
        use_box_distance=bool(state.get("is_box_dist", False)),
        corner_policy=(
            self._manual_corner_policy(
                'door', self._door_material_frame_width(val['fw'], val['t'])
            )
        ),
    )

def _validate_indicator_state_fit(self, state, *, finished_width, finished_height, thickness):
    state = self._normalize_door_indicator_state(state)
    mode = state.get("mode", "none")
    if mode == "none":
        return (0.0, 0.0)
    layers = max(1, min(6, int(state.get("layers", 1))))
    groups = tuple(int(v) for v in list(state.get("groups", [2] * 6))[:layers])
    return manufacturing_api.validate_door_indicator_fit(
        mode=mode, groups=groups,
        finished_width=float(finished_width), finished_height=float(finished_height),
        thickness=float(thickness),
        offset=(float(state.get("offset_x", 0.0)), float(state.get("offset_y", 0.0))),
    )

def _validate_single_door_indicator_fit(self, val, state=None):
    state = self._single_door_indicator_state_snapshot() if state is None else state
    spec = self._single_door_part_spec(val)
    finished_w, finished_h = manufacturing_api.door_finished_face_size(spec)
    return self._validate_indicator_state_fit(
        state, finished_width=finished_w, finished_height=finished_h, thickness=val['t']
    )

def _validate_door_layout_indicator_fit(self, cell, state, val):
    spec = self._door_layout_part_spec(cell, val)
    finished_w, finished_h = manufacturing_api.door_finished_face_size(spec)
    return self._validate_indicator_state_fit(
        state, finished_width=finished_w, finished_height=finished_h, thickness=val['t']
    )

def _base_plate_part_spec_from_values(self, val, *, features, corner_policy=None):
    """Forward the current operator/saved sources to the headless Engine."""
    return manufacturing_api.build_base_plate_operator_part_spec(
        val,
        features=features,
        corner_policy=corner_policy,
        box_body_structure_state=self.workspace_controller.box_body_structure_state(),
        box_body_fold_profile=self.workspace_controller.box_body_profile() or (),
    )


def _base_plate_part_spec(self, val):
    return self._base_plate_part_spec_from_values(
        val, features=self.surface_features["base_plate"],
        corner_policy=self._manual_corner_policy("base_plate", val["fw"]),
    )


def _indicator_box_part_spec_from_values(self, val, layer_groups, *, features):
    return manufacturing_api.build_indicator_box_operator_part_spec(
        val, layer_groups, features=features,
    )


def _indicator_box_part_spec(self, val, layer_groups, *, features):
    return manufacturing_api.build_indicator_box_operator_part_spec(
        val, layer_groups, features=features,
    )

def _indicator_door_part_spec_from_values(self, val, layer_groups, *, features):
    """Map operator fields to the Engine-owned Small Door spec/context."""
    return manufacturing_api.indicator_small_door_operator_spec(
        layer_groups,
        thickness=val["t"],
        frame_width=val["fw"],
        door_gap_w=val["door_gap_w"],
        door_gap_h=val["door_gap_h"],
        indicator_door_fold=val.get("indicator_door_fold"),
        features=features,
    )

def _indicator_door_part_spec(self, val, layer_groups, *, features):
    spec, _context = self._indicator_door_part_spec_from_values(
        val, layer_groups, features=features
    )
    return spec

def _indicator_component_editor_contexts(self, state, val, *, box_features, door_features):
    """View-only adapter: ask the engine for physical surfaces and display them."""
    state = self._normalize_door_indicator_state(state)
    layers = max(1, min(6, int(state.get("layers", 1))))
    groups = tuple(int(v) for v in list(state.get("groups", [2] * 6))[:layers])
    if not groups:
        groups = (2,)
    door_spec = self._indicator_door_part_spec(val, groups, features=door_features)
    geometry = manufacturing_api.resolve_indicator_editor_components(
        groups, thickness=val["t"], door_spec=door_spec,
    )
    box = geometry["indicator_box"]
    door = geometry["indicator_door"]
    return {
        "indicator_box": {
            "part_key": "indicator_box", "title": "指示燈盒 — 盒體（基準檔＋指示燈）",
            "surface": box.surface, "width": box.width, "height": box.height,
            "reference_guide": box.reference_guide, "feature_list": box_features,
            "baseline_scene": box.baseline_scene,
            "baseline_status_text": (
                f"{box.baseline_status}｜排列 {list(groups)}｜{box.width:g} × {box.height:g} mm"
            ),
        },
        "indicator_door": {
            "part_key": "indicator_door", "title": "指示燈盒 — 小門（基準檔）",
            "surface": door.surface, "width": door.width, "height": door.height,
            "reference_guide": door.reference_guide, "feature_list": door_features,
            "baseline_scene": door.baseline_scene,
            "baseline_status_text": door.baseline_status,
        },
    }
