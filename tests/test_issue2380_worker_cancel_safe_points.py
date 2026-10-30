# -*- coding: utf-8 -*-
"""#2380 W-06 private cancellation is durable and never cuts a DXF replacement.

Actual W-06 two-DXF stage/backup/journal fixtures are used, not string mocks.
These tests do not activate CADSplit public CLI or release a manufactured DXF.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import sqlite3

import pytest

from integration_cli.job_identity_ledger import DurableJobIdentityLedger
from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.request_canonical import compute_wire_request_digest
from test_issue2378_request_canonical import (
    _w06_committing_context, _w06_request, _w06_result,
)
from test_issue2378_prepare_batch import _request, _root, COMMIT, ENGINE, KEY


def _code(error):
    return error.value.code


def test_cancel_persists_across_process_reopen_before_dxf_arm(tmp_path):
    store, directory, original, stage1, stage2, req, ledger, journal, proof = (
        _w06_committing_context(tmp_path)
    )
    original_bytes = original.read_bytes()
    original_mtime = original.stat().st_mtime_ns
    assert ledger.request_cancel(req) == "requested"
    reloaded = DurableJobIdentityLedger(store)
    assert reloaded.request_cancel(req) == "requested"  # durable idempotent
    with pytest.raises(PrepareEvidenceError) as exc:
        reloaded.assert_not_cancelled(req)
    assert _code(exc) == "WHD_JOB_CANCELLED"
    with pytest.raises(PrepareEvidenceError) as exc:
        journal.arm(req)
    assert _code(exc) == "WHD_JOB_CANCELLED"
    assert original.read_bytes() == original_bytes
    assert original.stat().st_mtime_ns == original_mtime
    assert stage1.exists() and stage2.exists()  # no untrusted cleanup
    assert not (directory / "part-two.dxf").exists()
    with sqlite3.connect(store / "job_identity.sqlite3") as db:
        assert not db.execute(
            "SELECT 1 FROM batch_replace_journals WHERE operation='export'"
        ).fetchone()
    # An unfinished cancelled job cannot be "retried" as another manufacture.
    with pytest.raises(PrepareEvidenceError) as exc:
        reloaded.claim(req)
    assert _code(exc) == "WHD_JOB_RECOVERY_REQUIRED"


def test_cancel_after_durable_arming_must_not_interrupt_or_claim_success(tmp_path):
    store, directory, original, stage1, stage2, req, ledger, journal, proof = (
        _w06_committing_context(tmp_path)
    )
    journal.arm(req)
    with pytest.raises(PrepareEvidenceError) as exc:
        DurableJobIdentityLedger(store).request_cancel(req)
    assert _code(exc) == "WHD_JOB_RECOVERY_REQUIRED"
    journal_state, _ = journal._read(req)
    assert journal_state == "armed"
    with sqlite3.connect(store / "job_identity.sqlite3") as db:
        assert not db.execute(
            "SELECT 1 FROM job_cancel_intents WHERE operation='export'"
        ).fetchone()
    output = journal.apply(req)
    ledger.complete(req, _w06_result(req), trusted_artifacts=output)
    assert DurableJobIdentityLedger(store).claim(req).state == "committed"


def test_cancel_different_semantic_digest_conflicts_without_canceling_owner(tmp_path):
    store = tmp_path / "trusted-worker"
    store.mkdir()
    led = DurableJobIdentityLedger(store)
    req = _w06_request(operation="export")
    assert led.claim(req).state == "new"
    changed = deepcopy(req)
    changed["items"][0]["part"]["dimensions_mm"]["width"] += 11
    changed["request_digest"] = compute_wire_request_digest(changed)
    with pytest.raises(PrepareEvidenceError) as exc:
        led.request_cancel(changed)
    assert _code(exc) == "WHD_JOB_ID_CONFLICT"
    DurableJobIdentityLedger(store).assert_not_cancelled(req)


def test_cancel_and_arm_are_serialized_without_customer_file_damage(tmp_path):
    store, directory, original, stage1, stage2, req, ledger, journal, proof = (
        _w06_committing_context(tmp_path)
    )
    before = original.read_bytes(), original.stat().st_mtime_ns

    def cancel():
        try:
            return "cancel:" + DurableJobIdentityLedger(store).request_cancel(req)
        except PrepareEvidenceError as exc:
            return "cancel:" + exc.code

    def arm():
        from integration_cli.batch_commit_journal import DurableMultiDXFRollbackJournal
        try:
            DurableMultiDXFRollbackJournal(DurableJobIdentityLedger(store)).arm(req)
            return "arm:armed"
        except PrepareEvidenceError as exc:
            return "arm:" + exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        f = pool.submit(cancel)
        g = pool.submit(arm)
        observed = {f.result(), g.result()}
    assert observed in (
        {"cancel:requested", "arm:WHD_JOB_CANCELLED"},
        {"cancel:WHD_JOB_RECOVERY_REQUIRED", "arm:armed"},
    ), observed
    assert (original.read_bytes(), original.stat().st_mtime_ns) == before
    assert not (directory / "part-two.dxf").exists()


def test_prepare_cancel_during_real_source_prepare_never_commits_a_receipt(
    monkeypatch, tmp_path,
):
    root, _, _ = _root(tmp_path)
    store = tmp_path / "worker"
    store.mkdir()
    led = DurableJobIdentityLedger(store)
    req = _request(count=2)
    import integration_cli.prepare_batch as module
    original = module.prepare_trusted_door_batch

    def cancel_before_receipt(*args, **kwargs):
        actual = original(*args, **kwargs)
        DurableJobIdentityLedger(store).request_cancel(req)
        return actual

    monkeypatch.setattr(module, "prepare_trusted_door_batch", cancel_before_receipt)
    with pytest.raises(PrepareEvidenceError) as exc:
        led.prepare_and_persist(
            req, resource_root=root, engine_commit=COMMIT,
            engine_sha256=ENGINE, build_id="test-only-source", worker_key=KEY,
        )
    assert _code(exc) == "WHD_JOB_CANCELLED"
    with sqlite3.connect(store / "job_identity.sqlite3") as db:
        assert not db.execute("SELECT 1 FROM trusted_prepares").fetchone()
        assert db.execute("SELECT state FROM jobs").fetchone() == ("started",)
    with pytest.raises(PrepareEvidenceError) as exc:
        led.load_trusted_prepare(
            client_installation_id=req["client_installation_id"],
            job_id=req["job_id"], worker_key=KEY,
        )
    assert _code(exc) == "WHD_JOB_RECOVERY_REQUIRED"
