# -*- coding: utf-8 -*-
"""#2378 W-03 in-process Door prepare, gated on trusted inputs and key custody.

This function is a testable orchestration boundary, NOT the CLI handler.
W-06 owns installation key custody, journal and replay. W-04 owns export.
No source geometry can be committed by this module.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from integration_cli.prepare_binding import create_preparation_binding
from integration_cli.prepare_evidence import (
    PrepareEvidenceError, assert_snapshot_current, build_resource_evidence, resolve_authoritative_door_inputs
)
from integration_cli.prepare_frame import resolve_door_finished_local_frame
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


def prepare_trusted_door_batch(
    request: Mapping[str, Any], *,
    resource_root: Path, engine_commit: str, engine_sha256: str,
    build_id: str, worker_key: bytes,
) -> dict[str, Any]:
    """Return schema-validated preparation with no DXF and no manufacturing claim.

    No caller can enable this through the public source-only CLI: the trusted
    W-06 key lifecycle and W-05 resource manifest are not yet available.
    """
    from ae_engine.contracts import DoorPartSpec, ManufacturingContext
    from ae_engine.manufacturing_api import (
        expected_baseline_path_for, resolve_policy,
    )
    from ae_engine.sheetmetal_part_adapters import DoorFrameEdges

    schema_dir = Path(__file__).resolve().parent / "schemas"
    req_schema = Draft202012Validator(
        __import__("json").loads((schema_dir / "request_v1.schema.json").read_text(encoding="utf-8"))
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
        if p["kind"] != "door" or p["dimension_semantics"] != "cabinet_outer":
            raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "only verified cabinet_outer Door-local frame is supported")
        flags = p.get("frame_edges")
        if not isinstance(flags, dict) or set(flags) != {"left","right","top","bottom"} or not all(type(v) is bool for v in flags.values()):
            raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "source layout must explicitly certify all four Door frame edges")
        dims = p["dimensions_mm"]
        if not all(k in dims for k in ("width","height","thickness")):
            raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "complete verified Door input dimensions required")
        if item["item_id"] in identities:
            raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "duplicate item ID")
        identities.add(item["item_id"])
        frame_width = p.get("frame_width_mm", float(policy.frame_width))
        door = DoorPartSpec(
            width=float(dims["width"]), height=float(dims["height"]),
            thickness=float(dims["thickness"]), frame_width=float(frame_width),
            model_name=p["cabinet_family"],
            gap_w=p.get("gap_w_mm"), gap_h=p.get("gap_h_mm"),
            fold_left=p.get("fold_left_mm"), fold_right=p.get("fold_right_mm"),
            fold_top=p.get("fold_top_mm"), fold_bottom=p.get("fold_bottom_mm"),
            frame_edges=DoorFrameEdges(**flags),
        )
        identity_bytes = ("WHD-PART-v1\0" + request["client_installation_id"]
                + "\0" + request["job_id"] + "\0" + item["item_id"]
                + "\0" + p["source_part_ref"] + "\0" + item["source_document_sha256"]).encode("utf-8")
        physical_id = "whd-" + hashlib.sha256(identity_bytes).hexdigest()[:24]
        authoritative = resolve_authoritative_door_inputs(door, ctx)
        frame = resolve_door_finished_local_frame(door, ctx, physical_part_id=physical_id)
        baseline = expected_baseline_path_for(door, ctx)
        if baseline is None:
            raise PrepareEvidenceError("WHD_RESOURCE_UNVERIFIED", "WHD could not identify its Door baseline")
        # Resolving a symlink before creating the manifest would erase
        # the fact that a different physical file was selected.
        probe = baseline
        while probe != resource_root and probe != probe.parent:
            if probe.is_symlink():
                raise PrepareEvidenceError("WHD_RESOURCE_PATH_INVALID", "selected WHD baseline is symlinked")
            probe = probe.parent
        try:
            relative = baseline.resolve().relative_to(resource_root.resolve()).as_posix()
        except ValueError as exc:
            raise PrepareEvidenceError("WHD_RESOURCE_PATH_INVALID", "baseline escapes trusted resource root") from exc
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
        "protocol_version":"1.0.0",
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
            "required_inputs":["source_transform","verified_source_entity_refs"],
            "production_scope":"single_part",
            "manufacturing_verified":False,
            "diagnostics":[],
        } for p in recorded],
        "diagnostics":[],
    }
    resp_schema = Draft202012Validator(
        __import__("json").loads((schema_dir / "response_v1.schema.json").read_text(encoding="utf-8"))
    )
    resp_schema.validate(result)
    return result
