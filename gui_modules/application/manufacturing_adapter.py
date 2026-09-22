"""Manufacturing request adapters extracted from gui.py for #295/T7.

This module maps existing application/workspace state into established AE contract
objects and validation/export contexts.  AE/manufacturing modules remain the
geometry, formula, DXF and process authority.
"""
from copy import deepcopy
from dataclasses import replace

import ae_engine.ae as ae
from ae_engine import manufacturing_api
from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.contracts import (
    BasePlatePartSpec,
    BoxBodyPartSpec,
    DoorPartSpec,
    EndCapPartSpec,
    IndicatorBoxPartSpec,
    ManufacturingContext,
)
from ae_engine.sheetmetal_geometry import CornerTypeId
from ae_engine.sheetmetal_features import feature_surface_from_structural_result
from gui_modules.rendering import feature_surface_from_drawing_scene
from ae_engine.sheetmetal_part_adapters import (
    DoorFrameEdges,
    build_door_result,
    build_finished_reference_guide,
    build_indicator_box_result,
    build_unknown_door_result,
    build_unknown_indicator_box_result,
)
from phase6_endcap_semantics import (
    assembly_intent_value,
    normalize_endcap_bottom_wrap_state,
    resolve_endcap_bottom_wrap,
)
from phase6_fold_profiles import (
    build_endcap_xy_profiles,
    engine_segment_length_to_ui,
    formed_box_body_fw_widths,
    profile_to_fold_segments,
)


def _endcap_profiles_for_assembly(values, stored_profiles, assembly_type, part_key):
    """Return render profiles consistent with the current box assembly type.

    OVERLAY has no left/right X bends, even when the operator has never opened
    the 3D workspace (and therefore has no stored Phase6 profile yet).  Existing
    Y topology is preserved.  Switching back from OVERLAY restores the normal X
    topology from the shared scalar parameters without changing CornerType or
    the deferred bottom-corner rule.
    """
    intent_id = assembly_intent_value(assembly_type)
    source = dict(values or {})
    source["assembly_type"] = intent_id
    defaults = build_endcap_xy_profiles(source, part_key=part_key)
    profiles = deepcopy(dict(stored_profiles or {}))

    if not profiles:
        return defaults if intent_id == CornerTypeId.OVERLAY.value else None

    current_x = list(profiles.get("X", ()) or ())
    is_flat_x = len(current_x) == 1 and current_x[0].get("phase6_key") == "endcap_w_flat"
    if intent_id == CornerTypeId.OVERLAY.value or is_flat_x:
        profiles["X"] = deepcopy(defaults["X"])
    if not profiles.get("Y"):
        profiles["Y"] = deepcopy(defaults["Y"])
    return profiles

def _manufacturing_context(self, *, draw_stock=False):
    """GUI-owned execution context for the headless manufacturing boundary."""
    return ManufacturingContext(draw_stock=bool(draw_stock), overwrite=True)

def _box_body_part_spec_from_values(
    self, val, *, model_name, features, face_features,
    head_corner_policy=None, tail_corner_policy=None, fold_profile=None,
    structure_state=None, head_ybottom1=None, tail_ybottom1=None,
    snapshot=None,
):
    def resolved_ybottom(part_key):
        profiles = self.workspace_controller.profile_for(part_key) or {}
        rows = list(dict(profiles).get("Y", ()) or ())
        for row in rows:
            if str(row.get("phase6_key") or "") == "ybottom1":
                return float(engine_segment_length_to_ui(row))
        return float(val.get("ybottom1", ae.ybottom1_def))

    source_structure = (
        self.workspace_controller.box_body_structure_state()
        if structure_state is None else deepcopy(dict(structure_state or {}))
    )
    structure_state = cabinet_family_policy.resolve_box_body_structure_state(
        model_name, source_structure
    )

    back_panel_contract = {}
    if cabinet_family_policy.canonical_family_name(model_name) == "受電箱":
        from phase6_box_body_structure import BoxBodyStructureType
        from ae_engine.sheetmetal_geometry import box_body_height_from_corner_policies

        cfg = structure_state["configs"][BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value]
        panel_width = float(val["w"]) - float(cfg.get("back_width_comp_t", 0.0)) * float(val["t"])
        full_panel_height = box_body_height_from_corner_policies(
            float(val["h"]),
            float(val["t"]),
            head_corner_policy=head_corner_policy,
            tail_corner_policy=tail_corner_policy,
        )
        back_panel_contract = cabinet_family_policy.resolve_back_panel_contract(
            model_name,
            dict(snapshot or val),
            structure_state=structure_state,
            panel_width=panel_width,
            full_panel_height=full_panel_height,
        ) or {}

    return BoxBodyPartSpec(
        width=float(val['w']), height=float(val['h']), depth=float(val['d']),
        thickness=float(val['t']), frame_width=float(val['fw']),
        model_name=model_name,
        zl1=float(val['zl1']), zl2=float(val['zl2']),
        zr1=float(val['zr1']), zr2=float(val['zr2']),
        z_comp=float(val['z_comp']),
        fold_profile=profile_to_fold_segments(
            fold_profile if fold_profile is not None else (self.workspace_controller.box_body_profile() or ())
        ),
        features=tuple(features or ()),
        face_features={k: tuple(v) for k, v in dict(face_features or {}).items()},
        head_corner_policy=head_corner_policy, tail_corner_policy=tail_corner_policy,
        structure_state=deepcopy(dict(structure_state or {})),
        back_panel_contract=deepcopy(dict(back_panel_contract or {})),
        head_ybottom1=(resolved_ybottom("head") if head_ybottom1 is None else float(head_ybottom1)),
        tail_ybottom1=(resolved_ybottom("tail") if tail_ybottom1 is None else float(tail_ybottom1)),
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
    profiles = dict(fold_profiles or {})
    x_rows = [dict(row) for row in profiles.get("X", ())]
    y_rows = [dict(row) for row in profiles.get("Y", ())]

    if depth_comp_t is None:
        depth_comp_t = cabinet_family_policy.endcap_depth_comp_t(model_name)

    # Scalar folds remain the canonical/legacy request values.  Fold Profile
    # precedence is resolved exactly once inside AE manufacturing_api.
    fold_left = float(val['yl1'])
    fold_right = float(val['yr1'])
    fold_top = float(val['ytop1'])
    fold_bottom = float(val['ybottom1'])

    if box_body_structure_state is None:
        controller = getattr(self, "workspace_controller", None)
        getter = getattr(controller, "box_body_structure_state", None)
        resolved_structure_state = deepcopy(dict(getter() if callable(getter) else {}))
    else:
        resolved_structure_state = deepcopy(dict(box_body_structure_state or {}))
    if assembly_joints is None:
        joint_state = dict(getattr(self, "assembly_joint_state", {}) or {})
        resolved_assembly_joints = tuple(deepcopy(joint_state.get("assembly_joints", ())) or ())
    else:
        resolved_assembly_joints = tuple(deepcopy(tuple(assembly_joints or ())))
        joint_state = {"assembly_joints": resolved_assembly_joints}
    if cabinet_family_policy.supports_bottom_wrap_controls(model_name):
        try:
            part_key = "tail" if is_tail else "head"
            wrap_state = endcap_bottom_wrap_state
            if wrap_state is None:
                wrap_state = getattr(self, "endcap_bottom_wrap_state", None)
            if wrap_state is None:
                wrap_state = normalize_endcap_bottom_wrap_state({"model": model_name})
            projection_snapshot = {"model": model_name, **joint_state}
            item = resolve_endcap_bottom_wrap(projection_snapshot, part_key, state=wrap_state)
            # enabled is graph-owned; Receiving state retains only geometric
            # reserve inputs for the certified BOTTOM WRAP formula.
            resolved_structure_state = cabinet_family_policy.set_bottom_relief_reserves(
                model_name,
                resolved_structure_state,
                reserve_u=item["reserve_u"],
                reserve_v=item["reserve_v"],
            )
        except Exception:
            pass

    return EndCapPartSpec(
        width=float(val['w']), height=float(val['h']), depth=float(val['d']),
        thickness=float(val['t']), frame_width=float(val['fw']),
        model_name=model_name, is_tail=bool(is_tail),
        fold_left=fold_left, fold_right=fold_right,
        fold_top=fold_top, fold_bottom=fold_bottom,
        box_fold_left=float(val['zl1']), box_fold_right=float(val['zr1']),
        box_body_formed_fw_left=(None if box_body_formed_fw_left is None else float(box_body_formed_fw_left)),
        box_body_formed_fw_right=(None if box_body_formed_fw_right is None else float(box_body_formed_fw_right)),
        box_body_structure_state=resolved_structure_state,
        assembly_joints=resolved_assembly_joints,
        fold_profile_x=profile_to_fold_segments(x_rows),
        fold_profile_y=profile_to_fold_segments(y_rows),
        holes=tuple(holes or ()), corner_policy=corner_policy,
        depth_comp_t=float(depth_comp_t),
        resolved_assembly_relief_cuts=tuple(
            tuple((float(x), float(y)) for x, y in polygon)
            for polygon in tuple(resolved_assembly_relief_cuts or ())
            if len(polygon) >= 3
        ),
    )

@staticmethod
def _phase6_relief_profile_signature(profile):
    rows = []
    for row in list(profile or ()):
        row = dict(row or {})
        rows.append((
            str(row.get("phase6_key") or ""),
            round(float(row.get("len", row.get("length", 0.0)) or 0.0), 6),
            None if row.get("angle") is None else round(float(row.get("angle") or 0.0), 6),
            str(row.get("core") or ""),
        ))
    return tuple(rows)

def _resolved_committed_assembly_relief_cuts(self, key, val, stored_profiles):
    state = deepcopy(getattr(self, "assembly_relief_state", {}) or {})
    if not bool(state.get("enabled")):
        return ()
    part = dict((state.get("parts") or {}).get(str(key), {}) or {})
    if not bool(part.get("verified")) and not bool(part.get("canonical_accepted")):
        return ()
    trust_level = str(part.get("trust_level") or "")
    rule_id = part.get("rule_id")
    rule_revision = part.get("rule_revision")
    if trust_level in {"CERTIFIED", "CERTIFIED_FROM_3D", "ENGINE_CONFLICT"} and rule_id:
        from ae_engine.certified_relief_registry import certified_rule_revision_exists
        try:
            active_revision = certified_rule_revision_exists(str(rule_id), int(rule_revision))
        except (TypeError, ValueError):
            active_revision = False
        if not active_revision:
            return ()
    source = dict(state.get("source") or {})
    from ae_engine.certified_relief_registry import RELIEF_CONTRACT_VERSION
    try:
        if int(source.get("relief_contract_version", 0) or 0) != RELIEF_CONTRACT_VERSION:
            return ()
    except (TypeError, ValueError):
        return ()

    # Replay identity is mechanical, not the high-level assembly mirror.
    # Graph/family/structure must all match the state that was shadow-verified.
    from ae_engine.assembly_joint import resolved_joint_graph_fingerprint
    import hashlib as _hashlib, json as _json
    try:
        current_graph_fp = resolved_joint_graph_fingerprint(dict(getattr(self, "assembly_joint_state", {}) or {}))
    except Exception:
        return ()
    if not str(source.get("joint_graph_fingerprint") or "") or str(source.get("joint_graph_fingerprint")) != current_graph_fp:
        return ()
    controller = getattr(self, "workspace_controller", None)
    structure_getter = getattr(controller, "box_body_structure_state", None)
    current_structure = structure_getter() if callable(structure_getter) else {}
    structure_payload = _json.dumps(current_structure or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    current_structure_fp = _hashlib.sha256(structure_payload.encode("utf-8")).hexdigest()
    if not str(source.get("family_structure_fingerprint") or "") or str(source.get("family_structure_fingerprint")) != current_structure_fp:
        return ()
    family_getter = getattr(self, "_baseline_source_model", None)
    current_family = str(family_getter() if callable(family_getter) else "")
    if str(source.get("cabinet_family") or "") != current_family:
        return ()

    saved_formed = dict(source.get("box_body_formed_fw") or {})
    if saved_formed:
        body_profile_getter = getattr(controller, "box_body_profile", None)
        current_formed_left, current_formed_right = formed_box_body_fw_widths(
            body_profile_getter() if callable(body_profile_getter) else (),
            float(val.get("t", 0.0) or 0.0),
        )
        for side, current in (("left", current_formed_left), ("right", current_formed_right)):
            try:
                if current is None or abs(float(saved_formed[side]) - float(current)) > 1e-6:
                    return ()
            except (KeyError, TypeError, ValueError):
                return ()

    source_rules = dict(source.get("registry_rules") or {})
    if trust_level in {"CERTIFIED", "CERTIFIED_FROM_3D", "ENGINE_CONFLICT"} and rule_id:
        saved_rule = dict(source_rules.get(str(key)) or {})
        try:
            if str(saved_rule.get("rule_id") or "") != str(rule_id):
                return ()
            if int(saved_rule.get("revision", 0) or 0) != int(rule_revision):
                return ()
        except (TypeError, ValueError):
            return ()

    source_profiles = dict(source.get("part_profiles") or {})
    expected = dict(source_profiles.get(str(key), {}) or {})
    current_scalars = {
        "w": float(val.get("w", 0.0)),
        "h": float(val.get("h", 0.0)),
        "d": float(val.get("d", 0.0)),
        "t": float(val.get("t", 0.0)),
        "fw": float(val.get("fw", 0.0)),
        "zl1": float(val.get("zl1", ae.zl1_def)),
        "zr1": float(val.get("zr1", ae.zr1_def)),
        "yl1": float(val.get("yl1", ae.yl1_def)),
        "yr1": float(val.get("yr1", ae.yr1_def)),
        "ytop1": float(val.get("ytop1", ae.ytop1_def)),
        "ybottom1": float(val.get("ybottom1", ae.ybottom1_def)),
    }
    for name, current in current_scalars.items():
        if name not in source:
            continue
        # ytop1 is an optional legacy aggregate. Once a saved Y Fold
        # Profile exists, that profile is the authoritative topology/length
        # fingerprint; comparing the legacy scalar as well can reject a
        # valid committed 3D relief when the top fold was structurally
        # removed (the editor adapter correctly reports ytop1=0).
        if name == "ytop1" and "Y" in expected:
            continue
        try:
            if abs(float(source[name]) - current) > 1e-6:
                return ()
        except (TypeError, ValueError):
            return ()
    for axis in ("X", "Y"):
        expected_rows = expected.get(axis)
        if expected_rows is None:
            continue
        current_rows = dict(stored_profiles or {}).get(axis, ())
        if self._phase6_relief_profile_signature(expected_rows) != self._phase6_relief_profile_signature(current_rows):
            return ()
    cuts = []
    for polygon in list(part.get("cuts") or ()):
        coords = tuple((float(point[0]), float(point[1])) for point in polygon if len(point) >= 2)
        if len(coords) >= 3:
            cuts.append(coords)
    return tuple(cuts)

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
):
    """Canonical Door state -> DoorPartSpec mapping used by 2D and 3D."""
    return DoorPartSpec(
        width=float(val['w']), height=float(val['h']),
        thickness=float(val['t']), frame_width=float(val['fw']),
        model_name=model_name,
        gap_w=float(val['door_gap_w']), gap_h=float(val['door_gap_h']),
        fold_left=float(val['door_fold_l']), fold_right=float(val['door_fold_r']),
        fold_top=float(val['door_fold_t']), fold_bottom=float(val['door_fold_b']),
        frame_edges=frame_edges or DoorFrameEdges(),
        features=tuple(features or ()), feature_space="legacy_unfolded",
        indicator_hole=indicator_hole,
        door_indicator=tuple(door_indicator) if door_indicator else None,
        door_indicator_offset=(float(door_indicator_offset[0]), float(door_indicator_offset[1])),
        use_box_distance=bool(use_box_distance),
        corner_policy=corner_policy,
        indicator_window_groups=(tuple(indicator_window_groups) if indicator_window_groups else None),
        nameplate_center_datum_top=(
            None if getattr(self, "door_nameplate_center_datum_top", None) is None
            else float(self.door_nameplate_center_datum_top)
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
    return BasePlatePartSpec(
        width=float(val['w']), height=float(val['h']), thickness=float(val['t']),
        shrink_top=float(val['base_plate_shrink_top']),
        shrink_bottom=float(val['base_plate_shrink_bottom']),
        shrink_left=float(val['base_plate_shrink_left']),
        shrink_right=float(val['base_plate_shrink_right']),
        bend=float(val['base_plate_bend']),
        features=tuple(features or ()), corner_policy=corner_policy,
        box_body_structure_state=self.workspace_controller.box_body_structure_state(),
        box_body_fold_profile=profile_to_fold_segments(self.workspace_controller.box_body_profile() or ()),
        model_name=str(val.get('model', '')).strip() or None,
    )

def _base_plate_part_spec(self, val):
    return self._base_plate_part_spec_from_values(
        val, features=self.surface_features["base_plate"],
        corner_policy=(
            self._manual_corner_policy('base_plate', val['fw'])
        ),
    )

def _indicator_box_part_spec_from_values(self, val, layer_groups, *, features):
    return IndicatorBoxPartSpec(
        layer_groups=tuple(int(v) for v in layer_groups),
        thickness=float(val['t']), model_name=None,
        features=tuple(features or ()), corner_policy=None,
    )

def _indicator_box_part_spec(self, val, layer_groups, *, features):
    return IndicatorBoxPartSpec(
        layer_groups=tuple(int(v) for v in layer_groups),
        thickness=float(val['t']), model_name=None,
        features=tuple(features or ()), corner_policy=None,
    )

def _indicator_door_part_spec_from_values(self, val, layer_groups, *, features):
    groups = tuple(int(v) for v in layer_groups)
    policy = replace(
        manufacturing_api.resolve_policy(),
        frame_width=float(val['fw']),
        door_gap_w=float(val['door_gap_w']),
        door_gap_h=float(val['door_gap_h']),
        indicator_small_door_fold=float(
            val.get('indicator_door_fold', getattr(ae, 'indicator_small_door_fold_def', 19.0))
        ),
    )
    context = ManufacturingContext(policy=policy, draw_stock=False)
    base = manufacturing_api.indicator_small_door_spec(
        groups, thickness=float(val['t']), context=context
    )
    spec = replace(
        base, features=tuple(features or ()), feature_space="legacy_unfolded",
        corner_policy=None, model_name=None,
    )
    return spec, context

def _indicator_door_part_spec(self, val, layer_groups, *, features):
    spec, _context = self._indicator_door_part_spec_from_values(
        val, layer_groups, features=features
    )
    return spec

def _indicator_component_editor_contexts(self, state, val, *, box_features, door_features):
    """Build the two editable members of one Door-owned indicator-box assembly."""
    state = self._normalize_door_indicator_state(state)
    layers = max(1, min(6, int(state.get("layers", 1))))
    groups = tuple(int(v) for v in list(state.get("groups", [2] * 6))[:layers])
    if not groups:
        groups = (2,)

    # Box and small door are global shared parts, independent of the cabinet model.
    # GUI identifies the part role only; AE owns the physical shared-baseline namespace.
    box_corner_policy = None
    box_data = ae.get_stretched_indicator_box_data(
        None, groups, val['t'], corner_policy=None
    )
    box_baseline_scene = box_data.scene
    box_status = ae.indicator_shared_baseline_source_label("盒子.dxf")
    box_surface = feature_surface_from_drawing_scene("indicator_box", box_data.scene)
    box_w = float(box_data.params['w'])
    box_h = float(box_data.params['h'])
    box_fold = float(getattr(ae, 'indicator_box_fold_def', 49.0))
    box_result = (
        build_unknown_indicator_box_result(
            total_width=box_w, total_height=box_h, t=val['t'], fold=box_fold,
            corner_policy=box_corner_policy,
        ) if box_corner_policy is not None else
        build_indicator_box_result(total_width=box_w, total_height=box_h, t=val['t'], fold=box_fold)
    )
    box_guide = build_finished_reference_guide(
        "indicator_box", box_result,
        finished_width=box_w - 2.0 * box_fold + val['t'],
        finished_height=box_h - 2.0 * box_fold + val['t'],
    )

    door_spec = self._indicator_door_part_spec(val, groups, features=door_features)
    finished_w, finished_h = manufacturing_api.door_finished_face_size(door_spec)
    if door_spec.corner_policy is not None:
        door_result = build_unknown_door_result(
            w=door_spec.width, h=door_spec.height, t=door_spec.thickness, fw=door_spec.frame_width,
            gap_w=door_spec.gap_w, gap_h=door_spec.gap_h,
            fold_left=door_spec.fold_left, fold_right=door_spec.fold_right,
            fold_top=door_spec.fold_top, fold_bottom=door_spec.fold_bottom,
            corner_policy=door_spec.corner_policy,
        )
        door_surface = feature_surface_from_structural_result("indicator_door", door_result)
        door_width, door_height = door_result.width, door_result.height
        door_baseline_scene = None
        door_status = "自訂 / 手動截角"
    else:
        door_data = ae.get_stretched_door_data(
            None, door_spec.width, door_spec.height, door_spec.thickness, door_spec.frame_width,
            door_spec.gap_w, door_spec.gap_h,
            door_spec.fold_left, door_spec.fold_right, door_spec.fold_top, door_spec.fold_bottom,
            indicator_window_groups=groups,
        )
        door_surface = feature_surface_from_drawing_scene("indicator_door", door_data.scene)
        door_width = float(door_data.params['total_width'])
        door_height = float(door_data.params['total_depth'])
        door_result = build_door_result(
            w=door_spec.width, h=door_spec.height, t=door_spec.thickness, fw=door_spec.frame_width,
            gap_w=door_spec.gap_w, gap_h=door_spec.gap_h,
            fold_left=door_spec.fold_left, fold_right=door_spec.fold_right,
            fold_top=door_spec.fold_top, fold_bottom=door_spec.fold_bottom,
        )
        door_baseline_scene = door_data.scene
        door_status = ae.indicator_shared_baseline_source_label("小門.dxf")
    door_guide = build_finished_reference_guide(
        "indicator_door", door_result,
        finished_width=float(finished_w), finished_height=float(finished_h),
    )

    return {
        "indicator_box": {
            "part_key": "indicator_box", "title": "指示燈盒 — 盒體（基準檔＋指示燈）",
            "surface": box_surface, "width": box_w, "height": box_h,
            "reference_guide": box_guide, "feature_list": box_features,
            "baseline_scene": box_baseline_scene,
            "baseline_status_text": (
                f"{box_status}｜排列 {list(groups)}｜{box_w:g} × {box_h:g} mm"
            ),
        },
        "indicator_door": {
            "part_key": "indicator_door", "title": "指示燈盒 — 小門（基準檔）",
            "surface": door_surface, "width": door_width, "height": door_height,
            "reference_guide": door_guide, "feature_list": door_features,
            "baseline_scene": door_baseline_scene, "baseline_status_text": door_status,
        },
    }
