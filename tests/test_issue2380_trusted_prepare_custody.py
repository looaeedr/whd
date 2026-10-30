# -*- coding: utf-8 -*-
"""#2380: W-03 original request+receipt from real WHD, sealed by W-06 durable ledger.

All evidence is private Worker-owned; public W-01 CLI stays disabled.
No customer DXF output is written by these tests.
"""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from integration_cli.job_identity_ledger import DurableJobIdentityLedger
from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.request_canonical import compute_wire_request_digest
from test_issue2378_prepare_batch import (
    COMMIT, ENGINE, KEY, _export_request_from_prepared, _request, _root,
)

BUILD_ID = "test-only-source"


def _run(ledger, request, root, key=KEY):
    return ledger.prepare_and_persist(
        request, resource_root=root, engine_commit=COMMIT,
        engine_sha256=ENGINE, build_id=BUILD_ID, worker_key=key,
    )


def _ledger(tmp_path):
    store = tmp_path / "trusted Worker 本機 狀態"
    store.mkdir()
    return store, DurableJobIdentityLedger(store)


def test_real_two_door_prepare_persist_reopen_and_export_recheck(tmp_path, monkeypatch):
    root, _, _ = _root(tmp_path)
    store, ledger = _ledger(tmp_path)
    original = _request(count=2)
    actual = _run(ledger, original, root)
    assert actual["status"] == "success"
    assert actual["manufacturing_verified"] is False
    assert len(actual["items"]) == 2
    restarted = DurableJobIdentityLedger(store)
    persisted_request, persisted_receipt = restarted.load_trusted_prepare(
        client_installation_id=original["client_installation_id"],
        job_id=original["job_id"], worker_key=KEY,
    )
    assert persisted_request == original
    assert persisted_receipt == actual
    # Transport-only request_id may differ on a timeout retry, but the
    # exact immutable W-03 receipt must be returned without another render.
    retry = deepcopy(original)
    retry["request_id"] = "another-wire-correlation"
    assert compute_wire_request_digest(retry) == original["request_digest"]

    import integration_cli.prepare_batch as prepare_module
    with monkeypatch.context() as m:
        m.setattr(prepare_module, "prepare_trusted_door_batch",
                  lambda *a, **k: pytest.fail("retry rerendered a completed job"))
        assert _run(restarted, retry, root) == actual

    export = _export_request_from_prepared(original, actual)
    req, response = restarted.recheck_persisted_prepare_for_export(
        export, resource_root=root, engine_commit=COMMIT,
        engine_sha256=ENGINE, build_id=BUILD_ID, worker_key=KEY,
    )
    assert req == original and response == actual
    changed = deepcopy(export)
    changed["items"][0]["part"]["dimensions_mm"]["width"] += 1
    changed["request_digest"] = compute_wire_request_digest(changed)
    with pytest.raises(PrepareEvidenceError) as exc:
        restarted.recheck_persisted_prepare_for_export(
            changed, resource_root=root, engine_commit=COMMIT,
            engine_sha256=ENGINE, build_id=BUILD_ID, worker_key=KEY,
        )
    assert exc.value.code == "WHD_PREPARE_STALE"
    assert not list(store.rglob("*.dxf"))


def test_wrong_hmac_key_and_tampered_original_request_fail_closed(tmp_path):
    root, _, _ = _root(tmp_path)
    store, ledger = _ledger(tmp_path)
    original = _request()
    _run(ledger, original, root)
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.load_trusted_prepare(
            client_installation_id=original["client_installation_id"],
            job_id=original["job_id"], worker_key=b"different-trusted-key-" + b"a" * 32,
        )
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"
    with sqlite3.connect(store / "job_identity.sqlite3") as conn:
        payload, = conn.execute("SELECT source_and_receipt_json FROM trusted_prepares").fetchone()
        forged = json.loads(payload)
        forged["original_request"]["items"][0]["part"]["dimensions_mm"]["width"] = 777
        conn.execute(
            "UPDATE trusted_prepares SET source_and_receipt_json=?",
            (json.dumps(forged, ensure_ascii=False, sort_keys=True),),
        )
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.load_trusted_prepare(
            client_installation_id=original["client_installation_id"],
            job_id=original["job_id"], worker_key=KEY,
        )
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"


def test_tampered_result_even_with_recomputed_plain_sha_cannot_be_export_authority(tmp_path):
    import hashlib

    root, _, _ = _root(tmp_path)
    store, ledger = _ledger(tmp_path)
    original = _request()
    result = _run(ledger, original, root)
    forged = deepcopy(result)
    forged["items"][0]["physical_part_id"] = "whd-false-physical-id"
    encoded = json.dumps(forged, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    with sqlite3.connect(store / "job_identity.sqlite3") as conn:
        conn.execute(
            "UPDATE jobs SET result_json=?, result_sha256=? WHERE operation='prepare'",
            (encoded, hashlib.sha256(encoded.encode("utf-8")).hexdigest()),
        )
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.load_trusted_prepare(
            client_installation_id=original["client_installation_id"],
            job_id=original["job_id"], worker_key=KEY,
        )
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"


def test_crashed_unfinished_job_is_never_recomputed(tmp_path, monkeypatch):
    root, _, _ = _root(tmp_path)
    store, ledger = _ledger(tmp_path)
    original = _request()
    assert ledger.claim(original).state == "new"
    # After a simulated hard stop, neither a retry nor an export may treat
    # uncommitted data as authorized. No automatic retry / signing.
    with pytest.raises(PrepareEvidenceError) as exc:
        _run(DurableJobIdentityLedger(store), original, root)
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.load_trusted_prepare(
            client_installation_id=original["client_installation_id"],
            job_id=original["job_id"], worker_key=KEY,
        )
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"


def test_completed_legacy_prepare_job_without_original_record_fails_closed(tmp_path):
    root, _, _ = _root(tmp_path)
    store, ledger = _ledger(tmp_path)
    original = _request()
    # Historical record may have a result, but it did not seal the original
    # prepare request. It cannot be upgraded to export authority.
    ledger.claim(original)
    result = {
        "operation": "prepare", "status": "success",
        "client_installation_id": original["client_installation_id"],
        "job_id": original["job_id"],
        "request_digest": original["request_digest"],
        "manufacturing_verified": False,
    }
    ledger.complete(original, result, trusted_artifacts={})
    with pytest.raises(PrepareEvidenceError) as exc:
        _run(DurableJobIdentityLedger(store), original, root)
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"


def test_missing_worker_key_refuses_even_if_job_was_prepared(tmp_path):
    root, _, _ = _root(tmp_path)
    _, ledger = _ledger(tmp_path)
    request = _request()
    _run(ledger, request, root)
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.load_trusted_prepare(
            client_installation_id=request["client_installation_id"],
            job_id=request["job_id"], worker_key=b"weak",
        )
    assert exc.value.code == "WHD_PREPARE_KEY_UNAVAILABLE"


@pytest.mark.skipif(sys.platform != "win32", reason="requires actual current-user Windows DPAPI")
def test_windows_real_dpapi_key_authenticates_saved_whd_prepare_after_process_restart(tmp_path, monkeypatch):
    """One trusted Worker key, genuine WHD baselines and separate Windows process."""
    from integration_cli.worker_key_custody import load_installation_key

    profile = tmp_path / "專屬 Windows Worker 使用者資料"
    profile.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(profile))
    install_id = "WHD-CAD-trusted-local-install"
    worker_key = load_installation_key(install_id, initialize=True)
    assert len(worker_key) == 32
    root, _, _ = _root(tmp_path)
    store, ledger = _ledger(tmp_path)
    request = _request(count=2)
    receipt = _run(ledger, request, root, key=worker_key)
    assert receipt["status"] == "success"
    assert not list(store.rglob("*.dxf"))
    # The same native OS user must reopen BOTH independently persisted trust
    # owners. Only fixed success/failure text crosses stdout, never the key or
    # a live prepare_token.
    source = (
        "import sys;"
        "from pathlib import Path;"
        "from integration_cli.worker_key_custody import load_installation_key;"
        "from integration_cli.job_identity_ledger import DurableJobIdentityLedger;"
        "key=load_installation_key(sys.argv[2]);"
        "original,receipt=DurableJobIdentityLedger(Path(sys.argv[1])).load_trusted_prepare("
        "client_installation_id=sys.argv[3],job_id=sys.argv[4],worker_key=key);"
        "assert len(original['items'])==len(receipt['items'])==2;"
        "assert receipt['manufacturing_verified'] is False;"
        "print('W06_DPAPI_PREPARE_CROSS_PROCESS_VERIFIED')"
    )
    result = subprocess.run(
        [sys.executable, "-c", source, str(store), install_id,
         request["client_installation_id"], request["job_id"]],
        cwd=Path(__file__).resolve().parents[1], env=os.environ.copy(),
        capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == "W06_DPAPI_PREPARE_CROSS_PROCESS_VERIFIED"
    assert result.stderr == ""
    # A different installation's genuine DPAPI key must not authenticate
    # this first installation's durable record.
    foreign = load_installation_key("other-trusted-install", initialize=True)
    with pytest.raises(PrepareEvidenceError) as exc:
        DurableJobIdentityLedger(store).load_trusted_prepare(
            client_installation_id=request["client_installation_id"],
            job_id=request["job_id"], worker_key=foreign,
        )
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"
