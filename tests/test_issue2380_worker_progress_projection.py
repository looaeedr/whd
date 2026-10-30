# -*- coding: utf-8 -*-
"""#2380 actual W-06 ledger-derived progress.json safety and restart tests.

Real WHD two-DXF stage, backed-up originals, journal and prepare HMAC are
the authorities; progress.json is only a read-only projection in Worker store.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from integration_cli.job_identity_ledger import DurableJobIdentityLedger
from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.worker_progress import PrivateWorkerProgress
from test_issue2378_request_canonical import (
    _w06_committing_context, _w06_request, _w06_result,
)
from test_issue2378_prepare_batch import _request, _root, COMMIT, ENGINE, KEY


def test_actual_multidxf_progress_staged_armed_applied_and_only_verified_complete(tmp_path):
    store, out, old, stage1, stage2, req, ledger, journal, proof = _w06_committing_context(tmp_path)
    before = old.read_bytes(), old.stat().st_mtime_ns
    projection = PrivateWorkerProgress(ledger)
    target = projection.publish(req)
    assert target.name == "progress.json"
    assert target.parent.parent == store / "progress"
    assert json.loads(target.read_text(encoding="utf-8"))["phase"] == "staged"
    assert projection.read(req)["percent"] == 50
    assert projection.read(req)["manufacturing_verified"] is False
    journal.arm(req)
    assert projection.read(req)["phase"] == "precommit"
    assert projection.read(req)["percent"] == 75
    assert json.loads(target.read_text(encoding="utf-8"))["phase"] == "precommit"
    assert (old.read_bytes(), old.stat().st_mtime_ns) == before
    result = journal.apply(req)
    assert projection.read(req)["phase"] == "awaiting_verified_receipt"
    assert projection.read(req)["percent"] == 90
    assert json.loads(target.read_text(encoding="utf-8"))["percent"] == 90
    # Even physically copied final DXFs do not authorize 100% without the
    # immutable, complete W-06 receipt and physical Save/Reload proofs.
    ledger.complete(req, _w06_result(req), trusted_artifacts=result)
    final_path = PrivateWorkerProgress(DurableJobIdentityLedger(store)).publish(req)
    final = json.loads(final_path.read_text(encoding="utf-8"))
    assert final["phase"] == "completed" and final["percent"] == 100
    assert final["completed_items"] == final["total_items"] == 1
    assert final["manufacturing_verified"] is False
    first_mtime = final_path.stat().st_mtime_ns
    replay = PrivateWorkerProgress(DurableJobIdentityLedger(store)).read(req)
    assert replay == final
    assert final_path.stat().st_mtime_ns == first_mtime


def test_fake_success_json_cannot_authorize_a_durable_unfinished_job(tmp_path):
    store, out, old, stage1, stage2, req, ledger, journal, proof = _w06_committing_context(tmp_path)
    progress = PrivateWorkerProgress(ledger)
    path = progress.publish(req)
    forged = json.loads(path.read_text(encoding="utf-8"))
    forged.update(phase="completed", percent=100, completed_items=99,
                  manufacturing_verified=True)
    path.write_text(json.dumps(forged), encoding="utf-8")
    # Raw file is never input to the real Worker state machine.
    fresh = PrivateWorkerProgress(DurableJobIdentityLedger(store)).read(req)
    assert fresh["phase"] == "staged" and fresh["percent"] == 50
    assert fresh["manufacturing_verified"] is False
    assert old.exists()
    assert not (out / "part-two.dxf").exists()
    progress.publish(req)
    assert json.loads(path.read_text(encoding="utf-8")) == fresh


def test_cancelled_progress_persists_without_manufactured_success(tmp_path):
    store = tmp_path / "trusted Worker 狀態"
    store.mkdir()
    req = _w06_request(operation="export")
    led = DurableJobIdentityLedger(store)
    assert led.claim(req).state == "new"
    proj = PrivateWorkerProgress(led)
    assert proj.publish(req).is_file()
    assert proj.read(req)["phase"] == "claimed"
    assert led.request_cancel(req) == "requested"
    saved = PrivateWorkerProgress(DurableJobIdentityLedger(store)).read(req)
    assert saved["phase"] == "cancel_requested"
    assert saved["percent"] == 0
    path, = (store / "progress").rglob("progress.json")
    assert json.loads(path.read_text(encoding="utf-8")) == saved
    with pytest.raises(PrepareEvidenceError) as exc:
        led.complete(req, _w06_result(req), trusted_artifacts={})
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"


def test_crash_between_real_dxf_renames_never_projects_false_100(tmp_path):
    store, out, old, stage1, stage2, req, ledger, journal, proof = _w06_committing_context(tmp_path)
    journal.arm(req)
    def interrupt(_):
        raise SystemExit("test hard stop after one real DXF rename")
    with pytest.raises(SystemExit):
        journal.apply(req, after_replace=interrupt)
    saved = PrivateWorkerProgress(DurableJobIdentityLedger(store)).read(req)
    assert saved["phase"] == "recovery_required"
    assert saved["percent"] < 100
    path, = (store / "progress").rglob("progress.json")
    assert json.loads(path.read_text(encoding="utf-8"))["phase"] == "recovery_required"
    with pytest.raises(PrepareEvidenceError):
        DurableJobIdentityLedger(store).claim(req)


def test_prepare_progress_needs_worker_hmac_and_true_source_receipt(tmp_path):
    resource, _, _ = _root(tmp_path)
    store = tmp_path / "Worker-權限"
    store.mkdir()
    original = _request(count=2)
    ledger = DurableJobIdentityLedger(store)
    receipt = ledger.prepare_and_persist(
        original, resource_root=resource, engine_commit=COMMIT,
        engine_sha256=ENGINE, build_id="test-only-source", worker_key=KEY,
    )
    assert receipt["status"] == "success"
    progress = PrivateWorkerProgress(DurableJobIdentityLedger(store))
    with pytest.raises(PrepareEvidenceError) as exc:
        progress.read(original)  # missing key may not publish 100%
    assert exc.value.code == "WHD_PREPARE_KEY_UNAVAILABLE"
    snapshot = progress.read(original, worker_key=KEY)
    assert snapshot["phase"] == "prepared"
    assert snapshot["percent"] == 100
    assert snapshot["completed_items"] == 2
    assert snapshot["manufacturing_verified"] is False
    saved, = (store / "progress").rglob("progress.json")
    assert json.loads(saved.read_text(encoding="utf-8")) == snapshot
    altered = deepcopy(original)
    altered["request_id"] = "retry-transport-only"
    assert progress.read(altered, worker_key=KEY) == snapshot
    with pytest.raises(PrepareEvidenceError):
        progress.read(original, worker_key=b"x" * 32)


def test_progress_job_identity_and_path_are_never_client_selected(tmp_path):
    store = tmp_path / "Worker-database"
    store.mkdir()
    led = DurableJobIdentityLedger(store)
    first = _w06_request(operation="export", job="job-one")
    second = _w06_request(operation="export", job="job-two")
    for req in (first, second):
        assert led.claim(req).state == "new"
    a, b = (PrivateWorkerProgress(led).publish(req) for req in (first, second))
    assert a != b and a.name == b.name == "progress.json"
    assert a.is_relative_to(store) and b.is_relative_to(store)
    forged = deepcopy(first)
    forged["output"]["directory"] = "client-chosen-output"
    with pytest.raises(PrepareEvidenceError):
        PrivateWorkerProgress(led).publish(forged)
    assert not (tmp_path / "client-chosen-output").exists()
