# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""Manufacturing/payload projection seam extracted from fold_designer_adapter.

This module adapts application state to existing authoritative manufacturing APIs.
It owns no project/workspace/navigation state.
"""
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

from ae_engine import manufacturing_api
from ae_engine.contracts import ManufacturingContext
from gui_modules.application.state_sync import Phase6DerivedCacheOwner
from gui_modules.parts.panels.divider import collect_divider_input
from gui_modules.parts.panels.door import collect_door_input
from gui_modules.parts.panels.indicator_box import collect_indicator_box_input
from gui_modules.parts.panels.multipart import collect_multipart_input

def _fold_designer_secondary_scene_rows(scene):
    """GUI compatibility port; manufacturing projection belongs to Engine."""
    return manufacturing_api.fold_designer_secondary_scene_rows(scene)


def _query_fold_designer_baseline_data(self, part_key, model, values):
    """Read operator inputs and display the Engine-owned source-hole result."""
    model = str(model or "").strip()
    if not model or manufacturing_api.is_unknown_operator_model(model):
        return []
    v = dict(values or {})
    try:
        v.setdefault("w", self.w_var.get())
        v.setdefault("h", self.h_var.get())
        v.setdefault("d", self.d_var.get())
        v.setdefault("t", self.t_var.get())
        v.setdefault("fw", self.fw_z_var.get())
        return manufacturing_api.query_fold_designer_baseline_rows(part_key, model, v)
    except Exception:
        # Preserve optional, read-only baseline-panel fallback; never export.
        return []


def _apply_cabinet_family_endcap_policy(
    self, policy, part_key, *, snapshot=None, thickness=None, structure_state=None
):
    """Forward operator family/structure inputs to authoritative Engine policy."""
    if policy is None or str(part_key) not in {"head", "tail"}:
        return policy
    family_source = self._current_cabinet_type_name() if snapshot is None else snapshot
    if structure_state is None:
        try:
            structure_state = self.workspace_controller.box_body_structure_state()
        except Exception:
            structure_state = None
    if thickness is None:
        try:
            thickness = float(self.t_var.get())
        except Exception:
            thickness = None
    return manufacturing_api.apply_cabinet_family_endcap_policy(
        policy, part_key, family_source=family_source,
        structure_state=structure_state, thickness=thickness,
    )


def _fold_designer_corner_policy_from_payload(corner_state, part_key, fw):
    """Compatibility GUI seam: Engine builds the canonical CornerType policy."""
    return manufacturing_api.corner_policy_from_payload(corner_state, part_key, fw)


def _read_live_receiving_snapshot(self):
    """Prefer live Fold Designer application ownership over a stale bridge copy."""
    app = getattr(self, "fold_designer_app", None)
    live = getattr(app, "_phase6_input_snapshot", None) if app is not None else None
    return live if live is not None else getattr(self, "_phase6_input_snapshot", None)


def _authoritative_render_data(self, spec, context=None):
    """Build raw 2D/3D material from the exact typed manufacturing PartSpec.

    The primary authoritative cache is always cleared on a geometry edit.
    Only source-certified Receiving Set/Bay raw material may cross W/H/D
    edits on an unchanged typed Spec/Context. EndCap raw reuse excludes
    committed relief cuts and embedded assembly relief; the canonical
    downstream Joint/collision solver still runs on every changed state.
    The complete manufacturing resolver (Joint/collision/placement/relief)
    still executes after each changed global manufacturing state.
    """
    ctx = context or ManufacturingContext(draw_stock=False)
    cache = getattr(self, "_authoritative_part_render_cache", None)
    if cache is None:
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is None:
            owner = self._derived_cache_owner = Phase6DerivedCacheOwner()
        cache = self._authoritative_part_render_cache = owner.cache("authoritative_render")
    owner = getattr(self, "_derived_cache_owner", None)
    cache_key = (repr(spec), repr(ctx))
    snapshot = _read_live_receiving_snapshot(self)
    # Engine alone decides physical source eligibility, structure coverage
    # and Head/Tail DXF witness. GUI owns only bounded LRU and invalidation.
    plan = (
        manufacturing_api.plan_operator_raw_material_reuse(
            spec, snapshot, context=ctx,
        )
        if isinstance(owner, Phase6DerivedCacheOwner) else None
    )
    history = (
        owner._receiving_exact_material_history
        if plan is not None and plan.eligible else None
    )
    source_stamp = plan.source_stamp if plan is not None else None
    if history is not None:
        if source_stamp is None:
            history.clear()
            owner._receiving_exact_material_stamp = None
            cache.clear()
        elif owner._receiving_exact_material_stamp != source_stamp:
            history.clear()
            cache.clear()
            owner._receiving_exact_material_stamp = source_stamp
        if source_stamp is not None and cache_key not in cache and cache_key in history:
            render_data = history[cache_key]
            history.move_to_end(cache_key)
            cache[cache_key] = render_data
            if len(cache) > 32:
                cache.pop(next(iter(cache)))
            return render_data
    if cache_key in cache:
        return cache[cache_key]
    render_data = manufacturing_api.build_operator_part_render_data(spec, ctx)
    cache[cache_key] = render_data
    if len(cache) > 32:
        cache.pop(next(iter(cache)))
    if history is not None and source_stamp is not None:
        history[cache_key] = render_data
        history.move_to_end(cache_key)
        if len(history) > 8:
            history.popitem(last=False)
    return render_data


def _require_verified_baseline_sources_for_manufacturing(self):
    """GUI only forwards operator-selected model; Engine verifies source custody."""
    model = self._baseline_source_model() if hasattr(self, "_baseline_source_model") else ""
    return manufacturing_api.require_verified_operator_baseline_sources(model)

def _export_authoritative_part(self, spec, output_path, context=None):
    """Save the exact cached FinalScene used by 2D/3D without rebuilding it."""
    self._flush_phase6_authoritative_state()
    owner = getattr(self, "workspace_controller", None)
    if owner is not None and owner.workspace_snapshot().get("receiving_quantity_box"):
        manufacturing_api.require_valid_operator_quantity_features(
            self._make_original_fold_designer_snapshot(),
        )
    self._require_verified_baseline_sources_for_manufacturing()
    ctx = context or self._manufacturing_context(draw_stock=False)
    render_data = self._authoritative_render_data(spec, ctx)
    if getattr(render_data, "pieces", None):
        output = Path(output_path)
        return manufacturing_api.generate_box_body_structure_parts(
            spec, output.parent, ctx,
            resolved_render_data=render_data, verify_reopen=True,
        )
    return manufacturing_api.save_part_render_data_dxf(
        render_data, output_path,
        overwrite=bool(getattr(ctx, "overwrite", False)),
        verify_reopen=True,
    )

def _box_body_divider_from_payload(key, payload):
    """UI input normalization only; Engine selects the physical Divider."""
    divider_input = collect_divider_input(
        key, payload, default_depth=manufacturing_api.fold_designer_legacy_source_default("d"),
        default_thickness=manufacturing_api.fold_designer_legacy_source_default("t"),
    )
    return manufacturing_api.resolve_fold_designer_divider_part(key, divider_input)


def _inner_door_frame_from_payload(key, payload):
    """The Engine owns Family/legacy frame topology and stable identity."""
    return manufacturing_api.resolve_fold_designer_frame_part(
        key, payload,
        default_thickness=manufacturing_api.fold_designer_legacy_source_default("t"),
    )


def _query_receiving_resolved_base_render_data(self, key, payload):
    """GUI supplies current source and lazy FinalScene callback; Engine decides sheet."""
    owner = getattr(self, "fold_designer_app", None)
    return manufacturing_api.resolve_operator_receiving_base_2d_source(
        key, payload,
        getattr(owner, "_phase6_input_snapshot", None),
        cached_geometry=getattr(owner, "_phase6_last_resolved_manufacturing_geometry", None),
        resolve_geometry=getattr(owner, "_phase6_resolve_manufacturing_geometry", None),
    )


def _query_fold_designer_render_data(self, part_key, payload):
    def sheet(render):
        return manufacturing_api.with_physical_sheet_features(
            str(part_key), render, (payload or {}).get('features', ()),
        )
    """Return the same authoritative final geometry used by 2D consumers."""
    key = str(part_key or "")
    source_plan = manufacturing_api.plan_operator_manufacturing_part_source(key)
    if source_plan.input_adapter == "indicator":
        payload = collect_indicator_box_input(payload)
    elif source_plan.input_adapter == "multipart":
        payload = collect_multipart_input(payload)
    elif source_plan.input_adapter == "door":
        payload = collect_door_input(payload)
    receiving_base = _query_receiving_resolved_base_render_data(self, key, payload)
    if receiving_base is not None:
        return receiving_base
    if source_plan.render_source == "nfb_pad":
        owner = getattr(self, "fold_designer_app", None)
        return sheet(manufacturing_api.resolve_operator_receiving_pad_2d_source(
            key, getattr(owner, "_phase6_input_snapshot", None),
        ))
    if source_plan.render_source == "fixing_plate":
        return sheet(manufacturing_api.resolve_operator_receiving_fixing_2d_source(
            key, payload, live_snapshot=_read_live_receiving_snapshot(self),
        ))
    if source_plan.render_source == "divider":
        divider = _box_body_divider_from_payload(key, payload)
        return sheet(manufacturing_api.build_box_body_divider_render_data(divider))

    if source_plan.render_source == "inner_panel":
        panel = manufacturing_api.resolve_fold_designer_panel_part(key, payload)
        features = tuple(dict(payload or {}).get("features") or ())
        # The canonical inner-door panel factory consumes only the immutable
        # physical panel and finished-face features. It reads no DXF/source
        # file. Do not apply this cross-transaction reuse to frame/divider
        # factories: those read dedicated physical baseline source data.
        snapshot = _read_live_receiving_snapshot(self)
        owner = getattr(self, "_derived_cache_owner", None)
        # Engine owns physical panel identity, active Bay Family and the
        # deterministic source-free Feature signature. GUI owns only the LRU.
        fingerprint = (
            manufacturing_api.project_operator_inner_door_panel_preview_cache_signature(
                snapshot, panel, features,
            )
            if isinstance(owner, Phase6DerivedCacheOwner) else None
        )
        if fingerprint is not None:
            history = owner._receiving_inner_door_panel_history
            if fingerprint in history:
                history.move_to_end(fingerprint)
                return history[fingerprint]
            material = manufacturing_api.build_inner_door_panel_render_data(
                panel, features=features)
            history[fingerprint] = material
            history.move_to_end(fingerprint)
            while len(history) > 8:
                history.popitem(last=False)
            return material
        return manufacturing_api.build_inner_door_panel_render_data(
            panel, features=features,
        )

    if source_plan.render_source == "inner_frame":
        frame = _inner_door_frame_from_payload(key, payload)
        return sheet(manufacturing_api.build_inner_door_frame_render_data(frame))

    spec, context = self._fold_designer_part_spec_from_payload(part_key, payload)
    # The single authoritative PartSpec cache already dispatches integral
    # versus multipart BoxBody to the correct manufacturing-owned factory.
    # Calling build_box_body_structure_render_data directly here bypassed that
    # exact Spec/Context cache, rebuilding the same physical 2D/3D geometry
    # multiple times between geometry invalidations.
    return self._authoritative_render_data(spec, context)

def _payload_topology_context(part_key, payload):
    """GUI compatibility: Engine owns physical Door/BasePlate cell selection."""
    return manufacturing_api.resolve_fold_designer_payload_topology(
        part_key, payload,
    )


def _payload_policy(self, data, corner_state, part, fw, unknown, thickness):
    resolved = self._fold_designer_corner_policy_from_payload(corner_state, part, fw)
    if resolved is None and not unknown:
        resolved = manufacturing_api.corner_policy_from_payload(
            corner_state, part, fw,
            known_family=self._current_cabinet_type_name(),
        )
    return self._apply_cabinet_family_endcap_policy(
        resolved,
        part,
        snapshot=data,
        thickness=thickness,
        structure_state=data.get("box_body_structure"),
    )

def _door_part_spec_from_payload_context(
    self, data, w, h, t, fw, model, unknown, features, policy, door_cell
):
    if door_cell is not None:
        cell_key = f"{door_cell.column_index}:{door_cell.row_index}"
        states = dict(
            data.get("door_layout_indicator_states")
            or getattr(self, "door_layout_indicator_states", None)
            or {}
        )
        state = manufacturing_api.project_operator_door_cell_indicator_manufacturing_source(
            states.get(cell_key)
        )
        mode = state["mode"]
        groups = tuple(state["groups"][:state["layers"]]) if mode != "none" else ()
        indicator_hole = (
            manufacturing_api.indicator_box_opening_size(groups, thickness=t)
            if mode == "indicator_box" else None
        )
        direct = groups if mode == "indicator" else ()
        ind_offset = (float(state.get("offset_x", 0.0)), float(state.get("offset_y", 0.0)))
        use_box_dist = bool(state.get("is_box_dist", False))
    else:
        box_enabled = bool(data.get("door_indicator_box_enabled"))
        groups = (
            manufacturing_api.normalize_fold_designer_indicator_groups(
                data.get("indicator_layer_groups") or (),
            ) if box_enabled else ()
        )
        direct_source = data.get("door_indicator_groups") or ()
        direct = (
            manufacturing_api.normalize_fold_designer_indicator_groups(direct_source)
            if direct_source else ()
        )
        indicator_hole = (
            manufacturing_api.indicator_box_opening_size(groups, thickness=t)
            if box_enabled else None
        )
        ind_offset = tuple(data.get("door_indicator_offset") or (0.0, 0.0))
        use_box_dist = bool(data.get("use_box_distance", False))
    return self._door_part_spec_from_values(
        {
            "w": w, "h": h, "t": t, "fw": fw,
            **manufacturing_api.resolve_fold_designer_legacy_numeric_settings(
                data, part_name="door",
            ),
        },
        model_name=(None if unknown else model),
        features=features,
        indicator_hole=indicator_hole,
        door_indicator=(direct or None),
        door_indicator_offset=ind_offset,
        use_box_distance=use_box_dist,
        corner_policy=policy,
        frame_edges=(door_cell.edges if door_cell is not None else None),
    )


def _fold_designer_part_spec_from_payload(self, part_key, payload):
    """Convert Fold Designer draft state to the canonical manufacturing request."""
    (
        data, key, w, h, d, t, fw, model, unknown, corner_state,
        features, face_features, door_cell, base_plate_cell,
    ) = _payload_topology_context(part_key, payload)
    payload_policy = lambda part: _payload_policy(
        self, data, corner_state, part, fw, unknown, t
    )
    policy_part = (
        "door" if door_cell is not None
        else ("base_plate" if base_plate_cell is not None else key)
    )
    if manufacturing_api.is_custom_part(key):
        return manufacturing_api.custom_part_spec(
            data, key, features=features, profiles=data.get("fold_profiles"),
        ), ManufacturingContext(draw_stock=False)
    policy = payload_policy(policy_part)
    context = ManufacturingContext(draw_stock=False)

    if key == "box_body":
        box_source = manufacturing_api.resolve_fold_designer_legacy_numeric_settings(
            data, part_name="box_body",
        )
        spec = self._box_body_part_spec_from_values(
            {
                "w": w, "h": h, "d": d, "t": t, "fw": fw,
                **{name: box_source[name] for name in (
                    "zl1", "zl2", "zr1", "zr2", "z_comp",
                )},
            },
            model_name=(None if unknown else model),
            features=features,
            face_features=face_features,
            head_corner_policy=payload_policy("head"),
            tail_corner_policy=payload_policy("tail"),
            fold_profile=data.get("fold_profile"),
            structure_state=data.get("box_body_structure"),
            snapshot=data,
            head_ybottom1=box_source["head_ybottom1"],
            tail_ybottom1=box_source["tail_ybottom1"],
        )
    elif key in {"head", "tail"}:
        endcap_values = {
            "w": w, "h": h, "d": d, "t": t, "fw": fw,
            **manufacturing_api.resolve_fold_designer_legacy_numeric_settings(
                data, part_name=key,
            ),
        }
        resolved_cuts = data.get("resolved_assembly_relief_cuts")
        if resolved_cuts is None and bool(data.get("_use_committed_relief")):
            resolved_cuts = self._resolved_committed_assembly_relief_cuts(
                key, endcap_values, data.get("fold_profiles") or {}
            )
        formed_fw_left, formed_fw_right = manufacturing_api.formed_box_body_fw_widths(
            data.get("box_body_profile") or self.workspace_controller.box_body_profile() or (),
            t,
        )
        spec = self._end_cap_part_spec_from_values(
            endcap_values,
            model_name=(None if unknown else model),
            is_tail=(key == "tail"),
            holes=features,
            corner_policy=policy,
            fold_profiles=data.get("fold_profiles"),
            resolved_assembly_relief_cuts=resolved_cuts or (),
            box_body_formed_fw_left=formed_fw_left,
            box_body_formed_fw_right=formed_fw_right,
            box_body_structure_state=(
                data.get("box_body_structure")
                or self.workspace_controller.box_body_structure_state()
            ),
            endcap_bottom_wrap_state=data.get("endcap_bottom_wrap"),
            assembly_joints=data.get("assembly_joints"),
        )
    elif key == "door" or door_cell is not None:
        spec = _door_part_spec_from_payload_context(
            self, data, w, h, t, fw, model, unknown, features, policy, door_cell
        )
    elif key == "base_plate" or key.startswith("base_plate_c"):
        # GUI forwards the operator payload, current selected cell and policy.
        # Engine alone chooses any actual Receiving NFB physical BasePlate.
        values, base_policy = manufacturing_api.resolve_fold_designer_base_plate_source(
            key, data, width=w, height=h, thickness=t, frame_width=fw,
            model_name=model, corner_policy=policy,
        )
        spec = self._base_plate_part_spec_from_values(
            values, features=features, corner_policy=base_policy,
        )
    elif key == "indicator_box":
        groups = manufacturing_api.normalize_fold_designer_indicator_groups(
            data["indicator_layer_groups"] if "indicator_layer_groups" in data else (1,)
        )
        spec = self._indicator_box_part_spec_from_values({"t": t}, groups, features=features)
    elif key == "indicator_door":
        groups = manufacturing_api.normalize_fold_designer_indicator_groups(
            data["indicator_layer_groups"] if "indicator_layer_groups" in data else (1,)
        )
        spec, context = self._indicator_door_part_spec_from_values(
            {
                "t": t,
                "fw": fw,
                **manufacturing_api.resolve_fold_designer_legacy_numeric_settings(
                    data, part_name="indicator_door",
                ),
            },
            groups,
            features=features,
        )
    else:
        raise ValueError(f"未知 3D 板件: {key}")
    return spec, context
