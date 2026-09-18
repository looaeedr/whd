"""Tk/app-aware Phase 2 manufacturing request adapter.

Task #356 builds immutable manufacturing inputs only.  It intentionally does
not own solver/orchestration logic and does not switch the canonical resolver.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from phase6_manufacturing_contracts import (
    ManufacturingPartInput,
    ManufacturingResolveRequest,
    ManufacturingResolveResult,
    manufacturing_request_fingerprint,
    thaw_manufacturing_value,
)
from phase6_part_navigation import is_box_body_physical_piece_key


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
    finished_dimensions_provider=None,
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
        part_inputs.append(
            ManufacturingPartInput(
                part_key=key,
                scene_values=_scene_values_for_part(app, key, scene_payload_builder),
                x_profile=x_profile,
                y_profile=y_profile,
                finished_dimensions=_finished_dimensions_for_part(app, key, finished_dimensions_provider),
                features=_workspace_value(workspace, "features_for", key, ()),
                face_features=_workspace_value(workspace, "face_features_for", key, {}),
                box_body_structure=_box_body_structure(workspace),
            )
        )

    request = ManufacturingResolveRequest(
        source_revision=str(getattr(app, "_phase6_sync_revision", "") or ""),
        source_fingerprint="",
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
    """Phase 1 cheap cache signature retained until #359 extracts cache service."""
    from phase6_manufacturing_geometry import _phase6_manufacturing_state_signature
    return _phase6_manufacturing_state_signature(app)


def resolve_manufacturing_for_app(
    app: Any,
    *,
    scene_payload_builder=None,
    finished_dimensions_provider=None,
    publish_live_state=None,
) -> Any:
    """Compatibility entry preserving Phase 1 signature-first cache short-circuit."""
    signature = _legacy_manufacturing_signature(app)
    cached = getattr(app, "_phase6_last_resolved_manufacturing_geometry", None)
    cached_signature = getattr(app, "_phase6_last_resolved_manufacturing_signature", None)
    if cached is not None and signature == cached_signature:
        return cached

    request = build_manufacturing_request(
        app,
        scene_payload_builder=scene_payload_builder,
        finished_dimensions_provider=finished_dimensions_provider,
    )
    from phase6_manufacturing_geometry import _phase6_resolve_manufacturing_result

    result = _phase6_resolve_manufacturing_result(app, request, signature=signature)
    geometry = apply_manufacturing_result(app, result)

    if result.effects.publish_live_state and callable(publish_live_state):
        publish_live_state(force=result.effects.force_live_publish)

    # Phase 1 stores the post-publication/post-snapshot-mutation signature.
    app._phase6_last_resolved_manufacturing_signature = _legacy_manufacturing_signature(app)
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
]
