# -*- coding: utf-8 -*-
"""#2378 W-03 in-process Door prepare, gated on trusted inputs and key custody.

This function is a testable orchestration boundary, NOT the CLI handler.
W-06 owns installation key custody, journal and replay. W-04 owns export.
No source geometry can be committed by this module.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import math
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from integration_cli.prepare_binding import create_preparation_binding
from integration_cli.prepare_evidence import (
    PrepareEvidenceError, assert_snapshot_current, build_resource_evidence, resolve_authoritative_door_inputs
)
from integration_cli.prepare_frame import (
    resolve_door_finished_local_frame, resolve_indicator_box_size_only_frame,
    resolve_endcap_size_only_frame,
)
from integration_cli.request_canonical import require_matching_wire_request_digest

_REGISTRY_PATH = "基準檔/截角資料庫/certified_relief_rules.json"


def _validate_owning_resource_parsers(resource_root: Path, baseline_paths: list[str]) -> None:
    """A hash of arbitrary bytes is not proof of a valid WHD resource.

    Use the existing Certified Registry and DXF source owners. Their verified
    source reader must NOT use preview last-known-good fallback for prepare.
    This validation does not mutate runtime registry rules or manufacture DXF.
    """
    from ae_engine.certified_relief_registry import build_runtime_relief_rules_from_external
    from ae_engine.baseline_source import (
        BASELINE_SOURCE_VERIFIED, baseline_cutting_bounds, load_baseline_dxf_source_with_status,
    )
    from ezdxf import DXFError

    try:
        rules = build_runtime_relief_rules_from_external(resource_root / _REGISTRY_PATH)
        if not rules:
            raise ValueError("certified registry has no active runtime rules")
    except (ValueError, TypeError, OSError, KeyError, RuntimeError) as exc:
        raise PrepareEvidenceError(
            "WHD_RESOURCE_UNVERIFIED", "certified Registry content cannot be verified"
        ) from exc
    for rel in baseline_paths:
        try:
            doc, state = load_baseline_dxf_source_with_status(
                resource_root / rel, allow_unverified_source=False,
            )
            bounds = baseline_cutting_bounds(doc.modelspace())
            if state != BASELINE_SOURCE_VERIFIED or bounds is None:
                raise ValueError("DXF source is not verified CUTTING geometry")
            min_x, min_y, max_x, max_y = bounds
            if not min_x < max_x or not min_y < max_y:
                raise ValueError("DXF CUTTING geometry has no positive area envelope")
        except (ValueError, TypeError, OSError, RuntimeError, DXFError) as exc:
            raise PrepareEvidenceError(
                "WHD_RESOURCE_UNVERIFIED", "baseline DXF cannot be parsed and verified"
            ) from exc


def door_spec_from_trusted_prepared_part(part: Mapping[str, Any], policy):
    """Convert an already schema-checked Door part using WHD policy, not CADSplit formulas.

    This is the shared W-03/W-04 adapter. Only prepare/recheck may authorize
    the original part. The supplied policy must be resolved by WHD.
    """
    from ae_engine.contracts import DoorPartSpec
    from ae_engine.sheetmetal_part_adapters import DoorFrameEdges

    p = part
    dims = p["dimensions_mm"]
    flags = p["frame_edges"]
    return DoorPartSpec(
        width=float(dims["width"]), height=float(dims["height"]),
        thickness=float(dims["thickness"]),
        frame_width=float(p.get("frame_width_mm", policy.frame_width)),
        model_name=p["cabinet_family"],
        gap_w=p.get("gap_w_mm"), gap_h=p.get("gap_h_mm"),
        fold_left=p.get("fold_left_mm"), fold_right=p.get("fold_right_mm"),
        fold_top=p.get("fold_top_mm"), fold_bottom=p.get("fold_bottom_mm"),
        frame_edges=DoorFrameEdges(**flags),
    )


def indicator_small_door_spec_from_trusted_prepared_part(part: Mapping[str, Any], context):
    """Adapt only the WHD-owned shared small-door geometry, never CADSplit dimensions.

    The outside formed face must be asserted explicitly by the source; its
    dimensions and fold policy are recomputed by the existing WHD helper.
    An arbitrary Door override cannot turn this shared physical part into a
    second manufacturing recipe.
    """
    from ae_engine.manufacturing_api import (
        door_finished_face_size, indicator_small_door_finished_size,
        indicator_small_door_spec,
    )

    if part.get("kind") != "indicator_small_door" or part.get("dimension_semantics") != "part_formed_outer":
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "small-door physical dimensions must be part_formed_outer")
    prohibited = (
        "frame_edges", "frame_width_mm", "gap_w_mm", "gap_h_mm",
        "fold_left_mm", "fold_right_mm", "fold_top_mm", "fold_bottom_mm",
    )
    if any(key in part for key in prohibited):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "shared small door cannot override WHD factory policy")
    groups = part.get("indicator_groups")
    if (not isinstance(groups, list) or not groups
            or any(type(group) is not int or group <= 0 for group in groups)):
        raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "small-door layer groups required")
    dims = part.get("dimensions_mm")
    if not isinstance(dims, Mapping) or set(dims) != {"width", "height", "thickness"}:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "exact small-door formed dimensions required")
    if any(type(dims[key]) not in (int, float) or not math.isfinite(dims[key]) or dims[key] <= 0
           for key in ("width", "height", "thickness")):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "nonfinite or nonpositive small-door dimensions")
    try:
        spec = indicator_small_door_spec(groups, thickness=float(dims["thickness"]), context=context)
        expected = indicator_small_door_finished_size(
            groups, thickness=float(dims["thickness"]), context=context,
        )
        actual = door_finished_face_size(spec, context)
    except (TypeError, ValueError, OverflowError, ArithmeticError) as exc:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "WHD small-door geometry cannot be verified") from exc
    if any(
        not math.isfinite(actual[i])
        or not math.isclose(float(dims[key]), expected[i], rel_tol=0, abs_tol=1e-6)
        or not math.isclose(actual[i], expected[i], rel_tol=0, abs_tol=1e-6)
        for i, key in enumerate(("width", "height"))
    ):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "source small-door size differs from WHD linked finished-face owner")
    return spec



def indicator_box_spec_from_trusted_prepared_part(part: Mapping[str, Any], context):
    """Use the WHD shared indicator-box owner; never trust caller dimensions.

    A size-only Prepare does NOT attest external source Feature placement.
    Only WHD-owned featureless geometry (with an empty original DXF source)
    may reach private W-04; external Feature mapping remains unsupported.
    """
    from ae_engine.contracts import IndicatorBoxPartSpec
    from ae_engine.manufacturing_api import indicator_box_finished_face_size

    if (part.get("kind") != "indicator_box"
            or part.get("dimension_semantics") != "part_formed_outer"):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "shared box requires part_formed_outer semantics")
    if any(field in part for field in (
        "frame_edges", "frame_width_mm", "gap_w_mm", "gap_h_mm",
        "fold_left_mm", "fold_right_mm", "fold_top_mm", "fold_bottom_mm",
    )):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "shared box cannot override WHD manufacturing policy")
    groups = part.get("indicator_groups")
    if not isinstance(groups, list) or not groups or any(
        type(n) is not int or n <= 0 for n in groups
    ):
        raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "positive indicator groups required")
    dims = part.get("dimensions_mm")
    if not isinstance(dims, Mapping) or set(dims) != {"width", "height", "thickness"}:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "exact box formed dimensions required")
    if any(type(dims[k]) not in (int, float) or not math.isfinite(dims[k]) or dims[k] <= 0
           for k in ("width", "height", "thickness")):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "nonfinite or nonpositive box dimensions")
    try:
        expected = indicator_box_finished_face_size(
            groups, thickness=float(dims["thickness"]), context=context,
        )
    except (TypeError, ValueError, OverflowError, ArithmeticError) as exc:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "WHD box dimensions unavailable") from exc
    if any(
        not math.isfinite(value)
        or not math.isclose(float(dims[key]), value, rel_tol=0, abs_tol=1e-6)
        for key, value in zip(("width", "height"), expected)
    ):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "box outside dimensions disagree with WHD owner")
    return IndicatorBoxPartSpec(
        layer_groups=tuple(groups), thickness=float(dims["thickness"]),
        model_name=None,  # Indicator boxes are globally shared, not family-owned.
    )


def endcap_spec_from_trusted_prepared_part(part: Mapping[str, Any], policy):
    """Use WHD's existing Vault EndCap part contract without inventing folds.

    A size-only Prepare is not source-Feature/assembly-space attestation.
    Only WHD's intrinsic Vault standard geometry is eligible for private
    W-04 with an entirely empty original DXF and no external Features.
    Both head and tail retain distinct physical identities; no external
    assembly relief, corner-policy override or source-to-DXF placement.
    """
    from ae_engine.contracts import EndCapPartSpec

    kind = part.get("kind")
    if kind not in ("end_cap_head", "end_cap_tail"):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "unrecognized EndCap physical role")
    if (part.get("cabinet_family") != "金庫型"
            or part.get("dimension_semantics") != "cabinet_outer"):
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED",
            "only WHD Vault cabinet_outer EndCap dimensions are verified",
        )
    if any(key in part for key in (
        "frame_edges", "frame_width_mm", "gap_w_mm", "gap_h_mm",
        "fold_left_mm", "fold_right_mm", "fold_top_mm", "fold_bottom_mm",
        "indicator_groups",
    )):
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED", "EndCap cannot override unverified folds or topology",
        )
    dims = part.get("dimensions_mm")
    if not isinstance(dims, Mapping) or set(dims) != {"width", "depth", "thickness"}:
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED", "exact Vault EndCap width/depth/thickness required",
        )
    if any(type(dims[key]) not in (int, float)
           or not math.isfinite(dims[key]) or dims[key] <= 0
           for key in ("width", "depth", "thickness")):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "nonfinite EndCap input dimensions")
    return EndCapPartSpec(
        width=float(dims["width"]), depth=float(dims["depth"]),
        thickness=float(dims["thickness"]), frame_width=float(policy.frame_width),
        model_name="金庫型", is_tail=(kind == "end_cap_tail"),
    )


def prepare_trusted_door_batch(
    request: Mapping[str, Any], *,
    resource_root: Path, engine_commit: str, engine_sha256: str,
    build_id: str, worker_key: bytes,
) -> dict[str, Any]:
    """Return source-attested Door/small-door preparation, not manufacturing.

    No caller can enable this through the public source-only CLI: the trusted
    W-06 key lifecycle and W-05 resource manifest are not yet available.
    """
    from ae_engine.contracts import ManufacturingContext
    from ae_engine.manufacturing_api import (
        expected_baseline_path_for, resolve_policy,
    )

    schema_dir = Path(__file__).resolve().parent / "schemas"
    req_schema = Draft202012Validator(
        __import__("json").loads((schema_dir / "request_v1_1.schema.json").read_text(encoding="utf-8"))
    )
    req_schema.validate(request)
    if request["operation"] != "prepare":
        raise PrepareEvidenceError("WHD_OPERATION_MISMATCH", "only prepare supported")
    if len(request["items"]) > 20:
        raise PrepareEvidenceError("WHD_BATCH_TOO_LARGE", "WHD batch max exceeded")
    require_matching_wire_request_digest(request)
    if not isinstance(resource_root, Path) or not resource_root.is_dir() or resource_root.is_symlink():
        raise PrepareEvidenceError("WHD_RESOURCE_UNVERIFIED", "trusted resource root unavailable")
    ctx = ManufacturingContext(resource_root=resource_root)
    policy = resolve_policy(ctx)
    ctx = ManufacturingContext(resource_root=resource_root, policy=policy)
    recorded, baselines, identities = [], set(), set()

    for item in request["items"]:
        p = item["part"]
        kind = p["kind"]
        if kind == "door":
            if p["dimension_semantics"] != "cabinet_outer":
                raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "only verified cabinet_outer Door-local frame is supported")
            flags = p.get("frame_edges")
            if not isinstance(flags, dict) or set(flags) != {"left","right","top","bottom"} or not all(type(v) is bool for v in flags.values()):
                raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "source layout must explicitly certify all four Door frame edges")
            dims = p["dimensions_mm"]
            if not all(k in dims for k in ("width","height","thickness")):
                raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "complete verified Door input dimensions required")
        elif kind not in (
            "indicator_small_door", "indicator_box", "end_cap_head", "end_cap_tail",
        ):
            raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "unverified physical part kind has no supported local Frame")
        if item["item_id"] in identities:
            raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "duplicate item ID")
        identities.add(item["item_id"])
        if kind == "door":
            part_spec = door_spec_from_trusted_prepared_part(p, policy)
        elif kind == "indicator_small_door":
            part_spec = indicator_small_door_spec_from_trusted_prepared_part(p, ctx)
        elif kind == "indicator_box":
            part_spec = indicator_box_spec_from_trusted_prepared_part(p, ctx)
        else:
            part_spec = endcap_spec_from_trusted_prepared_part(p, policy)
        identity_bytes = ("WHD-PART-v1\0" + request["client_installation_id"]
                + "\0" + request["job_id"] + "\0" + item["item_id"]
                + "\0" + p["source_part_ref"] + "\0" + item["source_document_sha256"]).encode("utf-8")
        physical_id = "whd-" + hashlib.sha256(identity_bytes).hexdigest()[:24]
        if kind == "indicator_box":
            frame = resolve_indicator_box_size_only_frame(
                part_spec, ctx, physical_part_id=physical_id,
            )
            authoritative = {
                "part_kind": kind,
                "indicator_groups": list(p["indicator_groups"]),
                "input_dimensions_mm": {"thickness": float(part_spec.thickness)},
                "finished_face_dimensions_mm": frame["finished_face_dimensions_mm"],
                "coordinate_space": "size_only",
                "target_frame_certified": False,
            }
        elif kind in ("end_cap_head", "end_cap_tail"):
            frame = resolve_endcap_size_only_frame(
                part_spec, physical_part_id=physical_id,
            )
            authoritative = {
                "part_kind": kind,
                "cabinet_family": "金庫型",
                "input_dimensions_mm": {
                    "width": part_spec.width,
                    "depth": part_spec.depth,
                    "thickness": part_spec.thickness,
                    "frame_width": part_spec.frame_width,
                },
                "finished_face_dimensions_mm": frame["finished_face_dimensions_mm"],
                "coordinate_space": "size_only",
                "target_frame_certified": False,
            }
        else:
            authoritative = resolve_authoritative_door_inputs(part_spec, ctx)
            if kind == "indicator_small_door":
                authoritative = {**authoritative, "part_kind": kind,
                                 "indicator_groups": list(p["indicator_groups"])}
            frame = resolve_door_finished_local_frame(
                part_spec, ctx, physical_part_id=physical_id,
            )
        baseline = expected_baseline_path_for(part_spec, ctx)
        if baseline is None:
            raise PrepareEvidenceError("WHD_RESOURCE_UNVERIFIED", "WHD could not identify the physical part baseline")
        # The CURRENT AE shared-indicator resolver selects a *single*
        # global folder only when both 盒子.dxf and 小門.dxf are present.
        # Attest the same coupled resource set even for a one-kind Prepare:
        # otherwise an unseen paired file could change after sealing the
        # environment but before a later mixed Door/Box use of that folder.
        selected_baselines = [baseline]
        if kind in ("indicator_small_door", "indicator_box"):
            from ae_engine.manufacturing_baseline_policy import _indicator_shared_expected_path
            counterpart_name = ("盒子.dxf" if kind == "indicator_small_door"
                                else "小門.dxf")
            counterpart = _indicator_shared_expected_path(counterpart_name, ctx)
            if counterpart is None or counterpart.parent != baseline.parent:
                raise PrepareEvidenceError(
                    "WHD_RESOURCE_UNVERIFIED", "WHD shared-indicator baselines are not paired",
                )
            selected_baselines.append(counterpart)
        for selected in selected_baselines:
            # Do not resolve before checking the exact physical path: that
            # would erase a symlink alias from the signed source manifest.
            probe = selected
            while probe != resource_root and probe != probe.parent:
                if probe.is_symlink():
                    raise PrepareEvidenceError(
                        "WHD_RESOURCE_PATH_INVALID", "selected WHD baseline is symlinked",
                    )
                probe = probe.parent
            try:
                relative = selected.resolve().relative_to(resource_root.resolve()).as_posix()
            except ValueError as exc:
                raise PrepareEvidenceError(
                    "WHD_RESOURCE_PATH_INVALID", "baseline escapes trusted resource root",
                ) from exc
            baselines.add(relative)
        recorded.append({
            "item_id": item["item_id"],
            "physical_part_id": physical_id,
            "source_part_ref": p["source_part_ref"],
            "source_document_sha256": item["source_document_sha256"],
            "target_frame": frame,
            "locked_dimensions_mm": {
                "raw_part": p, "authoritative": authoritative
            },
        })
    evidence = build_resource_evidence(
        resource_root=resource_root,registry_path=_REGISTRY_PATH,
        baseline_paths=sorted(baselines),resolved_policy=asdict(policy),
        locked_inputs={"client_installation_id":request["client_installation_id"],
                       "job_id":request["job_id"],"items":recorded},
        engine_commit=engine_commit,engine_sha256=engine_sha256,
        build_id=build_id,
    )
    # Parsing is necessary in addition to resource-byte attestation. Hash
    # again afterwards so any concurrent file mutation between reading and
    # parsing invalidates the entire batch before a token can be issued.
    _validate_owning_resource_parsers(resource_root, sorted(baselines))
    current = build_resource_evidence(
        resource_root=resource_root,registry_path=_REGISTRY_PATH,
        baseline_paths=sorted(baselines),resolved_policy=asdict(policy),
        locked_inputs={"client_installation_id":request["client_installation_id"],
                       "job_id":request["job_id"],"items":recorded},
        engine_commit=engine_commit,engine_sha256=engine_sha256,
        build_id=build_id,
    )
    assert_snapshot_current(evidence, current)
    sealed = create_preparation_binding(
        worker_key=worker_key, client_installation_id=request["client_installation_id"],
        job_id=request["job_id"],
        environment_fingerprint=evidence["environment_fingerprint"],
        prepared_items=recorded,
    )
    result = {
        "protocol_version":"1.1.0",
        "client_installation_id":request["client_installation_id"],
        "request_id":request["request_id"],
        "job_id":request["job_id"],
        "request_digest":request["request_digest"],
        "operation":"prepare",
        "status":"success",
        "engine_commit":engine_commit,
        "build_id":build_id,
        "environment_fingerprint":evidence["environment_fingerprint"],
        "prepare_token":sealed["prepare_token"],
        "manufacturing_verified":False,
        "items":[{
            "item_id":p["item_id"],
            "status":"prepared",
            "physical_part_id":p["physical_part_id"],
            "preparation_digest":sealed["item_preparation_digests"][p["item_id"]],
            "target_frames":[p["target_frame"]],
            "required_inputs":([] if p["target_frame"]["allowed_feature_types"] == []
                               else ["source_transform","verified_source_entity_refs"]),
            "production_scope":"single_part",
            "manufacturing_verified":False,
            "diagnostics":[],
        } for p in recorded],
        "diagnostics":[],
    }
    resp_schema = Draft202012Validator(
        __import__("json").loads((schema_dir / "response_v1_1.schema.json").read_text(encoding="utf-8"))
    )
    resp_schema.validate(result)
    return result
