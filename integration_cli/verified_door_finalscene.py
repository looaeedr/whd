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

from integration_cli.prepare_batch import (
    door_spec_from_trusted_prepared_part,
    indicator_small_door_spec_from_trusted_prepared_part,
    indicator_box_spec_from_trusted_prepared_part,
)
from integration_cli.prepare_evidence import PrepareEvidenceError, _pure_json
from integration_cli.prepare_frame import (
    resolve_door_finished_local_frame, resolve_indicator_box_size_only_frame,
)
from integration_cli.prepare_recheck import recheck_trusted_door_export
from integration_cli.source_circle_verification import verify_trusted_original_dxf_features

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
    from ae_engine.sheetmetal_drawing import CirclePrimitive, PolylinePrimitive
    from ae_engine.sheetmetal_features import CircleFeature, RectFeature, ProfileFeature, ResolvedRect

    actual = [
        p for p in render_data.scene.primitives
        if isinstance(p, CirclePrimitive) and p.layer == "CUTTING"
        and p.source_type == _SOURCE_CIRCLE_MARKER
    ]
    circles = tuple(x for x in mapped_circles if isinstance(x, CircleFeature))
    if len(actual) != len(circles):
        _reject("a verified source CIRCLE was lost or duplicated in WHD FinalScene")
    unmatched = list(actual)
    for expected in circles:
        matches = [
            p for p in unmatched
            if math.isclose(float(p.center.x), float(expected.offset.x), abs_tol=_TOL, rel_tol=0)
            and math.isclose(float(p.center.y), float(expected.offset.y), abs_tol=_TOL, rel_tol=0)
            and math.isclose(float(p.radius), float(expected.diameter) / 2, abs_tol=_TOL, rel_tol=0)
        ]
        if len(matches) != 1:
            _reject("verified source CIRCLE location/radius changed inside WHD FinalScene")
        unmatched.remove(matches[0])
    # A closed contour is an ordered cycle, not an unordered vertex set.
    # A bow-tie path may use exactly the same four corners and bounding box
    # as a valid rectangle, but connects different edges and must fail closed.
    # Permit only cyclic start shifts and reversed winding of the canonical
    # ResolvedRect path; neither changes the manufactured closed contour.
    def same_closed_contour(actual, expected):
        if len(actual) != len(expected):
            return False
        n = len(expected)
        for start in range(n):
            for direction in (1, -1):
                if all(
                    math.isclose(actual[(start + direction * i) % n].x, expected[i].x,
                                 abs_tol=_TOL, rel_tol=0)
                    and math.isclose(actual[(start + direction * i) % n].y, expected[i].y,
                                     abs_tol=_TOL, rel_tol=0)
                    for i in range(n)
                ):
                    return True
        return False

    # WHD's ResolvedRect generates the canonical four corners; unlike
    # CirclePrimitive, PolylinePrimitive has no source_type field. Compare
    # the full ordered CUTTING edge cycle for each source-derived RectFeature.
    available = [
        p for p in render_data.scene.primitives
        if isinstance(p, PolylinePrimitive) and p.layer == "CUTTING" and p.closed
    ]
    for expected in mapped_circles:
        if isinstance(expected, RectFeature):
            points = tuple(ResolvedRect(
                center=expected.offset, width=expected.width, height=expected.height,
                rotation_deg=expected.rotation_deg, layer="CUTTING",
            ).points)
        elif isinstance(expected, ProfileFeature):
            # ProfileFeature holds source-transformed finished-face vertices.
            # WHD maps its absolute anchor to the authoritative Door guide.
            points = tuple(expected.offset + p for p in expected.points)
        else:
            continue
        matches = []
        for poly in available:
            if same_closed_contour(poly.points, points):
                matches.append(poly)
        if len(matches) != 1:
            _reject("source-attested CUTTING contour missing or duplicated in FinalScene")
        available.remove(matches[0])


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
    durable_ledger=None,
) -> dict[str, str]:
    """Source-verified Door/small-door plus zero-feature box all-or-nothing batch.

    Never accepts a caller-controlled PartSpec. Box external Feature mapping
    remains disabled; only an entirely empty original DXF can use WHD-owned
    indicator-box FinalScene and independently verified DXF.

    The original W-03 authenticated prepare request/receipt are Worker-owned.
    Featureless Door/small-door is allowed only with an entirely empty original
    DXF modelspace, so no real source geometry can be silently dropped.
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
    if durable_ledger is not None:
        from integration_cli.job_identity_ledger import DurableJobIdentityLedger
        if not isinstance(durable_ledger, DurableJobIdentityLedger):
            _reject("trusted W-06 durable Worker ledger required")
        if output_dir.is_symlink() or not output_dir.is_dir():
            _reject("W-06 durable export needs preexisting trusted output directory")

    # The very first source guard runs before a W-06 job is claimed.
    # Later stage/commit guards can safely read its durable cancel intent.
    active_durable_job = False

    def guard() -> None:
        if active_durable_job:
            durable_ledger.assert_not_cancelled(export_request)
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
        kind = original["part"]["kind"]
        if kind not in ("door", "indicator_small_door", "indicator_box"):
            _reject("only WHD-owned Door/small-door/featureless box frames supported")
        if kind == "indicator_box" and exported.get("features"):
            _reject("shared indicator-box has no certified source-Feature mapping")
        # A source DXF containing untransferred geometry is never an
        # unperforated blank: even zero declared Features must not silently
        # drop any original entity. Only genuinely empty modelspace sources
        # can use WHD's intrinsic, hole-free Door/small-door manufacturing.
        # Source-side paths/SHAs are W-06 owned and independently rechecked
        # around staging and commit. No inferred source-to-DXF transform.
        if not exported.get("features"):
            from integration_cli.source_circle_verification import _source_snapshot
            original_dxf = _source_snapshot(
                source_documents.get(original["item_id"]),
                original["source_document_sha256"],
            )
            if any(True for _ in original_dxf.modelspace()):
                _reject("source DXF has untransferred geometry without declared Features")
        original_item_id = original["item_id"]
        source_path = source_documents.get(original_item_id)
        if kind == "indicator_box":
            # W-03 certifies ONLY WHD-owned box outside size; no local
            # source-Feature placement has been proved. When original DXF
            # modelspace and wire Features are BOTH empty, the physical box
            # and lamp layout are entirely resolved by WHD's own shared
            # baseline + IndicatorBoxPartSpec. Never synthesize a transform.
            spec = indicator_box_spec_from_trusted_prepared_part(
                original["part"], context,
            )
            frame = resolve_indicator_box_size_only_frame(
                spec, context, physical_part_id=receipt["physical_part_id"],
            )
            if _pure_json(frame) != _pure_json(receipt["target_frames"][0]):
                _reject("WHD box size-only frame differs from prepared Frame")
            render = build_part_render_data(spec, context)
            rows.append((receipt["physical_part_id"], render))
            continue
        # Do not accept an export-side replacement of canonical mechanical
        # inputs: the exact same adapter is used at W-03 prepare.
        spec = (
            door_spec_from_trusted_prepared_part(original["part"], policy)
            if kind == "door"
            else indicator_small_door_spec_from_trusted_prepared_part(
                original["part"], context
            )
        )
        frame = resolve_door_finished_local_frame(
            spec, context, physical_part_id=receipt["physical_part_id"],
        )
        if _pure_json(frame) != _pure_json(receipt["target_frames"][0]):
            _reject("WHD canonical Door frame differs from prepared frame")
        original_features = verify_trusted_original_dxf_features(
            exported["features"], source_path=source_path,
            expected_document_sha256=original["source_document_sha256"],
        )
        if len(original_features) != len(exported["features"]):
            _reject("unverified source CIRCLE inventory")

        marked = tuple(replace(c, source_type=_SOURCE_CIRCLE_MARKER) for c in original_features)
        owned_spec = replace(spec, features=marked, feature_space="finished_face")
        mapped = _door_features_for_legacy_engine(owned_spec, context)
        render = build_part_render_data(owned_spec, context)
        _assert_original_circles_in_final_scene(render, mapped)
        rows.append((receipt["physical_part_id"], render))

    # Existing W-04 callers retain normal WHD Save->Reload plus its
    # in-process rollback. The PRIVATE W-06 branch is opt-in by an already
    # authenticated Worker that supplies its installation-owned ledger.
    commit_staged = None
    if durable_ledger is not None:
        from integration_cli.original_backup_manifest import DurableOriginalBackupEvidence
        from integration_cli.batch_commit_journal import DurableMultiDXFRollbackJournal

        claim = durable_ledger.claim(export_request)
        if claim.state != "new":
            _reject("durable job cannot be rendered again; read its immutable result")
        active_durable_job = True
        durable_ledger.assert_not_cancelled(export_request)
        durable_ledger.reserve_output_directories(
            export_request, trusted_directories=[output_dir],
        )
        from integration_cli.worker_progress import PrivateWorkerProgress
        progress = PrivateWorkerProgress(durable_ledger)
        progress.publish(export_request)

        def commit_staged(staged: Mapping[str, Path], root: Path) -> dict[str, str]:
            # This callback runs ONLY after all 1..20 WHD-owned staged DXFs
            # survived the independent Save->Reload verifier and the final
            # W-03 source, policy, Frame, HMAC and source bytes recheck.
            if root != output_dir or set(staged) != {physical for physical, _ in rows}:
                _reject("verified staged physical inventory differs from prepared job")
            guard()
            durable_ledger.record_staged_batch_snapshot(
                export_request, trusted_output_dir=root,
                trusted_staged=staged, overwrite=overwrite,
            )
            progress.publish(export_request)
            backup = DurableOriginalBackupEvidence(durable_ledger)
            backup.create_verified_original_backups(
                export_request, trusted_output_dir=root,
            )
            journal = DurableMultiDXFRollbackJournal(durable_ledger)
            journal.arm(export_request)
            actual = journal.apply(export_request)
            # Only the trusted W-06 journal and verified physical final DXFs
            # may publish a committed immutable job result and release leases.
            receipt = {
                "operation": "export",
                "client_installation_id": export_request["client_installation_id"],
                "job_id": export_request["job_id"],
                "request_digest": export_request["request_digest"],
                "status": "success",
                "manufacturing_verified": False,  # not a public package certification
                "items": [{"physical_part_id": physical, "path": str(path)}
                          for physical, path in actual.items()],
            }
            durable_ledger.complete(
                export_request, receipt, trusted_artifacts=actual,
            )
            progress.publish(export_request)
            return {physical: str(path) for physical, path in actual.items()}

    # This engine owns staged DXFs and independent Save→Reload verification.
    # W-03 guard fires twice more around the stage, including source reread
    # after serialization and before any final os.replace.
    return save_verified_final_scene_batch_dxf(
        rows, output_dir, pre_commit_guard=guard, overwrite=overwrite,
        durable_stage_commit=commit_staged,
    )
