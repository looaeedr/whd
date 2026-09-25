"""Tk/app-aware Phase 2 manufacturing request adapter.

Task #356 builds immutable manufacturing inputs only.  It intentionally does
not own solver/orchestration logic and does not switch the canonical resolver.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any
import re

from phase6_manufacturing_contracts import (
    ManufacturingPartInput,
    ManufacturingResolveRequest,
    ManufacturingResolveResult,
    manufacturing_request_fingerprint,
    thaw_manufacturing_value,
)
from phase6_part_navigation import is_box_body_physical_piece_key
from ae_engine.assembly_joint import migrate_legacy_snapshot_joints
from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.corner_type_ui import policy_from_corner_state
from ae_engine.display_dimensions import resolve_operator_finished_dimensions
from ae_engine.sheetmetal_geometry import FourCornerTypePolicy
from phase6_endcap_semantics import (
    ENDCAP_FW_PARTS,
    normalize_endcap_bottom_wrap_state,
    normalize_endcap_fw_state,
    resolve_endcap_bottom_wrap,
    resolve_endcap_fw,
    selection_from_raw,
)
from phase6_fold_profiles import (
    _num,
    clone_profile,
    engine_segment_length_to_ui,
    read_box_body_profile,
    read_endcap_xy_profiles,
)
from phase6_manufacturing_cache import (
    ManufacturingCacheKey,
    ManufacturingCacheService,
)


_CORNER_KEYS = ("bottom_left", "bottom_right", "top_left", "top_right")


def _is_door_part_key(value) -> bool:
    key = str(value or "")
    return key == "door" or re.fullmatch(r"door_c\d+_r\d+", key) is not None


def _is_base_plate_part_key(value) -> bool:
    key = str(value or "")
    return key == "base_plate" or re.fullmatch(r"base_plate_c\d+_r\d+", key) is not None


def _profile_value(profile, key, default=0):
    for seg in profile or ():
        if seg.get("phase6_key") == key:
            return float(seg.get("len") or 0)
    return float(default or 0)


def read_standard_part_profiles(part_key, profiles, original_snapshot):
    """Canonical reverse mapping for standard saved-part fold profiles."""
    x = list((profiles or {}).get("X", ()))
    y = list((profiles or {}).get("Y", ()))
    if _is_door_part_key(part_key):
        return {
            "door_fold_l": _profile_value(x, "door_fold_l", original_snapshot.get("door_fold_l", 20)),
            "door_fold_r": _profile_value(x, "door_fold_r", original_snapshot.get("door_fold_r", 20)),
            "door_fold_b": _profile_value(y, "door_fold_b", original_snapshot.get("door_fold_b", 20)),
            "door_fold_t": _profile_value(y, "door_fold_t", original_snapshot.get("door_fold_t", 20)),
        }
    if _is_base_plate_part_key(part_key):
        vals = [
            _profile_value(x, "base_bend_l", original_snapshot.get("base_plate_bend", 20)),
            _profile_value(x, "base_bend_r", original_snapshot.get("base_plate_bend", 20)),
            _profile_value(y, "base_bend_b", original_snapshot.get("base_plate_bend", 20)),
            _profile_value(y, "base_bend_t", original_snapshot.get("base_plate_bend", 20)),
        ]
        if len(set(vals)) != 1:
            raise ValueError("底板四邊折彎目前由 Phase6 共用一個 bend 值，四邊必須相同")
        return {"base_plate_bend": vals[0]}
    if part_key == "indicator_box":
        vals = [
            _profile_value(x, "ib_fold_l", original_snapshot.get("indicator_box_fold", 49)),
            _profile_value(x, "ib_fold_r", original_snapshot.get("indicator_box_fold", 49)),
            _profile_value(y, "ib_fold_b", original_snapshot.get("indicator_box_fold", 49)),
            _profile_value(y, "ib_fold_t", original_snapshot.get("indicator_box_fold", 49)),
        ]
        if len(set(vals)) != 1:
            raise ValueError("指示燈盒四邊折彎必須相同")
        return {"indicator_box_fold": vals[0]}
    if part_key == "indicator_door":
        vals = [
            _profile_value(x, "id_fold_l", original_snapshot.get("indicator_door_fold", 19)),
            _profile_value(x, "id_fold_r", original_snapshot.get("indicator_door_fold", 19)),
            _profile_value(y, "id_fold_b", original_snapshot.get("indicator_door_fold", 19)),
            _profile_value(y, "id_fold_t", original_snapshot.get("indicator_door_fold", 19)),
        ]
        if len(set(vals)) != 1:
            raise ValueError("指示燈小門四邊折彎必須相同")
        return {"indicator_door_fold": vals[0]}
    return {}


def _corner_policy_for_app(app: Any, part_key: str):
    raw_state = dict(
        (getattr(app, "_phase6_corner_state", {}) or {}).get(part_key, {}) or {}
    )
    if not all(key in raw_state for key in _CORNER_KEYS):
        return None
    selections = {
        key: selection_from_raw(raw_state[key])
        for key in _CORNER_KEYS
    }
    snapshot = dict(getattr(app, "_phase6_input_snapshot", {}) or {})
    snapshot.update(dict(getattr(app, "_settings_values", {}) or {}))
    snapshot["endcap_fw"] = deepcopy(
        getattr(app, "_phase6_endcap_fw_state", normalize_endcap_fw_state(snapshot))
    )
    fw = (
        resolve_endcap_fw(snapshot, part_key)
        if str(part_key) in ENDCAP_FW_PARTS
        else _num(snapshot.get("fw", 25), 25)
    )
    try:
        if (
            cabinet_family_policy.supports_bottom_wrap_controls(snapshot)
            and str(part_key) in ENDCAP_FW_PARTS
        ):
            thickness = _num(snapshot.get("t", 2.0), 2.0)
            return FourCornerTypePolicy(
                bottom_left=selections["bottom_left"],
                bottom_right=selections["bottom_right"],
                top_left=selections["top_left"],
                top_right=selections["top_right"],
                fw=float(fw),
                bottom_fw=cabinet_family_policy.effective_endcap_bottom_fw(
                    snapshot,
                    snapshot.get("box_body_structure"),
                    thickness=thickness,
                    default_fw=float(fw),
                ),
            )
    except Exception:
        pass
    return policy_from_corner_state(selections, fw=fw)


def operator_finished_dimensions_for_app(
    app: Any,
    part_key=None,
    *,
    triangles=None,
):
    """Tk/app adapter to the shared finished-dimension provider."""
    key = str(part_key or getattr(app, "active_part_key", "") or "")
    snapshot = getattr(app, "_phase6_input_snapshot", {}) or {}
    settings = getattr(app, "_settings_values", {}) or {}
    head_policy = tail_policy = None
    if key == "box_body":
        head_policy = _corner_policy_for_app(app, "head")
        tail_policy = _corner_policy_for_app(app, "tail")
    return resolve_operator_finished_dimensions(
        key,
        snapshot=snapshot,
        settings=settings,
        triangles=triangles,
        thickness=_num(settings.get("t", snapshot.get("t", 2.0)), 2.0),
        head_corner_policy=head_policy,
        tail_corner_policy=tail_policy,
    )


def build_scene_payload_for_app(app: Any, part_key: str) -> dict:
    """Build immutable-request scene values without importing the bridge."""
    key = str(part_key or "")
    if not key:
        return {}

    values = dict(getattr(app, "_phase6_input_snapshot", {}) or {})
    values.update(dict(getattr(app, "_settings_values", {}) or {}))
    values.update(dict(getattr(app, "_phase6_box_whd", {}) or {}))
    workspace = getattr(app, "designer_workspace", None)
    state = getattr(app, "state", None)

    try:
        if key == "box_body":
            profile = list(
                (getattr(state, "profiles_vault", {}) or {}).get("箱身", ()) or ()
            )
            values.update(read_box_body_profile(profile, values))
            values["fold_profile"] = clone_profile(profile)
        else:
            active = str(getattr(workspace, "active_part", "") or "")
            if key == active:
                profiles = getattr(state, "profiles", {}) or {}
            else:
                profiles_for = getattr(workspace, "profiles_for", None)
                profiles = (
                    profiles_for(key, {}) or {}
                    if callable(profiles_for)
                    else {}
                )
            if key in {"head", "tail"}:
                values.update(read_endcap_xy_profiles(profiles, values))
                values["box_body_profile"] = clone_profile(
                    (getattr(state, "profiles_vault", {}) or {}).get("箱身", ()) or ()
                )
                values["fold_profiles"] = {
                    "X": clone_profile(dict(profiles).get("X", ())),
                    "Y": clone_profile(dict(profiles).get("Y", ())),
                }
            else:
                values.update(read_standard_part_profiles(key, profiles, values))
    except Exception:
        pass

    model_var = getattr(app, "baseline_model_var", None)
    values["model"] = str(
        _safe_var_get(
            model_var,
            getattr(app, "_phase6_baseline_initial_model", "") or "",
        )
        or ""
    ).strip()
    values["endcap_fw"] = deepcopy(
        getattr(app, "_phase6_endcap_fw_state", normalize_endcap_fw_state(values))
    )
    values["endcap_bottom_wrap"] = deepcopy(
        getattr(
            app,
            "_phase6_endcap_bottom_wrap_state",
            normalize_endcap_bottom_wrap_state(values),
        )
    )
    if key in ENDCAP_FW_PARTS:
        values["fw"] = resolve_endcap_fw(
            values,
            key,
            state=values["endcap_fw"],
        )
    values["corner_state"] = deepcopy(
        getattr(app, "_phase6_corner_state", {}) or {}
    )
    values["_use_committed_relief"] = True

    features_for = getattr(workspace, "features_for", None)
    face_features_for = getattr(workspace, "face_features_for", None)
    structure_state = getattr(workspace, "box_body_structure_state", None)
    values["features"] = features_for(key) if callable(features_for) else ()
    values["face_features"] = (
        face_features_for(key) if callable(face_features_for) else {}
    )
    values["box_body_structure"] = (
        structure_state() if callable(structure_state) else {}
    )

    source_graph = migrate_legacy_snapshot_joints(
        dict(getattr(app, "_phase6_input_snapshot", {}) or {})
    )
    values["assembly_joint_schema_version"] = source_graph.get(
        "assembly_joint_schema_version"
    )
    values["assembly_joints"] = deepcopy(
        source_graph.get("assembly_joints", ())
    )

    if (
        key in ENDCAP_FW_PARTS
        and cabinet_family_policy.supports_bottom_wrap_controls(values)
    ):
        try:
            item = resolve_endcap_bottom_wrap(
                values,
                key,
                state=values["endcap_bottom_wrap"],
            )
            values["box_body_structure"] = (
                cabinet_family_policy.set_bottom_relief_reserves(
                    values,
                    values["box_body_structure"],
                    reserve_u=item["reserve_u"],
                    reserve_v=item["reserve_v"],
                )
            )
        except Exception:
            pass

    if key == "box_body":
        profiles_for = getattr(workspace, "profiles_for", None)
        for child_key, target in (
            ("head", "head_ybottom1"),
            ("tail", "tail_ybottom1"),
        ):
            profiles = (
                profiles_for(child_key, {}) or {}
                if callable(profiles_for)
                else {}
            )
            for row in list(dict(profiles).get("Y", ()) or ()):
                if str(row.get("phase6_key") or "") == "ybottom1":
                    values[target] = float(engine_segment_length_to_ui(row))
                    break

    source = getattr(app, "_phase6_input_snapshot", {}) or {}
    for name in (
        "indicator_layer_groups",
        "door_indicator_groups",
        "door_indicator_offset",
        "door_indicator_box_enabled",
    ):
        if name not in values and name in source:
            values[name] = deepcopy(source[name])
    return values


def _safe_var_get(value: Any, default: Any = None) -> Any:
    getter = getattr(value, "get", None)
    if callable(getter):
        try:
            return getter()
        except Exception:
            return default
    return default if value is None else value


def _mapping(value: Any) -> dict:
    try:
        return dict(value or {})
    except Exception:
        return {}


def _profile_inputs_for_part(app: Any, part_key: str) -> tuple[tuple, tuple]:
    """Read raw authoritative profile inputs without rendering or solving."""
    key = str(part_key or "")
    workspace = getattr(app, "designer_workspace", None)

    if key == "box_body":
        state = getattr(app, "state", None)
        vault = _mapping(getattr(state, "profiles_vault", {}) if state is not None else {})
        return tuple(vault.get("箱身", ()) or ()), ()

    state = getattr(app, "state", None)
    active = str(getattr(workspace, "active_part", "") or "")
    if key == active and state is not None:
        profiles = _mapping(getattr(state, "profiles", {}) or {})
    else:
        profiles_for = getattr(workspace, "profiles_for", None)
        profiles = _mapping(profiles_for(key, {}) if callable(profiles_for) else {})
    return tuple(profiles.get("X", ()) or ()), tuple(profiles.get("Y", ()) or ())


def _workspace_value(workspace: Any, method_name: str, part_key: str, default: Any) -> Any:
    method = getattr(workspace, method_name, None)
    if not callable(method):
        return default
    try:
        return method(part_key)
    except Exception:
        return default


def _box_body_structure(workspace: Any) -> Any:
    method = getattr(workspace, "box_body_structure_state", None)
    if not callable(method):
        return {}
    try:
        return method() or {}
    except Exception:
        return {}


def _scene_values_for_part(app: Any, part_key: str, builder=None) -> Any:
    builder = builder if callable(builder) else getattr(app, "_phase6_scene_query_payload_for_part", None)
    if not callable(builder):
        raise RuntimeError("manufacturing scene-input adapter is not connected")
    payload = builder(part_key)
    if payload is None:
        raise ValueError(f"manufacturing scene input unavailable: {part_key}")
    return payload


def _domain_inputs_for_part(
    app: Any,
    part_key: str,
    scene_values: Any,
    *,
    render_data_provider=None,
    part_spec_provider=None,
):
    """Materialize the raw domain input for one part before pure service entry.

    Committed Head/Tail render data is intentionally materialized in a second
    pass after every raw part. This preserves the accepted Phase 1 provider
    ordering: all raw parts first, then committed Head/Tail fallbacks.
    """
    key = str(part_key or "")
    render_data = None
    committed_render_data = None
    part_spec = manufacturing_context = None

    if callable(render_data_provider):
        base_payload = dict(scene_values or {})
        base_payload["_use_committed_relief"] = False
        render_data = render_data_provider(key, base_payload)
        if key not in {"head", "tail"}:
            committed_render_data = render_data

    if callable(part_spec_provider) and key in {"head", "tail"}:
        spec_payload = dict(scene_values or {})
        spec_payload["_use_committed_relief"] = False
        resolved = part_spec_provider(key, spec_payload)
        if isinstance(resolved, tuple) and len(resolved) == 2:
            part_spec, manufacturing_context = resolved
        elif resolved is not None:
            raise TypeError("part_spec_provider must return (spec, context)")

    return render_data, committed_render_data, part_spec, manufacturing_context


def _materialize_committed_endcap_inputs(
    parts: list[ManufacturingPartInput],
    *,
    render_data_provider=None,
) -> list[ManufacturingPartInput]:
    """Attach committed Head/Tail fallbacks after all raw providers have run."""
    if not callable(render_data_provider):
        return parts
    result: list[ManufacturingPartInput] = []
    for part in parts:
        if part.part_key not in {"head", "tail"}:
            result.append(part)
            continue
        committed_payload = thaw_manufacturing_value(part.scene_values)
        committed_payload["_use_committed_relief"] = True
        committed = render_data_provider(part.part_key, committed_payload)
        result.append(replace(part, committed_render_data=committed))
    return result


def _finished_dimensions_for_part(app: Any, part_key: str, provider=None) -> Any:
    provider = provider if callable(provider) else getattr(app, "_phase6_operator_finished_dimensions", None)
    if not callable(provider):
        return {}
    try:
        return provider(part_key) if str(part_key or "") else provider()
    except TypeError:
        # Preserve compatibility with older lightweight facade providers that
        # expose the no-argument form only.
        return provider()


def _canonical_part_keys(app: Any) -> tuple[str, ...]:
    workspace = getattr(app, "designer_workspace", None)
    values = tuple(getattr(workspace, "available_parts", ()) or ())
    return tuple(
        str(key)
        for key in values
        if str(key or "") and not is_box_body_physical_piece_key(key)
    )


def _assembly_graph_inputs(snapshot: dict) -> dict:
    return {
        "assembly_joint_schema_version": snapshot.get("assembly_joint_schema_version"),
        "assembly_joints": snapshot.get("assembly_joints", ()),
    }


def _assembly_intent(app: Any) -> str:
    value = getattr(app, "_phase6_assembly_type", "")
    return str(getattr(value, "value", value) or "")


def _relief_clearance(app: Any) -> float:
    raw = _safe_var_get(getattr(app, "assembly_relief_clearance_var", None), "0")
    try:
        return max(0.0, float(str(raw).strip() or "0"))
    except (TypeError, ValueError):
        return 0.0


def _cabinet_model(app: Any, snapshot: dict) -> str:
    live = _safe_var_get(getattr(app, "baseline_model_var", None), "")
    value = str(live or "").strip()
    if value:
        return value
    return str(snapshot.get("model") or snapshot.get("cabinet_type") or "").strip()


def build_manufacturing_request(
    app: Any,
    *,
    scene_payload_builder=None,
    render_data_provider=None,
    part_spec_provider=None,
    finished_dimensions_provider=None,
    cache_key_fingerprint="",
) -> ManufacturingResolveRequest:
    """Build one immutable manufacturing request from current app/workspace state.

    This function is intentionally an adapter boundary: it may read app/workspace
    state but performs no manufacturing solve, collision, relief, or cache
    decision.
    """
    snapshot = _mapping(getattr(app, "_phase6_input_snapshot", {}) or {})
    settings = _mapping(getattr(app, "_settings_values", {}) or {})
    box_dimensions = _mapping(getattr(app, "_phase6_box_whd", {}) or {})
    corner_state = _mapping(getattr(app, "_phase6_corner_state", {}) or {})
    endcap_fw = _mapping(getattr(app, "_phase6_endcap_fw_state", {}) or {})
    endcap_bottom_wrap = _mapping(getattr(app, "_phase6_endcap_bottom_wrap_state", {}) or {})
    workspace = getattr(app, "designer_workspace", None)

    part_inputs: list[ManufacturingPartInput] = []
    for key in _canonical_part_keys(app):
        x_profile, y_profile = _profile_inputs_for_part(app, key)
        scene_values = _scene_values_for_part(app, key, scene_payload_builder)
        render_data, committed_render_data, part_spec, manufacturing_context = (
            _domain_inputs_for_part(
                app,
                key,
                scene_values,
                render_data_provider=render_data_provider,
                part_spec_provider=part_spec_provider,
            )
        )
        part_inputs.append(
            ManufacturingPartInput(
                part_key=key,
                scene_values=scene_values,
                render_data=render_data,
                committed_render_data=committed_render_data,
                part_spec=part_spec,
                manufacturing_context=manufacturing_context,
                x_profile=x_profile,
                y_profile=y_profile,
                finished_dimensions=_finished_dimensions_for_part(app, key, finished_dimensions_provider),
                features=_workspace_value(workspace, "features_for", key, ()),
                face_features=_workspace_value(workspace, "face_features_for", key, {}),
                box_body_structure=_box_body_structure(workspace),
            )
        )

    part_inputs = _materialize_committed_endcap_inputs(
        part_inputs,
        render_data_provider=render_data_provider,
    )

    request = ManufacturingResolveRequest(
        source_revision=str(getattr(app, "_phase6_sync_revision", "") or ""),
        source_fingerprint="",
        cache_key_fingerprint=str(cache_key_fingerprint or ""),
        input_snapshot=snapshot,
        settings=settings,
        box_dimensions=box_dimensions,
        corner_state=corner_state,
        endcap_fw=endcap_fw,
        endcap_bottom_wrap=endcap_bottom_wrap,
        assembly_graph=_assembly_graph_inputs(snapshot),
        canonical_part_keys=_canonical_part_keys(app),
        parts=tuple(part_inputs),
        operator_finished_dimensions=_finished_dimensions_for_part(
            app, "", finished_dimensions_provider
        ),
        assembly_intent=_assembly_intent(app),
        allow_3d_fallback=bool(
            _safe_var_get(getattr(app, "assembly_ignore_fixed_corner_var", None), False)
        ),
        relief_clearance=_relief_clearance(app),
        cabinet_model=_cabinet_model(app, snapshot),
    )
    # Transport/source metadata must not affect semantic request identity.
    return replace(
        request,
        source_fingerprint=manufacturing_request_fingerprint(request),
    )


def _legacy_manufacturing_signature(app: Any) -> str:
    """Phase 1 cheap semantic signature retained as the T5 pre-scan key source."""
    from phase6_manufacturing_geometry import _phase6_manufacturing_state_signature
    return _phase6_manufacturing_state_signature(app)


def build_manufacturing_cache_key(app: Any) -> ManufacturingCacheKey:
    """Build the lightweight semantic cache key before full DTO construction."""
    return ManufacturingCacheKey(_legacy_manufacturing_signature(app))


def _cache_service_for_app(app: Any) -> ManufacturingCacheService:
    service = getattr(app, "_phase6_manufacturing_cache_service", None)
    if isinstance(service, ManufacturingCacheService):
        return service
    service = ManufacturingCacheService()
    setattr(app, "_phase6_manufacturing_cache_service", service)
    return service


def resolve_for_app(app: Any) -> Any:
    """Single compatibility entry from app/Tk world into manufacturing."""
    render_provider = getattr(app, "_scene_query_callback", None)
    part_spec_provider = getattr(app, "_part_spec_query_callback", None)
    publish_live_state = getattr(app, "_phase6_publish_live_state", None)
    return resolve_manufacturing_for_app(
        app,
        scene_payload_builder=lambda key: build_scene_payload_for_app(app, key),
        render_data_provider=render_provider,
        part_spec_provider=part_spec_provider,
        finished_dimensions_provider=lambda key=None: operator_finished_dimensions_for_app(
            app,
            key,
        ),
        publish_live_state=publish_live_state,
        require_render_provider=True,
    )


def resolve_manufacturing_for_app(
    app: Any,
    *,
    scene_payload_builder=None,
    render_data_provider=None,
    part_spec_provider=None,
    finished_dimensions_provider=None,
    publish_live_state=None,
    cache_service=None,
    require_render_provider=False,
) -> Any:
    """Resolve through explicit cache ownership with signature-first hit parity."""
    service = (
        cache_service
        if isinstance(cache_service, ManufacturingCacheService)
        else _cache_service_for_app(app)
    )
    key = build_manufacturing_cache_key(app)
    lookup = service.lookup(key)
    if lookup.result is not None:
        # Legacy mirrors remain readers only; they are never cache authority.
        app._phase6_last_resolved_manufacturing_geometry = lookup.result.geometry
        app._phase6_last_resolved_manufacturing_signature = key.fingerprint
        return lookup.result.geometry

    if require_render_provider and not callable(render_data_provider):
        # Preserve the accepted Phase 1 GUI fail-closed boundary after the
        # signature-first cache short-circuit, while keeping this lower-level
        # adapter seam injectable for focused service/cache tests.
        raise RuntimeError("3D final-scene provider is not connected")

    request = build_manufacturing_request(
        app,
        scene_payload_builder=scene_payload_builder,
        render_data_provider=render_data_provider,
        part_spec_provider=part_spec_provider,
        finished_dimensions_provider=finished_dimensions_provider,
        cache_key_fingerprint=key.fingerprint,
    )
    import phase6_manufacturing_service as manufacturing_service

    result = manufacturing_service.resolve(request)
    geometry = apply_manufacturing_result(app, result)

    if result.effects.publish_live_state and callable(publish_live_state):
        publish_live_state(force=result.effects.force_live_publish)

    # Publication or snapshot mutation may change the semantic signature.
    post_key = build_manufacturing_cache_key(app)
    stored_receipt = service.store(post_key, result)
    app._phase6_last_resolved_manufacturing_signature = stored_receipt.signature
    return geometry


def apply_manufacturing_result(app: Any, result: ManufacturingResolveResult) -> Any:
    """Apply explicit Phase 2 result state to the legacy app facade.

    T3 deliberately applies state only.  `ManufacturingEffects` remains an
    explicit intent and no live publication/callback is executed here.
    """
    if not isinstance(result, ManufacturingResolveResult):
        raise TypeError("result must be ManufacturingResolveResult")

    diagnostics = result.diagnostics
    app._phase6_last_interference_probe_parts = tuple(
        diagnostics.interference_probe_parts
    )
    app._phase6_last_relief_errors = dict(diagnostics.relief_errors.items())
    app._phase6_last_relief_solutions = dict(diagnostics.relief_solutions.items())
    app._phase6_last_resolved_manufacturing_geometry = result.geometry
    app._phase6_last_resolved_manufacturing_signature = result.cache.signature

    current_snapshot = _mapping(getattr(app, "_phase6_input_snapshot", {}) or {})
    patch = thaw_manufacturing_value(result.mutations.snapshot_patch)
    if not isinstance(patch, dict):
        raise TypeError("snapshot patch must thaw to dict")
    current_snapshot.update(patch)
    app._phase6_input_snapshot = current_snapshot
    return result.geometry


__all__ = [
    "build_manufacturing_request",
    "apply_manufacturing_result",
    "resolve_manufacturing_for_app",
    "resolve_for_app",
    "build_scene_payload_for_app",
    "operator_finished_dimensions_for_app",
    "read_standard_part_profiles",
    "build_manufacturing_cache_key",
]
