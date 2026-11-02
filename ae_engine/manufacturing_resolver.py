# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""Engine-owned canonical manufacturing orchestration service.

The service consumes one immutable ManufacturingResolveRequest and returns one
immutable ManufacturingResolveResult.  UI/application adaptation, callbacks,
publication, cache lookup, and compatibility mirrors live outside this module.
"""
from __future__ import annotations

from .assembly_mesh_reuse import mesh_build_scope
from .cabinet_types.policy import (
    canonical_family_name, require_implemented_manufacturing_family,
)

from copy import deepcopy
from dataclasses import replace

from .contracts import ResolvedManufacturingGeometry
from .manufacturing_api import (
    replay_resolved_endcap_render, resolve_live_cabinet_family,
    endcap_relief_transaction_committable,
    solve_endcap_assembly_relief, endcap_relief_solution_diagnostic,
    resolve_manufacturing_joint_graph,
    resolve_manufacturing_relief_evidence,
    resolve_receiving_nfb_assembly_parts,
    materialize_resolved_manufacturing_parts,
)
from .joint_marking_policy import resolve_joint_marking_foundation_status
from .receiving_joint_marking import (
    joint_marking_export_summary as _joint_marking_export_summary,
    resolve_joint_marking_production_status,
    resolve_receiving_joint_markings,
)
from .receiving_pairing_marking import (
    resolve_receiving_pairing_marking,
)
from .assembly_intent import normalize_assembly_intent_id
from .assembly_scene_part import AssemblyScenePart
# Preserve Phase6's operator text-number coercion for the legacy request path.
def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)

from .manufacturing_contracts import (
    ManufacturingCacheReceipt,
    ManufacturingDiagnosticsResult,
    ManufacturingEffects,
    ManufacturingMutationResult,
    ManufacturingResolveRequest,
    ManufacturingResolveResult,
    thaw_manufacturing_value,
)
from .manufacturing_api import (
    resolve_scene_assembly_placement,
    build_joint_world_geometry,
    resolve_material_mesh_profiles,
    resolve_manufacturing_explicit_joint_reliefs,
    resolve_family_divider_reliefs,
)


def _request_part(request, part_key):
    key = str(part_key or "")
    for item in tuple(request.parts or ()):
        if str(item.part_key) == key:
            return item
    raise KeyError(key)


def _assembly_intent_value(value):
    return normalize_assembly_intent_id(getattr(value, "value", value))


def _cabinet_family(request: ManufacturingResolveRequest) -> str:
    """Use the same public Engine Family resolution as the live Phase6 GUI."""
    return resolve_live_cabinet_family({"model": request.cabinet_model})


def _replay_endcap_render(part_input, solution):
    """Compatibility seam; Engine alone replays verified physical relief."""
    return replay_resolved_endcap_render(part_input, solution)


@mesh_build_scope()
def resolve(request):
    """Resolve one canonical manufacturing result from immutable domain input."""
    if not isinstance(request, ManufacturingResolveRequest):
        raise TypeError("request must be ManufacturingResolveRequest")

    fallback_enabled = bool(request.allow_3d_fallback)
    available = {str(key) for key in tuple(request.canonical_part_keys or ())}
    snapshot = thaw_manufacturing_value(request.input_snapshot)
    settings = thaw_manufacturing_value(request.settings)
    if not isinstance(snapshot, dict) or not isinstance(settings, dict):
        raise TypeError("manufacturing request snapshot/settings must thaw to mappings")
    # The caller's live Family selector takes precedence over a stale snapshot.
    # Missing explicit selectors retain the legacy snapshot/ANY behavior.
    requested_family = (
        str(request.cabinet_model or "").strip()
        or snapshot.get("model")
        or snapshot.get("cabinet_type")
    )
    require_implemented_manufacturing_family(requested_family)
    if canonical_family_name(snapshot) == "受電箱":
        from .receiving_nfb_manufacturing_transport import (
            restore_receiving_nfb_dto_selectors,
        )
        snapshot = restore_receiving_nfb_dto_selectors(snapshot)

    resolved_joint_graph = resolve_manufacturing_joint_graph(
        snapshot, available,
    )
    # The downstream explicit-joint relief path consumes the Engine-resolved
    # eligible Joint identities; never re-migrate or re-filter them in Phase6.
    joints = resolved_joint_graph.joints

    parts = []
    for part_input in tuple(request.parts or ()):
        key = str(part_input.part_key)
        if key not in available:
            continue
        render_data = part_input.render_data
        if render_data is None:
            raise ValueError(f"manufacturing render data unavailable: {key}")
        if getattr(render_data, "pieces", None):
            x_profile, y_profile = (), ()
        else:
            if (
                getattr(render_data, "scene", None) is None
                or getattr(render_data, "material", None) is None
            ):
                raise TypeError(
                    "manufacturing render input must contain scene + material "
                    "or physical pieces"
                )
            x_profile, y_profile = resolve_material_mesh_profiles(
                part_input,
                render_data.material,
            )
        if key.startswith("custom:"):
            placement, offset = "standalone", (0.0,0.0,0.0)
        else:
            placement, offset = resolve_scene_assembly_placement(snapshot, key)
        parts.append(
            AssemblyScenePart(
                part_key=key,
                render_data=render_data,
                x_profile=tuple(dict(seg) for seg in x_profile),
                y_profile=tuple(dict(seg) for seg in y_profile),
                placement=placement,
                offset=offset,
            )
        )
    # Physical NFB tier construction and committed CSV FinalScene projection
    # are an atomic Engine-owned manufacturing sequence, not Phase6 formulas.
    parts = list(resolve_receiving_nfb_assembly_parts(snapshot, parts))

    if not parts:
        raise ValueError("no parts available for assembly 3D display")

    pre_solve_probe_parts = tuple(
        part for part in parts if part.part_key in {"head", "tail"}
    )

    solutions = {}
    errors = {}
    publish_live_state = False
    required = [key for key in ("head", "tail") if key in available]
    dims = thaw_manufacturing_value(request.operator_finished_dimensions)
    thickness = _num(settings.get("t", snapshot.get("t", 2.0)), 2.0)
    clearance = float(request.relief_clearance or 0.0)

    if required:
        body_part = next(
            (part for part in parts if part.part_key == "box_body"),
            None,
        )
        if body_part is not None:
            by_key = {part.part_key: part for part in parts}
            for key in required:
                part = by_key[key]
                try:
                    solution = solve_endcap_assembly_relief(
                        body_part, part,
                        finished_dimensions=dims,
                        sheet_thickness=thickness,
                        clearance=clearance,
                        assembly_intent=_assembly_intent_value(
                            request.assembly_intent
                        ),
                        assembly_graph=resolved_joint_graph,
                        cabinet_family=_cabinet_family(request),
                        allow_3d_fallback=fallback_enabled,
                    )
                    solutions[key] = solution
                    diagnostic = endcap_relief_solution_diagnostic(solution)
                    if diagnostic is not None:
                        errors[key] = diagnostic
                except Exception as exc:
                    errors[key] = str(exc)

            atomic_committable = endcap_relief_transaction_committable(
                required, solutions,
            )

            if atomic_committable:
                publish_live_state = True
                solved_parts = []
                for part in parts:
                    if part.part_key not in required:
                        solved_parts.append(part)
                        continue
                    solution = solutions[part.part_key]
                    part_input = _request_part(
                        request,
                        part.part_key,
                    )
                    canonical_render = _replay_endcap_render(
                        part_input,
                        solution,
                    )
                    solved_parts.append(
                        AssemblyScenePart(
                            part_key=part.part_key,
                            render_data=canonical_render,
                            x_profile=part.x_profile,
                            y_profile=part.y_profile,
                            placement=part.placement,
                            offset=part.offset,
                        )
                    )
                parts = solved_parts
            else:
                canonical_parts = []
                for part in parts:
                    if part.part_key not in required:
                        canonical_parts.append(part)
                        continue
                    part_input = _request_part(
                        request,
                        part.part_key,
                    )
                    canonical_render = (
                        part_input.committed_render_data
                        or part_input.render_data
                    )
                    if canonical_render is None:
                        raise ValueError(
                            "committed manufacturing render unavailable: "
                            f"{part.part_key}"
                        )
                    canonical_parts.append(
                        AssemblyScenePart(
                            part_key=part.part_key,
                            render_data=canonical_render,
                            x_profile=part.x_profile,
                            y_profile=part.y_profile,
                            placement=part.placement,
                            offset=part.offset,
                        )
                    )
                parts = canonical_parts

    divider_joint_diagnostics = ()
    family_divider_joints = ()
    if any(
        str(part.part_key).startswith("box_body:divider:")
        for part in parts
    ):
        (
            parts,
            divider_joint_diagnostics,
            family_divider_joints,
        ) = resolve_family_divider_reliefs(
            tuple(parts),
            finished_dimensions=dims,
            sheet_thickness=thickness,
            clearance=clearance,
        )

    explicit_joint_diagnostics = ()
    explicit_joint_state = {"schema_version": 1, "items": {}}
    snapshot_patch = {}
    if any(
        str(
            getattr(
                getattr(joint, "source", None),
                "value",
                getattr(joint, "source", ""),
            )
        )
        == "USER_ADDED"
        for joint in joints
    ):
        (
            parts,
            explicit_joint_diagnostics,
            explicit_joint_state,
        ) = resolve_manufacturing_explicit_joint_reliefs(
            tuple(parts),
            joints,
            finished_dimensions=dims,
            sheet_thickness=thickness,
            clearance=clearance,
            committed_state=snapshot.get("joint_relief_state"),
        )
        snapshot_patch["joint_relief_state"] = deepcopy(
            explicit_joint_state
        )

    resolved_parts = materialize_resolved_manufacturing_parts(parts)
    traces, joint_registry_diagnostics = resolve_manufacturing_relief_evidence(
        resolved_parts, solutions, joints,
    )
    diagnostics = list(joint_registry_diagnostics)
    diagnostics.extend(tuple(divider_joint_diagnostics or ()))
    diagnostics.extend(tuple(explicit_joint_diagnostics or ()))

    resolved = ResolvedManufacturingGeometry(
        parts=resolved_parts,
        joints=tuple(joints) + tuple(family_divider_joints or ()),
        relief_rules=tuple(traces),
        diagnostics=tuple(diagnostics),
    )

    joint_marking_status = resolve_joint_marking_production_status()
    joint_marking_results = ()
    pairing_marking_result = None
    if _cabinet_family(request) == "受電箱":
        marking_world_geometry = build_joint_world_geometry(
            tuple(resolved.parts or ()), dims, thickness
        )
        marking_resolution = resolve_receiving_joint_markings(
            snapshot,
            resolved,
            dimensions=dims,
            sheet_thickness=thickness,
            cabinet_family="受電箱",
            world_geometry=marking_world_geometry,
        )
        resolved = marking_resolution.geometry
        joint_marking_status = marking_resolution.status
        joint_marking_results = tuple(marking_resolution.results)

        pairing_resolution = resolve_receiving_pairing_marking(
            snapshot,
            resolved,
            world_geometry=marking_world_geometry,
        )
        resolved = pairing_resolution.geometry
        pairing_marking_result = pairing_resolution.result

    return ManufacturingResolveResult(
        geometry=resolved,
        diagnostics=ManufacturingDiagnosticsResult(
            relief_errors=errors,
            relief_solutions=solutions,
            joint_diagnostics=tuple(diagnostics),
            rule_traces=tuple(traces),
            interference_probe_parts=tuple(pre_solve_probe_parts),
            joint_marking_foundation=resolve_joint_marking_foundation_status(),
            joint_marking_status=joint_marking_status,
            joint_marking_results=joint_marking_results,
            joint_marking_export_summary=_joint_marking_export_summary(
                joint_marking_results
            ),
            pairing_marking_result=pairing_marking_result,
        ),
        mutations=ManufacturingMutationResult(
            snapshot_patch=snapshot_patch
        ),
        effects=ManufacturingEffects(
            publish_live_state=publish_live_state,
            force_live_publish=publish_live_state,
            reason=(
                "atomic relief commit"
                if publish_live_state
                else ""
            ),
        ),
        cache=ManufacturingCacheReceipt(
            signature=str(
                request.cache_key_fingerprint
                or request.source_fingerprint
                or ""
            ),
            hit=False,
            stored=True,
        ),
    )


__all__ = ["resolve"]
