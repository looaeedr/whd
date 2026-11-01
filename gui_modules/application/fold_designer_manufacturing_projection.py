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

import ae_engine.ae as ae
from ae_engine import manufacturing_api
from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.contracts import BoxBodyPartSpec, EndCapPartSpec, ManufacturingContext
from ae_engine.corner_type_ui import (
    is_unknown_model,
)
from ae_engine.sheetmetal_part_adapters import DoorFrameEdges
from phase6_fold_profiles import formed_box_body_fw_widths
from gui_modules.application.state_sync import Phase6DerivedCacheOwner
from gui_modules.parts.panels.divider import collect_divider_input
from gui_modules.parts.panels.door import collect_door_input, normalize_door_indicator_state
from gui_modules.parts.panels.indicator_box import collect_indicator_box_input
from gui_modules.parts.panels.multipart import collect_multipart_input

def _fold_designer_secondary_scene_rows(scene):
    """GUI compatibility port; manufacturing projection belongs to Engine."""
    return manufacturing_api.fold_designer_secondary_scene_rows(scene)


def _query_fold_designer_baseline_data(self, part_key, model, values):
    """Read operator inputs and display the Engine-owned source-hole result."""
    model = str(model or "").strip()
    if not model or is_unknown_model(model):
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
    # EndCap raw material is independent of a different Bay's W/H/D only
    # when the exact typed inputs are identical and no pre-solved assembly
    # cuts/embedded relief are present. Do not retain final solved endcaps.
    raw_endcap = (
        isinstance(spec, EndCapPartSpec)
        and not spec.resolved_assembly_relief_cuts
        and spec.assembly_relief is None
    )
    eligible = (
        (isinstance(spec, BoxBodyPartSpec) or raw_endcap)
        and isinstance(snapshot, Mapping)
        and snapshot.get("model") == "受電箱"
        and snapshot.get("active_mode") == "set_bay"
        and str(spec.model_name) == "受電箱"
        and isinstance(owner, Phase6DerivedCacheOwner)
    )
    history = (
        owner._receiving_exact_material_history if eligible else None
    )
    source_stamp = None
    if history is not None:
        # Same verified baseline source-generation seam used by the complete
        # manufacturing cache. Missing/unreadable witness forbids reuse.
        from phase6_manufacturing_adapter import _receiving_baseline_source_stamp
        from phase6_box_body_structure import (
            BoxBodyStructureType, normalize_box_body_structure_state,
        )
        structure_state = (
            spec.structure_state if isinstance(spec, BoxBodyPartSpec)
            else spec.box_body_structure_state
        )
        is_dedicated_three_piece = (
            normalize_box_body_structure_state(structure_state).get("active_type")
            == BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
        )
        source_stamp = _receiving_baseline_source_stamp(
            str(spec.model_name),
            context=ctx,
            include_physical_panels=is_dedicated_three_piece,
        )
        # Unlike the existing BoxBody fallback, a Receiving EndCap must
        # have a real witnessed 封頭尾 DXF. A missing optional source never
        # certifies cross-transaction reuse of EndCap material.
        if raw_endcap and source_stamp is not None and not any(
            len(row) >= 2 and row[0] == "封頭尾.dxf" and row[1] is not None
            for row in source_stamp
        ):
            source_stamp = None
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
    if isinstance(spec, BoxBodyPartSpec):
        from phase6_box_body_structure import BoxBodyStructureType, normalize_box_body_structure_state
        structure = normalize_box_body_structure_state(spec.structure_state)
        if structure.get("active_type") != BoxBodyStructureType.INTEGRAL.value:
            render_data = manufacturing_api.build_box_body_structure_render_data(spec, ctx)
        else:
            render_data = manufacturing_api.build_part_render_data(spec, ctx)
    else:
        render_data = manufacturing_api.build_part_render_data(spec, ctx)
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
    """Fail closed when a baseline-backed manufacturing source is not freshly verified."""
    model = self._baseline_source_model() if hasattr(self, "_baseline_source_model") else ""
    if not model:
        return True
    for filename in ("箱身.dxf", "封頭尾.dxf", "門.dxf"):
        path = ae.baseline_part_path(model, filename)
        if not path:
            continue
        _doc, status = ae.load_baseline_dxf_source_with_status(
            path, allow_unverified_source=False
        )
        if status != ae.BASELINE_SOURCE_VERIFIED:
            raise RuntimeError(
                f"基準來源尚未驗證：{model}/{filename}；正式製造輸出已停止。"
            )
    return True

def _export_authoritative_part(self, spec, output_path, context=None):
    """Save the exact cached FinalScene used by 2D/3D without rebuilding it."""
    self._flush_phase6_authoritative_state()
    owner = getattr(self, "workspace_controller", None)
    if owner is not None and owner.workspace_snapshot().get("receiving_quantity_box"):
        from ae_engine.receiving_quantity_box import require_valid_quantity_features
        require_valid_quantity_features(self._make_original_fold_designer_snapshot())
    self._require_verified_baseline_sources_for_manufacturing()
    ctx = context or self._manufacturing_context(draw_stock=False)
    render_data = self._authoritative_render_data(spec, ctx)
    if getattr(render_data, "pieces", None):
        output = Path(output_path)
        return manufacturing_api.generate_box_body_structure_parts(spec, output.parent, ctx)
    return manufacturing_api.save_part_render_data_dxf(
        render_data, output_path, overwrite=bool(getattr(ctx, "overwrite", False))
    )

def _box_body_divider_from_payload(key, payload):
    """UI input normalization only; Engine selects the physical Divider."""
    divider_input = collect_divider_input(
        key, payload, default_depth=ae.D, default_thickness=ae.T,
    )
    return manufacturing_api.resolve_fold_designer_divider_part(key, divider_input)


def _inner_door_frame_from_payload(key, payload):
    """The Engine owns Family/legacy frame topology and stable identity."""
    return manufacturing_api.resolve_fold_designer_frame_part(
        key, payload, default_thickness=ae.T,
    )


def _query_receiving_resolved_base_render_data(self, key, payload):
    if key == "base_plate" and (payload or {}).get("_use_committed_relief") is not False:
        owner = getattr(self, "fold_designer_app", None)
        current = getattr(owner, "_phase6_input_snapshot", None)
        if (isinstance(current, Mapping)
                and current.get("model") in ("受電箱", "RECEIVING")
                and current.get("nfb_config_submitted") is True
                and isinstance(current.get("nfb_config"), Mapping)
                and current["nfb_config"].get("layer_count") == 1):
            from ae_engine.receiving_base_plate_config import receiving_base_plate_values
            try:
                known_base = receiving_base_plate_values(current)
            except (ValueError, TypeError, KeyError):
                known_base = None
            if known_base is not None:
                resolved = getattr(owner, "_phase6_last_resolved_manufacturing_geometry", None)
                found = next(
                    (part for part in tuple(getattr(resolved, "parts", ()) or ())
                     if str(part.part_key) == key), None,
                )
                if found is None:
                    resolver = getattr(owner, "_phase6_resolve_manufacturing_geometry", None)
                    if not callable(resolver):
                        raise ValueError("RECEIVING_ONE_TIER_2D_SOURCE_UNAVAILABLE")
                    resolved = resolver()
                    found = next(
                        (part for part in tuple(getattr(resolved, "parts", ()) or ())
                         if str(part.part_key) == key), None,
                    )
                if found is None or getattr(found.render_data, "unfolded_topology", None) is None:
                    raise ValueError("RECEIVING_ONE_TIER_2D_PHYSICAL_PART_MISSING")
                return found.render_data
    if key.startswith("base_plate:nfb_layer:"):
        import re
        if not re.fullmatch(r"base_plate:nfb_layer:[01]", key):
            raise ValueError("RECEIVING_NFB_TIER_2D_PART_ID_INVALID")
        owner = getattr(self, "fold_designer_app", None)
        current = getattr(owner, "_phase6_input_snapshot", None)
        if (not isinstance(current, Mapping)
                or current.get("nfb_config_submitted") is not True):
            raise ValueError("RECEIVING_NFB_TIER_2D_NOT_SUBMITTED")
        resolved = getattr(owner, "_phase6_last_resolved_manufacturing_geometry", None)
        found = next(
            (part for part in tuple(getattr(resolved, "parts", ()) or ())
             if str(part.part_key) == key), None,
        )
        if found is None:
            resolver = getattr(owner, "_phase6_resolve_manufacturing_geometry", None)
            if not callable(resolver):
                raise ValueError("RECEIVING_NFB_TIER_2D_SOURCE_UNAVAILABLE")
            resolved = resolver()
            found = next(
                (part for part in tuple(getattr(resolved, "parts", ()) or ())
                 if str(part.part_key) == key), None,
            )
        if found is None or getattr(found.render_data, "unfolded_topology", None) is None:
            raise ValueError("RECEIVING_NFB_TIER_2D_PHYSICAL_PART_MISSING")
        return found.render_data
    return None


def _query_fold_designer_render_data(self, part_key, payload):
    from ae_engine.physical_sheet_features import with_physical_sheet_features

    def sheet(render):
        return with_physical_sheet_features(str(part_key), render, (payload or {}).get('features', ()))
    if str(part_key or "").startswith("indicator"):
        payload = collect_indicator_box_input(payload)
    if str(part_key or "").startswith("box_body:part:"):
        payload = collect_multipart_input(payload)
    if str(part_key or "").startswith("door:"):
        payload = collect_door_input(payload)
    """Return the same authoritative final geometry used by 2D consumers."""
    key = str(part_key or "")
    receiving_base = _query_receiving_resolved_base_render_data(self, key, payload)
    if receiving_base is not None:
        return receiving_base
    if key.startswith("nfb_pad:"):
        # The operator's current committed V5 source, never a stale
        # navigation key or a profile-only fabricated sheet.
        owner = getattr(self, "fold_designer_app", None)
        current = getattr(owner, "_phase6_input_snapshot", None)
        if not isinstance(current, Mapping):
            raise ValueError("PAD_OPERATOR_2D_SNAPSHOT_UNAVAILABLE")
        from ae_engine.receiving_nfb_pad_operator_parts import (
            committed_nfb_pad_draft_parts,
        )
        matches = tuple(
            part for part in committed_nfb_pad_draft_parts(current)
            if part.part_id == key
        )
        if len(matches) != 1:
            raise ValueError("PAD_OPERATOR_2D_STALE_OR_UNAUTHORIZED_PART")
        part = matches[0]
        if (part.manufacturing_ready
                or part.render_data.metadata.get("manufacturing_ready")
                or part.render_data.metadata.get("nfb_deferred_manufacturing_role")
                    != "PAD"):
            raise ValueError("PAD_OPERATOR_2D_MFG_GATE_INVALID")
        return sheet(part.render_data)
    if key.startswith("base_plate:fixing_plate:"):
        # Native independent PartRenderData, not the BasePlatePartSpec blank
        # and not a drawing-only menu simulation.
        from ae_engine.receiving_base_fixing_plate import (
            receiving_base_fixing_plate_previews,
        )
        from ae_engine.receiving_base_fixing_plate_geometry import (
            build_fixing_plate_source_render_data,
        )
        # The part-specific scene payload may be intentionally minimal:
        # a child fixing-plate PartSpec has no separate NFB/Bay authority.
        # Derive the physical owner from this *current* application's
        # receiving snapshot, not a stale root-base payload or the part ID
        # being queried. This exact same source drives 2D material and
        # 3D formed weld contacts; it cannot grant manufacturing release.
        source = dict(payload or {})
        live = _read_live_receiving_snapshot(self)
        selection = source.get("_receiving_runtime_selection")
        if isinstance(selection, Mapping):
            # Bay-specific material is resolved through an isolated
            # ManufacturingRequest. Never overwrite Bay3's W/H/D and Door
            # from an unrelated live Bay1 while drawing a fixing plate.
            from ae_engine.receiving_layout import (
                project_receiving_bay_legacy_aliases,
            )
            si, bi = selection.get("set_index"), selection.get("bay_index")
            if type(si) is not int or type(bi) is not int:
                raise ValueError("BASE_FIXING_PLATE_BAY_SELECTOR_INVALID")
            authoritative = project_receiving_bay_legacy_aliases(
                source, set_index=si, bay_index=bi,
            )
            for field in (
                "w", "h", "d", "_receiving_runtime_selection",
                "multi_door_enabled", "door_layout_columns",
                "inner_doors", "nfb_config", "nfb_config_submitted",
            ):
                if source.get(field) != authoritative.get(field):
                    raise ValueError(
                        f"BASE_FIXING_PLATE_BAY_SOURCE_DRIFT:{field}:"
                        f" selected={selection!r}"
                    )
            # Provenanced source includes the selected Bay's committed NFB.
            # A missing or malformed source is not rescued from another Bay.
        elif isinstance(live, Mapping):
            # The direct single-part editor can pass a minimal PartSpec.
            # Without a verified Bay selector only the LIVE snapshot may
            # authorize physical fixing-plate geometry.
            for name in ("nfb_config", "nfb_config_submitted"):
                source.pop(name, None)
            for name in (
                "model", "w", "h", "d", "t", "receiving_base_plate",
                "receiving_layout", "_receiving_runtime_selection",
                "nfb_config", "nfb_config_submitted", "inner_doors",
                "receiving_inner_door_layer_heights_mm",
            ):
                if name in live:
                    source[name] = live[name]
        physical = receiving_base_fixing_plate_previews(
            source, available_parts=("base_plate",),
        )
        if key not in {part.part_id for part in physical}:
            raise ValueError(
                "BASE_FIXING_PLATE_NOT_AUTHORIZED_FOR_THIS_CABINET:"
                f" requested={key}; current="
                f"{tuple(part.part_id for part in physical)}"
            )
        return sheet(build_fixing_plate_source_render_data(key, snapshot=source))
    if key.startswith("box_body:divider:"):
        divider = _box_body_divider_from_payload(key, payload)
        return sheet(manufacturing_api.build_box_body_divider_render_data(divider))

    if key.startswith("inner_door:") and key.endswith(":panel"):
        panel = manufacturing_api.resolve_fold_designer_panel_part(key, payload)
        features = tuple(dict(payload or {}).get("features") or ())
        # The canonical inner-door panel factory consumes only the immutable
        # physical panel and finished-face features. It reads no DXF/source
        # file. Do not apply this cross-transaction reuse to frame/divider
        # factories: those read dedicated physical baseline source data.
        snapshot = _read_live_receiving_snapshot(self)
        owner = getattr(self, "_derived_cache_owner", None)
        eligible = (
            isinstance(snapshot, Mapping)
            and snapshot.get("model") in ("受電箱", "RECEIVING")
            and snapshot.get("active_mode") == "set_bay"
            and isinstance(owner, Phase6DerivedCacheOwner)
        )
        if eligible:
            from phase6_manufacturing_contracts import manufacturing_fingerprint
            try:
                # No arbitrary repr fallback: unknown feature/part input must
                # be manufactured normally instead of guessed equivalent.
                fingerprint = manufacturing_fingerprint(
                    {"panel": panel, "features": features})
            except (TypeError, ValueError, OverflowError):
                fingerprint = None
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

    if key.startswith("inner_door:") and key.endswith("_frame"):
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
        state = normalize_door_indicator_state(states.get(cell_key))
        layers = max(1, min(6, int(state.get("layers", 1))))
        groups = tuple(int(v) for v in list(state.get("groups", [2] * 6))[:layers])
        mode = state.get("mode", "indicator" if state.get("enabled") else "none")
        indicator_hole = (
            manufacturing_api.indicator_box_opening_size(groups, thickness=t)
            if mode == "indicator_box" else None
        )
        direct = groups if mode == "indicator" else ()
        ind_offset = (float(state.get("offset_x", 0.0)), float(state.get("offset_y", 0.0)))
        use_box_dist = bool(state.get("is_box_dist", False))
    else:
        groups = tuple(int(v) for v in (data.get("indicator_layer_groups") or ()))
        direct = tuple(int(v) for v in (data.get("door_indicator_groups") or ()))
        indicator_hole = (
            manufacturing_api.indicator_box_opening_size(groups, thickness=t)
            if bool(data.get("door_indicator_box_enabled")) and groups else None
        )
        ind_offset = tuple(data.get("door_indicator_offset") or (0.0, 0.0))
        use_box_dist = bool(data.get("use_box_distance", False))
    return self._door_part_spec_from_values(
        {
            "w": w, "h": h, "t": t, "fw": fw,
            "door_gap_w": float(data.get("door_gap_w", ae.door_gap_w_def)),
            "door_gap_h": float(data.get("door_gap_h", ae.door_gap_h_def)),
            "door_fold_l": float(data.get("door_fold_l", ae.door_fold_left_def)),
            "door_fold_r": float(data.get("door_fold_r", ae.door_fold_right_def)),
            "door_fold_t": float(data.get("door_fold_t", ae.door_fold_top_def)),
            "door_fold_b": float(data.get("door_fold_b", ae.door_fold_bottom_def)),
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
    from phase6_custom_parts import is_custom_part
    if is_custom_part(key):
        from phase6_custom_fold_profiles import custom_part_spec
        return custom_part_spec(data, key, features=features, profiles=data.get("fold_profiles")), ManufacturingContext(draw_stock=False)
    policy = payload_policy(policy_part)
    context = ManufacturingContext(draw_stock=False)

    if key == "box_body":
        spec = self._box_body_part_spec_from_values(
            {
                "w": w, "h": h, "d": d, "t": t, "fw": fw,
                "zl1": float(data.get("zl1", ae.zl1_def)),
                "zl2": float(data.get("zl2", ae.zl2_def)),
                "zr1": float(data.get("zr1", ae.zr1_def)),
                "zr2": float(data.get("zr2", ae.zr2_def)),
                "z_comp": float(data.get("z_comp", getattr(ae, "z_comp_def", 0.0))),
            },
            model_name=(None if unknown else model),
            features=features,
            face_features=face_features,
            head_corner_policy=payload_policy("head"),
            tail_corner_policy=payload_policy("tail"),
            fold_profile=data.get("fold_profile"),
            structure_state=data.get("box_body_structure"),
            snapshot=data,
            head_ybottom1=float(data.get("head_ybottom1", data.get("ybottom1", ae.ybottom1_def))),
            tail_ybottom1=float(data.get("tail_ybottom1", data.get("ybottom1", ae.ybottom1_def))),
        )
    elif key in {"head", "tail"}:
        endcap_values = {
            "w": w, "h": h, "d": d, "t": t, "fw": fw,
            "yl1": float(data.get("yl1", ae.yl1_def)),
            "yr1": float(data.get("yr1", ae.yr1_def)),
            "ytop1": float(data.get("ytop1", ae.ytop1_def)),
            "ybottom1": float(data.get("ybottom1", ae.ybottom1_def)),
            "zl1": float(data.get("zl1", ae.zl1_def)),
            "zr1": float(data.get("zr1", ae.zr1_def)),
        }
        resolved_cuts = data.get("resolved_assembly_relief_cuts")
        if resolved_cuts is None and bool(data.get("_use_committed_relief")):
            resolved_cuts = self._resolved_committed_assembly_relief_cuts(
                key, endcap_values, data.get("fold_profiles") or {}
            )
        formed_fw_left, formed_fw_right = formed_box_body_fw_widths(
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
        values = {
            "w": w, "h": h, "t": t, "fw": fw,
            "base_plate_shrink_top": float(data.get("base_plate_shrink_top", 0)),
            "base_plate_shrink_bottom": float(data.get("base_plate_shrink_bottom", 0)),
            "base_plate_shrink_left": float(data.get("base_plate_shrink_left", 0)),
            "base_plate_shrink_right": float(data.get("base_plate_shrink_right", 0)),
            "base_plate_bend": float(data.get("base_plate_bend", 20)),
            "receiving_bend_pattern": data.get("receiving_bend_pattern"),
            "physical_id": key,
            "model": model,
        }
        if model in {"受電箱", "RECEIVING"}:
            if key != "base_plate":
                raise ValueError("RECEIVING_BASE_PLATE_LEGACY_CELL_UNSUPPORTED")
            from ae_engine.receiving_base_plate_config import receiving_base_plate_values
            physical = receiving_base_plate_values(data)
            if physical is not None:
                # Physical Receiving base height/folds are NOT the cabinet H,
                # a door cell H, or the ordinary family base shrink defaults.
                values.update(physical)
                # This already selected physical contour owns its corner cuts;
                # the generic family corner policy must not replace it.
                policy = None
        spec = self._base_plate_part_spec_from_values(
            values, features=features, corner_policy=policy,
        )
    elif key == "indicator_box":
        groups = tuple(int(v) for v in (data.get("indicator_layer_groups") or (1,)))
        spec = self._indicator_box_part_spec_from_values({"t": t}, groups, features=features)
    elif key == "indicator_door":
        groups = tuple(int(v) for v in (data.get("indicator_layer_groups") or (1,)))
        spec, context = self._indicator_door_part_spec_from_values(
            {
                "t": t,
                "fw": fw,
                "door_gap_w": float(data.get("door_gap_w", ae.door_gap_w_def)),
                "door_gap_h": float(data.get("door_gap_h", ae.door_gap_h_def)),
                "indicator_door_fold": float(
                    data.get(
                        "indicator_door_fold",
                        getattr(ae, "indicator_small_door_fold_def", 19.0),
                    )
                ),
            },
            groups,
            features=features,
        )
    else:
        raise ValueError(f"未知 3D 板件: {key}")
    return spec, context
