# -*- coding: utf-8 -*-
"""#2375: W-01 Worker _execute_request -> private W-03/W-06/W-04 real DXF.

The normal CLI main() never accepts TrustedWorkerExecution. These tests
exercise the same request entry internally and actual WHD manufacturing
sources, Save->Reload DXF, DPAPI on Windows, durable replay and corruption.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys

import ezdxf
import pytest

from integration_cli.cadsplit_worker import _execute_request
from integration_cli.job_identity_ledger import DurableJobIdentityLedger
from integration_cli.private_worker_dispatch import TrustedWorkerExecution
from integration_cli.request_canonical import compute_wire_request_digest
from integration_cli.worker_progress import PrivateWorkerProgress
from test_issue2378_prepare_batch import KEY, COMMIT, ENGINE, _export_request_from_prepared
from test_issue2379_trusted_door_finalscene_batch import _real_batch


BUILD = "test-only-source"


def _context(tmp_path, batch, key=KEY):
    original, receipt, export, root, paths, source, *_ = batch
    store = tmp_path / "真正受信 Worker state"
    output = tmp_path / "客戶 實體 DXF output"
    store.mkdir()
    output.mkdir()
    return TrustedWorkerExecution(
        resource_root=root, store_root=store,
        output_dir=output, source_documents=paths,
        worker_key=key, engine_sha256=ENGINE,
    )


def _call(tmp_path, operation, request, context=None):
    path = tmp_path / f"{operation}-wire.json"
    path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    return _execute_request(
        operation, path, COMMIT, BUILD, trusted_context=context,
    )


def _export_from_real_sources(original, fresh_receipt, batch):
    result = _export_request_from_prepared(original, fresh_receipt)
    source_doc = ezdxf.readfile(batch[5])
    saved_handles = {str(e.dxf.handle).upper(): e.dxftype()
                     for e in source_doc.modelspace() if e.dxf.hasattr("handle")}
    for row, actual in zip(result["items"], batch[2]["items"]):
        row["features"] = deepcopy(actual["features"])
        for feature in row["features"]:
            refs = feature["source_transform"]["source_entity_refs"]
            assert len(refs) == 1 and saved_handles.get(refs[0].upper()) == "CIRCLE"
        from integration_cli.source_circle_verification import verify_trusted_original_dxf_features
        verified = verify_trusted_original_dxf_features(
            row["features"], source_path=batch[4][row["item_id"]],
            expected_document_sha256=row["source_document_sha256"],
        )
        assert len(verified) == len(row["features"])
    result["request_digest"] = compute_wire_request_digest(result)
    return result


def test_private_real_worker_prepare_export_writes_true_dxf_then_replays_without_rewriting(tmp_path):
    batch = _real_batch(tmp_path, count=2)
    original = batch[0]
    context = _context(tmp_path, batch)
    prepared, exit_code = _call(tmp_path, "prepare", original, context)
    assert exit_code == 0
    assert prepared["status"] == "success"
    assert prepared["manufacturing_verified"] is False
    assert len(prepared["items"]) == 2
    export = _export_from_real_sources(original, prepared, batch)
    export["output"]["directory"] = str(context.output_dir)
    export["request_digest"] = compute_wire_request_digest(export)
    finished, code = _call(tmp_path, "export", export, context)
    assert code == 0 and finished["status"] == "success", finished.get("diagnostics", [{}])[0].get("message")
    assert finished["manufacturing_verified"] is False  # PRIVATE only
    paths = {Path(x["path"]) for x in finished["items"]}
    assert len(paths) == 2
    assert all(p.is_file() and p.parent == context.output_dir for p in paths)
    assert all(len(ezdxf.readfile(p).modelspace().query("CIRCLE")) >= 1 for p in paths)
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}
    assert PrivateWorkerProgress(DurableJobIdentityLedger(context.store_root)).read(export)["percent"] == 100
    # Retry is an authenticated original receipt; no second DXF generation.
    retry = deepcopy(export)
    retry["request_id"] = "transport-reissue"
    assert compute_wire_request_digest(retry) == export["request_digest"]
    replay, code = _call(tmp_path, "export", retry, context)
    assert code == 0 and replay == finished
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths} == before
    assert _call(tmp_path, "prepare", original, context)[0] == prepared


def test_private_worker_refuses_wire_output_redirect_and_unprepared_export(tmp_path):
    batch = _real_batch(tmp_path)
    context = _context(tmp_path, batch)
    orig = batch[0]
    receipt, code = _call(tmp_path, "prepare", orig, context)
    assert code == 0
    export = _export_from_real_sources(orig, receipt, batch)
    export["output"]["directory"] = str(tmp_path / "client-picked-dir")
    export["request_digest"] = compute_wire_request_digest(export)
    failed, code = _call(tmp_path, "export", export, context)
    assert code != 0
    assert failed["diagnostics"][0]["code"] == "WHD_OUTPUT_PATH_INVALID"
    assert not (tmp_path / "client-picked-dir").exists()
    assert not list(context.output_dir.glob("*.dxf"))


def test_private_worker_never_accepts_copied_or_tampered_prepare_source_receipt(tmp_path):
    batch = _real_batch(tmp_path)
    orig = batch[0]
    context = _context(tmp_path, batch)
    valid, code = _call(tmp_path, "prepare", orig, context)
    assert code == 0
    export = _export_from_real_sources(orig, valid, batch)
    export["output"]["directory"] = str(context.output_dir)
    export["request_digest"] = compute_wire_request_digest(export)
    # Merely presenting a valid token with the wrong Worker-owned key is
    # NOT sufficient to produce an export.
    wrong = TrustedWorkerExecution(
        resource_root=context.resource_root, store_root=context.store_root,
        output_dir=context.output_dir, source_documents=context.source_documents,
        worker_key=b"untrusted-cadsplit-client-key" + b"x" * 32,
        engine_sha256=ENGINE,
    )
    refused, code = _call(tmp_path, "export", export, wrong)
    assert code != 0
    assert refused["diagnostics"][0]["code"] == "WHD_JOB_RECOVERY_REQUIRED"
    assert not list(context.output_dir.glob("*.dxf"))
    # A different client source digest with correctly recomputed canonical
    # wire digest must still reject against persisted original W-03 receipt.
    modified = deepcopy(export)
    modified["items"][0]["part"]["dimensions_mm"]["width"] += 1
    modified["request_digest"] = compute_wire_request_digest(modified)
    refused, code = _call(tmp_path, "export", modified, context)
    assert code != 0
    assert not list(context.output_dir.glob("*.dxf"))


def test_public_worker_never_accepts_private_context_from_wire(tmp_path):
    batch = _real_batch(tmp_path, count=1)
    req = batch[0]
    req["trusted_context"] = {
        "enabled": True, "worker_key": KEY.hex(),
        "store_root": str(tmp_path), "resource_root": str(batch[3]),
    }
    result, code = _call(tmp_path, "prepare", req, None)
    assert code != 0
    assert result["manufacturing_verified"] is False
    assert result["status"] == "failed"
    assert not list(tmp_path.rglob("progress.json"))


@pytest.mark.skipif(sys.platform != "win32", reason="requires real Windows DPAPI")
def test_windows_dpapi_key_does_real_worker_prepare_restart_export(tmp_path, monkeypatch):
    from integration_cli.worker_key_custody import load_installation_key
    profile = tmp_path / "local DPAPI profile"
    profile.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(profile))
    key = load_installation_key("trusted-worker-dispatch-1", initialize=True)
    batch = _real_batch(tmp_path)
    context = _context(tmp_path, batch, key)
    original = batch[0]
    result, code = _call(tmp_path, "prepare", original, context)
    assert code == 0 and result["status"] == "success"
    # Real OS DPAPI re-open and freshly constructed W-06 ledger after restart.
    restarted_context = TrustedWorkerExecution(
        resource_root=context.resource_root,
        store_root=context.store_root,
        output_dir=context.output_dir,
        source_documents=context.source_documents,
        worker_key=load_installation_key("trusted-worker-dispatch-1"),
        engine_sha256=ENGINE,
    )
    export = _export_from_real_sources(original, result, batch)
    export["output"]["directory"] = str(context.output_dir)
    export["request_digest"] = compute_wire_request_digest(export)
    finished, status = _call(tmp_path, "export", export, restarted_context)
    assert status == 0 and finished["status"] == "success", finished.get("diagnostics", [{}])[0].get("message")
    assert len(list(context.output_dir.glob("*.dxf"))) == 2
    assert all(len(ezdxf.readfile(p).modelspace().query("CIRCLE")) >= 1
               for p in context.output_dir.glob("*.dxf"))
