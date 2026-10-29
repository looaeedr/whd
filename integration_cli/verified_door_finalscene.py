# -*- coding: utf-8 -*-
"""#2379 W-04 internal authenticated Door CIRCLE → WHD FinalScene → batch DXF.

NOT a public Worker export. W-06 must supply trusted immutable prepare state,
installation HMAC key, original DXF file custody, exclusive output-path locks,
journal, retries and crash recovery before this may be exposed.
"""
from __future__ import annotations

from dataclasses import replace
import math
from pathlib import Path
from typing import Any, Mapping

from integration_cli.prepare_batch import door_spec_from_trusted_prepared_part
from integration_cli.prepare_evidence import PrepareEvidenceError, _pure_json
from integration_cli.prepare_frame import resolve_door_finished_local_frame
from integration_cli.prepare_recheck import recheck_trusted_door_export
from integration_cli.source_circle_verification import verify_trusted_original_dxf_circles

_SOURCE_CIRCLE_MARKER = "cadsplit_source_verified_circle_v1"
_TOL = 1e-6


def _reject(message: str) -> None:
    raise PrepareEvidenceError("WHD_FINALSCENE_UNVERIFIED", message)


def _assert_original_circles_in_final_scene(render_data, mapped_circles) -> None:
    """Fail closed if WHD's scene builder silently drops/moves original holes.

    The scene is deliberately *pre-export* and unmirrored. The canonical
    FinalScene serializer preserves that scene; legacy Door generate_part()
    adds a separate final X mirror and is NOT the oracle for this path.
    """
    from ae_engine.sheetmetal_drawing import CirclePrimitive

    actual = [
        p for p in render_data.scene.primitives
        if isinstance(p, CirclePrimitive) and p.layer == "CUTTING"
        and p.source_type == _SOURCE_CIRCLE_MARKER
    ]
    if len(actual) != len(mapped_circles):
        _reject("a verified source CIRCLE was lost or duplicated in WHD FinalScene")
    unmatched = list(actual)
    for expected in mapped_circles:
        matches = [
            p for p in unmatched
            if math.isclose(float(p.center.x), float(expected.offset.x), abs_tol=_TOL, rel_tol=0)
            and math.isclose(float(p.center.y), float(expected.offset.y), abs_tol=_TOL, rel_tol=0)
            and math.isclose(float(p.radius), float(expected.diameter) / 2, abs_tol=_TOL, rel_tol=0)
        ]
        if len(matches) != 1:
            _reject("verified source CIRCLE location/radius changed inside WHD FinalScene")
        unmatched.remove(matches[0])


def save_trusted_door_circle_finalscene_batch(
    trusted_prepare_request: Mapping[str, Any],
    trusted_prepare_response: Mapping[str, Any],
    export_request: Mapping[str, Any],
    *,
    source_documents: Mapping[str, Path],
    resource_root: Path,
    output_dir: Path,
    engine_commit: str,
    engine_sha256: str,
    build_id: str,
    worker_key: bytes,
    overwrite: bool = False,
) -> dict[str, str]:
    """Source-verified Door-only all-or-nothing batch; never accepts caller PartSpec.

    The original W-03 authenticated prepare request/receipt are Worker-owned.
    This function derives WHD DoorPartSpec from *those* original dimensions and
    Factory Policy, never from export wire dimensions. The original-DXF path,
    resource root and destination are supplied by the trusted Worker, not wire.
    W-03 checks *before render*, *before staging*, *again after Save→Reload*.
    W-06 still owns durability, output locks, journal and key/source custody.
    """
    from ae_engine.contracts import ManufacturingContext
    from ae_engine.manufacturing_api import (
        build_part_render_data, resolve_policy, save_verified_final_scene_batch_dxf,
    )
    from ae_engine.manufacturing_endcap_compat import _door_features_for_legacy_engine

    if not isinstance(source_documents, Mapping) or not isinstance(resource_root, Path):
        _reject("Worker-owned original source custody and resource root required")
    if not isinstance(output_dir, Path):
        _reject("Worker-owned output directory required")
    if (not isinstance(export_request, Mapping)
            or export_request.get("transaction_mode") != "all_or_nothing"):
        _reject("only W-04 all_or_nothing Door batch supported")

    def guard() -> None:
        recheck_trusted_door_export(
            trusted_prepare_request, trusted_prepare_response, export_request,
            source_documents=source_documents, resource_root=resource_root,
            engine_commit=engine_commit, engine_sha256=engine_sha256,
            build_id=build_id, worker_key=worker_key,
        )

    # Never create or touch output directories until the complete original
    # prepare token, source bytes, Frame and all batch identities are current.
    guard()
    original_items = trusted_prepare_request["items"]
    receipt_items = trusted_prepare_response["items"]
    exported_items = export_request["items"]
    if not 1 <= len(original_items) <= 20:
        _reject("unverified or empty physical-part batch")

    initial = ManufacturingContext(resource_root=resource_root)
    policy = resolve_policy(initial)
    context = ManufacturingContext(resource_root=resource_root, policy=policy)
    rows = []
    for original, receipt, exported in zip(original_items, receipt_items, exported_items):
        if original["part"]["kind"] != "door" or not exported.get("features"):
            _reject("only Door items with proven source CIRCLE inventory supported")
        original_item_id = original["item_id"]
        source_path = source_documents.get(original_item_id)
        # Do not accept an export-side replacement of canonical mechanical
        # inputs: the exact same adapter is used at W-03 prepare.
        spec = door_spec_from_trusted_prepared_part(original["part"], policy)
        frame = resolve_door_finished_local_frame(
            spec, context, physical_part_id=receipt["physical_part_id"],
        )
        if _pure_json(frame) != _pure_json(receipt["target_frames"][0]):
            _reject("WHD canonical Door frame differs from prepared frame")
        original_circles = verify_trusted_original_dxf_circles(
            exported["features"], source_path=source_path,
            expected_document_sha256=original["source_document_sha256"],
        )
        if len(original_circles) != len(exported["features"]):
            _reject("unverified source CIRCLE inventory")

        marked = tuple(replace(c, source_type=_SOURCE_CIRCLE_MARKER) for c in original_circles)
        owned_spec = replace(spec, features=marked, feature_space="finished_face")
        mapped = _door_features_for_legacy_engine(owned_spec, context)
        render = build_part_render_data(owned_spec, context)
        _assert_original_circles_in_final_scene(render, mapped)
        rows.append((receipt["physical_part_id"], render))

    # This engine owns staged DXFs and independent Save→Reload verification.
    # W-03 guard fires twice more around the stage, including source reread
    # after serialization and before any final os.replace.
    return save_verified_final_scene_batch_dxf(
        rows, output_dir, pre_commit_guard=guard, overwrite=overwrite,
    )
