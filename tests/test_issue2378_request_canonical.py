# -*- coding: utf-8 -*-
"""W-03/W-06 RFC8785 transport digest: reject tampering, preserve Unicode."""
from copy import deepcopy
import hashlib
import pytest
import rfc8785

from integration_cli.request_canonical import (
    compute_wire_request_digest, require_matching_wire_request_digest,
)
from integration_cli.prepare_evidence import PrepareEvidenceError


def _request():
    return {
        "protocol_version": "1.0.0",
        "client_installation_id": "CAD-1",
        "request_id": "transport-a",
        "job_id": "job-1",
        "request_digest": "a" * 64,
        "operation": "prepare",
        "coordinate_contract_revision": "1",
        "items": [{
            "item_id": "門一",
            "source_document_sha256": "f" * 64,
            "part": {
                "kind": "door",
                "cabinet_family": "金庫型",
                "source_part_ref": "DXF-來源/門",
                "dimension_semantics": "cabinet_outer",
                "dimensions_mm": {"width": 500, "height": 600.0, "thickness": 2},
            },
        }],
    }


def test_wire_digest_matches_rfc8785_and_excludes_only_transport_fields():
    request = _request()
    expected_payload = {k: v for k, v in request.items()
                        if k not in ("request_id", "request_digest")}
    expected = hashlib.sha256(rfc8785.dumps(expected_payload)).hexdigest()
    assert compute_wire_request_digest(request) == expected
    request["request_digest"] = expected
    assert require_matching_wire_request_digest(request) == expected
    request["request_id"] = "transport-new-after-timeout"
    assert require_matching_wire_request_digest(request) == expected


@pytest.mark.parametrize("field", ["job_id", "items", "client_installation_id",
                                  "operation", "coordinate_contract_revision"])
def test_semantic_rewrite_changes_digest_and_fails_closed(field):
    request = _request()
    request["request_digest"] = compute_wire_request_digest(request)
    edited = deepcopy(request)
    if field == "items":
        edited["items"][0]["part"]["dimensions_mm"]["width"] = 499
    else:
        edited[field] = {
            "job_id": "job-two",
            "client_installation_id": "CAD-2",
            "operation": "export",
            "coordinate_contract_revision": "2",
        }[field]
    with pytest.raises(PrepareEvidenceError) as exc:
        require_matching_wire_request_digest(edited)
    assert exc.value.code == "WHD_REQUEST_DIGEST_MISMATCH"


def test_request_digest_rejects_nonfinite_and_malformed_hash():
    request = _request()
    request["items"][0]["part"]["dimensions_mm"]["width"] = float("nan")
    with pytest.raises(PrepareEvidenceError):
        compute_wire_request_digest(request)
    request = _request()
    request["request_digest"] = "bad"
    with pytest.raises(PrepareEvidenceError) as exc:
        require_matching_wire_request_digest(request)
    assert exc.value.code == "WHD_REQUEST_DIGEST_INVALID"


def test_wire_digest_follows_rfc_numeric_canonicalization():
    one = _request()
    two = deepcopy(one)
    one["items"][0]["part"]["dimensions_mm"]["width"] = 500
    two["items"][0]["part"]["dimensions_mm"]["width"] = 500.0
    assert compute_wire_request_digest(one) == compute_wire_request_digest(two)


# #2380: durable W-06 job identity replay tests live beside canonical RFC8785
# requests, retaining the measured whole-file 18-shard owner.
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import ezdxf
import pytest

from integration_cli.job_identity_ledger import DurableJobIdentityLedger
from integration_cli.original_backup_manifest import DurableOriginalBackupEvidence
from integration_cli.batch_commit_journal import DurableMultiDXFRollbackJournal
from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.request_canonical import compute_wire_request_digest

ROOT = Path(__file__).resolve().parents[1]


def _w06_request(*, operation="prepare", job="job-2378"):
    request = {
        "protocol_version": "1.1.0",
        "client_installation_id": "CAD-install-A",
        "request_id": "wire-001",
        "job_id": job,
        "request_digest": "0" * 64,
        "operation": operation,
        "coordinate_contract_revision": "1",
        "items": [{
            "item_id": "door-1",
            "source_document_sha256": "f" * 64,
            "part": {
                "kind": "door", "cabinet_family": "金庫型",
                "source_part_ref": "real-source-door-1",
                "dimension_semantics": "cabinet_outer",
                "dimensions_mm": {"width": 500, "height": 600, "thickness": 2},
                "frame_edges": {"left": True, "right": True, "top": True, "bottom": True},
            },
        }],
    }
    if operation == "export":
        request["transaction_mode"] = "all_or_nothing"
        request["output"] = {"directory": "trusted-output", "overwrite": False}
    request["request_digest"] = compute_wire_request_digest(request)
    return request


def _w06_result(req):
    return {
        "operation": req["operation"],
        "client_installation_id": req["client_installation_id"],
        "job_id": req["job_id"],
        "status": "success",
        "request_digest": req["request_digest"],
        "manufacturing_verified": False,
    }


def test_private_ledger_restarts_and_replays_same_semantics_without_new_job(tmp_path):
    req = _w06_request()
    store = tmp_path / "trusted-installation-store"
    store.mkdir()
    first = DurableJobIdentityLedger(store)
    assert first.claim(req).state == "new"
    original = _w06_result(req)
    first.complete(req, original, trusted_artifacts={})
    retry = deepcopy(req)
    retry["request_id"] = "another-transport-correlation"
    assert compute_wire_request_digest(retry) == req["request_digest"]
    second = DurableJobIdentityLedger(store)
    replay = second.claim(retry)
    assert replay.state == "committed"
    assert replay.result == original
    assert second.claim(retry).state == "committed"
    assert not any(store.glob("*.dxf"))


@pytest.mark.parametrize("mutation", ["width", "item_id", "overwrite", "part_ref"])
def test_same_job_different_semantic_request_is_conflict(tmp_path, mutation):
    store = tmp_path / "worker-store"
    store.mkdir()
    ledger = DurableJobIdentityLedger(store)
    req = _w06_request(operation="export")
    assert ledger.claim(req).state == "new"
    changed = deepcopy(req)
    if mutation == "width":
        changed["items"][0]["part"]["dimensions_mm"]["width"] = 501
    elif mutation == "item_id":
        changed["items"][0]["item_id"] = "door-replaced"
    elif mutation == "overwrite":
        changed["output"]["overwrite"] = True
    else:
        changed["items"][0]["part"]["source_part_ref"] = "other-source"
    changed["request_digest"] = compute_wire_request_digest(changed)
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.claim(changed)
    assert exc.value.code == "WHD_JOB_ID_CONFLICT"


def test_unfinished_identity_after_restart_never_restarts_manufacturing(tmp_path):
    store = tmp_path / "worker-store"
    store.mkdir()
    req = _w06_request(operation="export")
    assert DurableJobIdentityLedger(store).claim(req).state == "new"
    retry = deepcopy(req)
    retry["request_id"] = "new-network-timeout-correlation"
    with pytest.raises(PrepareEvidenceError) as exc:
        DurableJobIdentityLedger(store).claim(retry)
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"


def test_committed_real_dxf_readback_keeps_bytes_and_mtime_then_detects_tamper(tmp_path):
    store = tmp_path / "worker-store"
    store.mkdir()
    output = tmp_path / "actual-output.dxf"
    doc = ezdxf.new()
    doc.modelspace().add_circle((10.0, 20.0), radius=3.0, dxfattribs={"layer": "CUTTING"})
    doc.saveas(output)
    assert len(ezdxf.readfile(output).modelspace().query("CIRCLE")) == 1
    before = (output.stat().st_mtime_ns, output.read_bytes())
    req = _w06_request(operation="export")
    ledger = DurableJobIdentityLedger(store)
    ledger.claim(req)
    ledger.reserve_output_directories(req, trusted_directories=[output.parent])
    receipt = _w06_result(req)
    ledger.complete(req, receipt, trusted_artifacts={"whd-part-one": output})
    assert DurableJobIdentityLedger(store).claim(req).result == receipt
    assert (output.stat().st_mtime_ns, output.read_bytes()) == before
    output.write_bytes(output.read_bytes() + b"\n999\nWHD-tamper")
    with pytest.raises(PrepareEvidenceError) as exc:
        DurableJobIdentityLedger(store).claim(req)
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"


def test_completed_export_missing_output_refuses_success_readback(tmp_path):
    store = tmp_path / "worker-store"
    store.mkdir()
    output = tmp_path / "actual-output.dxf"
    doc = ezdxf.new()
    doc.modelspace().add_circle((0, 0), radius=2, dxfattribs={"layer": "CUTTING"})
    doc.saveas(output)
    req = _w06_request(operation="export")
    ledger = DurableJobIdentityLedger(store)
    ledger.claim(req)
    ledger.reserve_output_directories(req, trusted_directories=[output.parent])
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.complete(req, _w06_result(req), trusted_artifacts={})
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"
    ledger.complete(req, _w06_result(req), trusted_artifacts={"part": output})
    output.unlink()
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.claim(req)
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"


def test_same_job_parallel_claims_have_one_winner_and_no_second_run(tmp_path):
    store = tmp_path / "worker-store"
    store.mkdir()
    req = _w06_request()
    DurableJobIdentityLedger(store)  # initial schema installed before race

    def claim_once(_):
        try:
            return DurableJobIdentityLedger(store).claim(req).state
        except PrepareEvidenceError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(claim_once, range(6)))
    assert results.count("new") == 1
    assert results.count("WHD_JOB_RECOVERY_REQUIRED") == 5


def test_cross_process_reopen_recovers_exact_persisted_identity(tmp_path):
    store = tmp_path / "worker-store"
    store.mkdir()
    req = _w06_request()
    ledger = DurableJobIdentityLedger(store)
    assert ledger.claim(req).state == "new"
    ledger.complete(req, _w06_result(req), trusted_artifacts={})
    code = (
        "import sys, json;"
        "from pathlib import Path;"
        "from integration_cli.job_identity_ledger import DurableJobIdentityLedger;"
        "print(DurableJobIdentityLedger(Path(sys.argv[1])).claim(json.loads(sys.argv[2])).state)"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code, str(store), json.dumps(req, ensure_ascii=False)],
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=20,
    )
    assert proc.stdout.strip() == "committed"


def test_reject_mismatched_digest_and_store_symlink_before_job_record(tmp_path):
    store = tmp_path / "worker-store"
    store.mkdir()
    ledger = DurableJobIdentityLedger(store)
    req = _w06_request()
    req["items"][0]["part"]["dimensions_mm"]["width"] += 1
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.claim(req)
    assert exc.value.code == "WHD_REQUEST_DIGEST_MISMATCH"
    assert not list(store.glob("*.dxf"))
    alias = tmp_path / "worker-store-alias"
    try:
        alias.symlink_to(store, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("filesystem does not support symlinks")
    with pytest.raises(PrepareEvidenceError) as exc:
        DurableJobIdentityLedger(alias)
    assert exc.value.code == "WHD_JOB_STORE_UNAVAILABLE"


def test_operation_is_part_of_durable_identity(tmp_path):
    store = tmp_path / "worker-store"
    store.mkdir()
    ledger = DurableJobIdentityLedger(store)
    assert ledger.claim(_w06_request(operation="prepare")).state == "new"
    assert ledger.claim(_w06_request(operation="export")).state == "new"


def _w06_real_output(path):
    scene = ezdxf.new()
    scene.modelspace().add_circle((12, 22), radius=3.5, dxfattribs={"layer": "CUTTING"})
    scene.saveas(path)
    assert len(ezdxf.readfile(path).modelspace().query("CIRCLE")) == 1
    return path


def test_cross_job_same_directory_lease_survives_restart_and_only_complete_releases(tmp_path):
    store = tmp_path / "worker-store"
    store.mkdir()
    output_dir = tmp_path / "actual-outputs"
    output_dir.mkdir()
    first = _w06_request(operation="export", job="job-first")
    second = _w06_request(operation="export", job="job-second")
    ledger = DurableJobIdentityLedger(store)
    assert ledger.claim(first).state == "new"
    assert ledger.claim(second).state == "new"
    key, = ledger.reserve_output_directories(first, trusted_directories=[output_dir])
    assert key
    with pytest.raises(PrepareEvidenceError) as exc:
        DurableJobIdentityLedger(store).reserve_output_directories(
            second, trusted_directories=[output_dir]
        )
    assert exc.value.code == "WHD_OUTPUT_PATH_LOCKED"
    # An interrupted first job has no right to release the lease on restart.
    with pytest.raises(PrepareEvidenceError) as exc:
        DurableJobIdentityLedger(store).claim(first)
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"
    output = _w06_real_output(output_dir / "first.dxf")
    ledger.complete(first, _w06_result(first), trusted_artifacts={"first": output})
    assert DurableJobIdentityLedger(store).claim(first).state == "committed"
    assert DurableJobIdentityLedger(store).reserve_output_directories(
        second, trusted_directories=[output_dir]
    ) == (key,)


def test_multi_destination_reservation_is_all_or_none_even_on_conflict(tmp_path):
    store = tmp_path / "worker-store"
    store.mkdir()
    output_a = tmp_path / "a"
    output_b = tmp_path / "b"
    output_a.mkdir()
    output_b.mkdir()
    first = _w06_request(operation="export", job="first-job")
    second = _w06_request(operation="export", job="second-job")
    third = _w06_request(operation="export", job="third-job")
    ledger = DurableJobIdentityLedger(store)
    for req in (first, second, third):
        assert ledger.claim(req).state == "new"
    ledger.reserve_output_directories(first, trusted_directories=[output_b])
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.reserve_output_directories(
            second, trusted_directories=[output_b, output_a]
        )
    assert exc.value.code == "WHD_OUTPUT_PATH_LOCKED"
    # A was NOT kept by second when B conflicted.
    assert len(ledger.reserve_output_directories(
        third, trusted_directories=[output_a]
    )) == 1
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.reserve_output_directories(
            second, trusted_directories=[output_a]
        )
    assert exc.value.code == "WHD_OUTPUT_PATH_LOCKED"


def test_export_completion_without_exclusive_destination_lease_fails_closed(tmp_path):
    store = tmp_path / "worker-store"
    store.mkdir()
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    req = _w06_request(operation="export")
    ledger = DurableJobIdentityLedger(store)
    ledger.claim(req)
    output = _w06_real_output(output_dir / "actual.dxf")
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.complete(req, _w06_result(req), trusted_artifacts={"part": output})
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"
    ledger.reserve_output_directories(req, trusted_directories=[output_dir])
    ledger.complete(req, _w06_result(req), trusted_artifacts={"part": output})


def test_output_directory_lease_rejects_relative_missing_duplicate_and_symlink(tmp_path):
    store = tmp_path / "worker-store"
    store.mkdir()
    output = tmp_path / "real"
    output.mkdir()
    req = _w06_request(operation="export")
    ledger = DurableJobIdentityLedger(store)
    ledger.claim(req)
    invalid = ([Path("relative-directory")], [tmp_path / "missing"], [output, output])
    for dirs in invalid:
        with pytest.raises(PrepareEvidenceError) as exc:
            ledger.reserve_output_directories(req, trusted_directories=dirs)
        assert exc.value.code == "WHD_OUTPUT_PATH_INVALID"
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(output, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("filesystem symlinks unavailable")
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.reserve_output_directories(req, trusted_directories=[alias])
    assert exc.value.code == "WHD_OUTPUT_PATH_INVALID"


def test_two_different_jobs_racing_one_directory_have_exactly_one_lease(tmp_path):
    store = tmp_path / "worker-store"
    store.mkdir()
    target = tmp_path / "output"
    target.mkdir()
    ledger = DurableJobIdentityLedger(store)
    requests = [_w06_request(operation="export", job=f"job-{i}") for i in range(8)]
    for request in requests:
        assert ledger.claim(request).state == "new"

    def reserve(request):
        try:
            DurableJobIdentityLedger(store).reserve_output_directories(
                request, trusted_directories=[target]
            )
            return "winner"
        except PrepareEvidenceError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(reserve, requests))
    assert results.count("winner") == 1
    assert results.count("WHD_OUTPUT_PATH_LOCKED") == 7


def test_export_artifact_outside_reserved_output_directory_cannot_be_committed(tmp_path):
    store = tmp_path / "worker-store"
    store.mkdir()
    reserved = tmp_path / "reserved"
    elsewhere = tmp_path / "elsewhere"
    reserved.mkdir()
    elsewhere.mkdir()
    req = _w06_request(operation="export")
    ledger = DurableJobIdentityLedger(store)
    ledger.claim(req)
    ledger.reserve_output_directories(req, trusted_directories=[reserved])
    outside = _w06_real_output(elsewhere / "wrong-output.dxf")
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.complete(req, _w06_result(req), trusted_artifacts={"part": outside})
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"
    # The rejected completion must neither publish a result nor drop A's
    # durable lock; a different job still cannot take over the target.
    other = _w06_request(operation="export", job="other-job")
    ledger.claim(other)
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.reserve_output_directories(other, trusted_directories=[reserved])
    assert exc.value.code == "WHD_OUTPUT_PATH_LOCKED"


def test_replaced_directory_at_same_path_cannot_complete_or_take_over_lease(tmp_path):
    """The lexical destination stays identical while its physical inode changes."""
    store = tmp_path / "worker-store"
    store.mkdir()
    owned = tmp_path / "customer-output"
    moved = tmp_path / "moved-original-output"
    owned.mkdir()
    request = _w06_request(operation="export", job="job-original")
    ledger = DurableJobIdentityLedger(store)
    assert ledger.claim(request).state == "new"
    original_keys = ledger.reserve_output_directories(
        request, trusted_directories=[owned]
    )
    assert len(original_keys) == 1
    owned.rename(moved)
    owned.mkdir()  # same string path, different original directory
    output = _w06_real_output(owned / "unexpected-new-inode.dxf")
    with pytest.raises(PrepareEvidenceError) as exc:
        DurableJobIdentityLedger(store).complete(
            request, _w06_result(request), trusted_artifacts={"part": output},
        )
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.reserve_output_directories(request, trusted_directories=[owned])
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"
    competing = _w06_request(operation="export", job="job-other")
    assert ledger.claim(competing).state == "new"
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.reserve_output_directories(competing, trusted_directories=[owned])
    assert exc.value.code == "WHD_OUTPUT_PATH_LOCKED"
    assert output.exists(), "refusal must not mutate untrusted new customer files"


def test_existing_unattested_lease_from_older_database_fails_closed(tmp_path):
    """Schema additions must not grandfather a path-only lease as certified."""
    import sqlite3
    store = tmp_path / "worker-store"
    store.mkdir()
    destination = tmp_path / "customer-output"
    destination.mkdir()
    request = _w06_request(operation="export")
    ledger = DurableJobIdentityLedger(store)
    ledger.claim(request)
    keys = ledger.reserve_output_directories(request, trusted_directories=[destination])
    with sqlite3.connect(store / "job_identity.sqlite3") as conn:
        conn.execute(
            "DELETE FROM output_directory_identity WHERE directory_key=?", (keys[0],)
        )
    with pytest.raises(PrepareEvidenceError) as exc:
        DurableJobIdentityLedger(store).reserve_output_directories(
            request, trusted_directories=[destination]
        )
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"
    output = _w06_real_output(destination / "customer.dxf")
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.complete(
            request, _w06_result(request), trusted_artifacts={"part": output},
        )
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"

# #2380 W-06: private, read-only durable precommit evidence, NOT a DXF
# replacement/rollback journal or public Worker manufacturing authorization.
def _w06_staged_dxf(output_dir, physical_id):
    stage_dir = output_dir / ".whd-dxf-stage-verified"
    stage_dir.mkdir(exist_ok=True)
    return _w06_real_output(stage_dir / f"{physical_id}.dxf")


def test_durable_precommit_two_real_dxf_and_original_output_untouched(tmp_path):
    store = tmp_path / "worker-store"
    store.mkdir()
    output = tmp_path / "customer-output"
    output.mkdir()
    old = _w06_real_output(output / "part-one.dxf")
    previous = (old.read_bytes(), old.stat().st_mtime_ns)
    stage_one = _w06_staged_dxf(output, "part-one")
    stage_two = _w06_staged_dxf(output, "part-two")
    assert len(ezdxf.readfile(stage_two).modelspace().query("CIRCLE")) == 1
    request = _w06_request(operation="export")
    request["output"]["overwrite"] = True
    request["request_digest"] = compute_wire_request_digest(request)
    ledger = DurableJobIdentityLedger(store)
    assert ledger.claim(request).state == "new"
    ledger.reserve_output_directories(request, trusted_directories=[output])
    inventory = {"part-one": stage_one, "part-two": stage_two}
    snapshot = ledger.record_staged_batch_snapshot(
        request, trusted_output_dir=output, trusted_staged=inventory, overwrite=True
    )
    assert len(snapshot["items"]) == 2
    assert [r["physical_id"] for r in snapshot["items"]] == ["part-one", "part-two"]
    retry = deepcopy(request)
    retry["request_id"] = "another-transport-request"
    assert DurableJobIdentityLedger(store).require_staged_batch_snapshot_current(retry) == snapshot
    assert ledger.record_staged_batch_snapshot(
        retry, trusted_output_dir=output, trusted_staged=inventory, overwrite=True
    ) == snapshot
    assert (old.read_bytes(), old.stat().st_mtime_ns) == previous
    assert not (output / "part-two.dxf").exists()
    # Stage snapshot MUST NOT be accepted as a multi-file committed result.
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.complete(request, _w06_result(request), trusted_artifacts={"part-one": old})
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"
    second = _w06_request(operation="export", job="other-export")
    ledger.claim(second)
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.reserve_output_directories(second, trusted_directories=[output])
    assert exc.value.code == "WHD_OUTPUT_PATH_LOCKED"


@pytest.mark.parametrize("mutation", ["stage_bytes", "stage_removed", "customer_bytes", "customer_removed"])
def test_durable_precommit_never_trusts_changed_staged_or_existing_dxf(tmp_path, mutation):
    store = tmp_path / "worker-store"
    store.mkdir()
    output = tmp_path / "customer-output"
    output.mkdir()
    original = _w06_real_output(output / "part-one.dxf")
    stage = _w06_staged_dxf(output, "part-one")
    req = _w06_request(operation="export")
    req["output"]["overwrite"] = True
    req["request_digest"] = compute_wire_request_digest(req)
    ledger = DurableJobIdentityLedger(store)
    ledger.claim(req)
    ledger.reserve_output_directories(req, trusted_directories=[output])
    ledger.record_staged_batch_snapshot(
        req, trusted_output_dir=output, trusted_staged={"part-one": stage}, overwrite=True
    )
    if mutation == "stage_bytes":
        stage.write_bytes(stage.read_bytes() + b"\n999\nchanged-stage")
    elif mutation == "stage_removed":
        stage.unlink()
    elif mutation == "customer_bytes":
        original.write_bytes(original.read_bytes() + b"\n999\nchanged-customer")
    else:
        original.unlink()
    with pytest.raises(PrepareEvidenceError) as exc:
        DurableJobIdentityLedger(store).require_staged_batch_snapshot_current(req)
    assert exc.value.code == "WHD_JOB_STAGING_STALE"


def test_durable_precommit_rejects_missing_lease_and_wrong_overwrite(tmp_path):
    store = tmp_path / "worker-store"
    store.mkdir()
    target = tmp_path / "output"
    target.mkdir()
    stage = _w06_staged_dxf(target, "part")
    req = _w06_request(operation="export")
    ledger = DurableJobIdentityLedger(store)
    ledger.claim(req)
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.record_staged_batch_snapshot(
            req, trusted_output_dir=target, trusted_staged={"part": stage}, overwrite=False
        )
    assert exc.value.code == "WHD_OUTPUT_PATH_LOCKED"
    ledger.reserve_output_directories(req, trusted_directories=[target])
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.record_staged_batch_snapshot(
            req, trusted_output_dir=target, trusted_staged={"part": stage}, overwrite=True
        )
    assert exc.value.code == "WHD_JOB_STAGING_INVALID"
    customer = _w06_real_output(target / "part.dxf")
    previous = (customer.read_bytes(), customer.stat().st_mtime_ns)
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.record_staged_batch_snapshot(
            req, trusted_output_dir=target, trusted_staged={"part": stage}, overwrite=False
        )
    assert exc.value.code == "WHD_JOB_STAGING_INVALID"
    assert (customer.read_bytes(), customer.stat().st_mtime_ns) == previous


def test_durable_precommit_rejects_unowned_stage_and_changed_physical_inventory(tmp_path):
    store = tmp_path / "worker-store"
    store.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    stage = _w06_staged_dxf(output, "part-one")
    req = _w06_request(operation="export")
    ledger = DurableJobIdentityLedger(store)
    ledger.claim(req)
    ledger.reserve_output_directories(req, trusted_directories=[output])
    outside = _w06_real_output(tmp_path / "part-one.dxf")
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.record_staged_batch_snapshot(
            req, trusted_output_dir=output, trusted_staged={"part-one": outside}, overwrite=False
        )
    assert exc.value.code == "WHD_JOB_STAGING_INVALID"
    ledger.record_staged_batch_snapshot(
        req, trusted_output_dir=output, trusted_staged={"part-one": stage}, overwrite=False
    )
    extra = _w06_staged_dxf(output, "part-two")
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.record_staged_batch_snapshot(
            req, trusted_output_dir=output,
            trusted_staged={"part-one": stage, "part-two": extra}, overwrite=False
        )
    assert exc.value.code == "WHD_JOB_STAGING_STALE"


def test_durable_precommit_persists_across_separate_python_process(tmp_path):
    store = tmp_path / "worker-store"
    store.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    stage = _w06_staged_dxf(output, "part-one")
    req = _w06_request(operation="export")
    ledger = DurableJobIdentityLedger(store)
    ledger.claim(req)
    ledger.reserve_output_directories(req, trusted_directories=[output])
    ledger.record_staged_batch_snapshot(
        req, trusted_output_dir=output, trusted_staged={"part-one": stage}, overwrite=False
    )
    code = (
        "import sys,json;"
        "from pathlib import Path;"
        "from integration_cli.job_identity_ledger import DurableJobIdentityLedger;"
        "print(len(DurableJobIdentityLedger(Path(sys.argv[1]))."
        "require_staged_batch_snapshot_current(json.loads(sys.argv[2]))['items']))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code, str(store), json.dumps(req, ensure_ascii=False)],
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=20,
    )
    assert proc.stdout.strip() == "1"


def test_durable_precommit_rejects_staged_hardlink_to_customer_original(tmp_path):
    store = tmp_path / "worker-store"
    store.mkdir()
    target = tmp_path / "customer"
    target.mkdir()
    original = _w06_real_output(target / "part-one.dxf")
    stage_dir = target / ".whd-dxf-stage-owner"
    stage_dir.mkdir()
    alias = stage_dir / "part-one.dxf"
    try:
        alias.hardlink_to(original)
    except (OSError, NotImplementedError):
        pytest.skip("hard links are unavailable")
    req = _w06_request(operation="export")
    req["output"]["overwrite"] = True
    req["request_digest"] = compute_wire_request_digest(req)
    ledger = DurableJobIdentityLedger(store)
    ledger.claim(req)
    ledger.reserve_output_directories(req, trusted_directories=[target])
    original_bytes, mtime = original.read_bytes(), original.stat().st_mtime_ns
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.record_staged_batch_snapshot(
            req, trusted_output_dir=target,
            trusted_staged={"part-one": alias}, overwrite=True
        )
    assert exc.value.code == "WHD_JOB_STAGING_INVALID"
    assert (original.read_bytes(), original.stat().st_mtime_ns) == (original_bytes, mtime)


def test_durable_precommit_rejects_corrupted_disk_journal_before_any_output_change(tmp_path):
    import sqlite3

    store = tmp_path / "worker-store"
    store.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    stage = _w06_staged_dxf(output, "part-one")
    req = _w06_request(operation="export")
    ledger = DurableJobIdentityLedger(store)
    ledger.claim(req)
    ledger.reserve_output_directories(req, trusted_directories=[output])
    ledger.record_staged_batch_snapshot(
        req, trusted_output_dir=output, trusted_staged={"part-one": stage},
        overwrite=False,
    )
    before = stage.read_bytes(), stage.stat().st_mtime_ns
    with sqlite3.connect(store / "job_identity.sqlite3") as conn:
        conn.execute(
            "UPDATE staged_batch_snapshots SET snapshot_json='{}' WHERE job_id=?",
            (req["job_id"],),
        )
    with pytest.raises(PrepareEvidenceError) as exc:
        DurableJobIdentityLedger(store).require_staged_batch_snapshot_current(req)
    assert exc.value.code == "WHD_JOB_STAGING_STALE"
    assert (stage.read_bytes(), stage.stat().st_mtime_ns) == before
    assert not (output / "part-one.dxf").exists()


def test_precommit_rejects_replaced_physical_directory_under_existing_lease(tmp_path):
    store = tmp_path / "worker-store"
    store.mkdir()
    target = tmp_path / "customer-output"
    target.mkdir()
    saved = tmp_path / "moved-original-dir"
    req = _w06_request(operation="export")
    ledger = DurableJobIdentityLedger(store)
    ledger.claim(req)
    ledger.reserve_output_directories(req, trusted_directories=[target])
    target.rename(saved)
    target.mkdir()
    staged = _w06_staged_dxf(target, "part-one")
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.record_staged_batch_snapshot(
            req, trusted_output_dir=target, trusted_staged={"part-one": staged}, overwrite=False
        )
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"
    assert not (target / "part-one.dxf").exists()


# #2380 private original-file backup evidence (NOT W-06 rollback/commit).
def _w06_backup_context(tmp_path):
    store = tmp_path / "worker-store"
    store.mkdir()
    target = tmp_path / "customer-output"
    target.mkdir()
    old = _w06_real_output(target / "part-one.dxf")
    first = _w06_staged_dxf(target, "part-one")
    second = _w06_staged_dxf(target, "part-two")
    req = _w06_request(operation="export")
    req["output"]["overwrite"] = True
    req["request_digest"] = compute_wire_request_digest(req)
    ledger = DurableJobIdentityLedger(store)
    assert ledger.claim(req).state == "new"
    ledger.reserve_output_directories(req, trusted_directories=[target])
    ledger.record_staged_batch_snapshot(
        req, trusted_output_dir=target,
        trusted_staged={"part-one": first, "part-two": second}, overwrite=True,
    )
    return store, target, old, first, second, req, ledger


def test_original_backup_manifest_retains_real_dxf_old_bytes_mtime_and_replays(tmp_path):
    store, target, old, first, second, req, ledger = _w06_backup_context(tmp_path)
    before = old.read_bytes(), old.stat().st_mtime_ns
    prior_stages = first.read_bytes(), second.read_bytes()
    backups = DurableOriginalBackupEvidence(ledger)
    manifest = backups.create_verified_original_backups(req, trusted_output_dir=target)
    assert list(manifest["backups"]) == ["part-one"]
    backup = Path(manifest["backups"]["part-one"]["path"])
    assert backup.parent.parent == target
    assert backup.stat().st_dev == target.stat().st_dev
    assert len(ezdxf.readfile(backup).modelspace().query("CIRCLE")) == 1
    assert (backup.read_bytes(), backup.stat().st_mtime_ns) == before
    assert (old.read_bytes(), old.stat().st_mtime_ns) == before
    assert (first.read_bytes(), second.read_bytes()) == prior_stages
    assert not (target / "part-two.dxf").exists()
    retry = deepcopy(req)
    retry["request_id"] = "transport-retry-only"
    assert DurableOriginalBackupEvidence(DurableJobIdentityLedger(store)).require_current(retry) == manifest
    assert backups.create_verified_original_backups(retry, trusted_output_dir=target) == manifest
    assert (backup.read_bytes(), backup.stat().st_mtime_ns) == before
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.complete(req, _w06_result(req), trusted_artifacts={"part-one": old})
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"


@pytest.mark.parametrize("mutation", ["backup_bytes", "backup_missing", "old_bytes", "old_missing"])
def test_private_backup_refuses_changed_or_missing_original_or_backup(tmp_path, mutation):
    store, target, old, _, _, req, ledger = _w06_backup_context(tmp_path)
    owner = DurableOriginalBackupEvidence(ledger)
    record = owner.create_verified_original_backups(req, trusted_output_dir=target)
    backup = Path(record["backups"]["part-one"]["path"])
    if mutation == "backup_bytes":
        backup.write_bytes(backup.read_bytes() + b"\n999\ncorrupted-backup")
    elif mutation == "backup_missing":
        backup.unlink()
    elif mutation == "old_bytes":
        old.write_bytes(old.read_bytes() + b"\n999\ncorrupted-old")
    else:
        old.unlink()
    with pytest.raises(PrepareEvidenceError) as exc:
        DurableOriginalBackupEvidence(DurableJobIdentityLedger(store)).require_current(req)
    assert exc.value.code in ("WHD_JOB_RECOVERY_REQUIRED", "WHD_JOB_STAGING_STALE")
    assert not (target / "part-two.dxf").exists()


def test_private_original_backup_manifest_refuses_sqlite_tamper(tmp_path):
    import sqlite3
    store, target, old, _, _, req, ledger = _w06_backup_context(tmp_path)
    before = old.read_bytes(), old.stat().st_mtime_ns
    owner = DurableOriginalBackupEvidence(ledger)
    owner.create_verified_original_backups(req, trusted_output_dir=target)
    with sqlite3.connect(store / "job_identity.sqlite3") as conn:
        conn.execute(
            "UPDATE original_backup_manifests SET manifest_json='{}' WHERE job_id=?",
            (req["job_id"],),
        )
    with pytest.raises(PrepareEvidenceError) as exc:
        DurableOriginalBackupEvidence(DurableJobIdentityLedger(store)).require_current(req)
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"
    assert (old.read_bytes(), old.stat().st_mtime_ns) == before


def test_private_original_backup_manifest_reopens_in_second_process(tmp_path):
    store, target, old, _, _, req, ledger = _w06_backup_context(tmp_path)
    owner = DurableOriginalBackupEvidence(ledger)
    owner.create_verified_original_backups(req, trusted_output_dir=target)
    command = (
        "import sys,json;"
        "from pathlib import Path;"
        "from integration_cli.job_identity_ledger import DurableJobIdentityLedger;"
        "from integration_cli.original_backup_manifest import DurableOriginalBackupEvidence;"
        "w=DurableOriginalBackupEvidence(DurableJobIdentityLedger(Path(sys.argv[1])));"
        "print(len(w.require_current(json.loads(sys.argv[2]))['backups']))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", command, str(store), json.dumps(req, ensure_ascii=False)],
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=20,
    )
    assert proc.stdout.strip() == "1"
    assert old.exists()


def test_private_original_backup_refuses_customer_mutation_before_first_copy(tmp_path):
    store, target, old, _, _, req, ledger = _w06_backup_context(tmp_path)
    old.write_bytes(old.read_bytes() + b"\n999\nchanged-before-backup")
    with pytest.raises(PrepareEvidenceError) as exc:
        DurableOriginalBackupEvidence(ledger).create_verified_original_backups(
            req, trusted_output_dir=target
        )
    assert exc.value.code in ("WHD_JOB_RECOVERY_REQUIRED", "WHD_JOB_STAGING_STALE")
    assert not list(target.glob(".whd-w06-original-backup-*"))
    assert not (target / "part-two.dxf").exists()


def test_private_original_backup_can_attest_no_prior_customer_file_without_creating_one(tmp_path):
    store = tmp_path / "worker-store"
    store.mkdir()
    target = tmp_path / "customer-output"
    target.mkdir()
    stage = _w06_staged_dxf(target, "part-one")
    req = _w06_request(operation="export")
    ledger = DurableJobIdentityLedger(store)
    ledger.claim(req)
    ledger.reserve_output_directories(req, trusted_directories=[target])
    ledger.record_staged_batch_snapshot(
        req, trusted_output_dir=target, trusted_staged={"part-one": stage}, overwrite=False
    )
    manifest = DurableOriginalBackupEvidence(ledger).create_verified_original_backups(
        req, trusted_output_dir=target
    )
    assert manifest["backups"] == {}
    assert DurableOriginalBackupEvidence(DurableJobIdentityLedger(store)).require_current(req) == manifest
    assert not (target / "part-one.dxf").exists()
    assert len(ezdxf.readfile(stage).modelspace().query("CIRCLE")) == 1


# #2380 private two-DXF durable replacement and crash rollback (not public W-01).
def _w06_committing_context(tmp_path):
    store, root, old, stage1, stage2, req, ledger = _w06_backup_context(tmp_path)
    original = old.read_bytes(), old.stat().st_mtime_ns
    DurableOriginalBackupEvidence(ledger).create_verified_original_backups(
        req, trusted_output_dir=root
    )
    journal = DurableMultiDXFRollbackJournal(ledger)
    return store, root, old, stage1, stage2, req, ledger, journal, original


def test_private_rollback_requires_writable_private_temp_file(tmp_path, monkeypatch):
    """Assert the private restore temp uses a writable fsync handle.

    A Linux-only happy path would silently accept the historical read-only
    open("rb"), while Windows CRT _commit refuses it. Track the mode even
    on Linux; ordinary read-only SHA proof reads must remain permitted.
    """
    store, root, old, _, _, req, _, journal, before = _w06_committing_context(tmp_path)
    journal.arm(req)
    with pytest.raises(SystemExit):
        journal.apply(
            req, after_replace=lambda n: (_ for _ in ()).throw(SystemExit()) if n == 1 else None,
        )
    original_open = Path.open
    observed_modes = []

    def track_restore_fsync_open(path, mode="r", *args, **kwargs):
        if path.name.startswith(".whd-w06-restore-") and mode == "rb+":
            observed_modes.append(mode)
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", track_restore_fsync_open)
    recovered = DurableMultiDXFRollbackJournal(DurableJobIdentityLedger(store))
    assert recovered.recover_rollback(req) == "rolled_back"
    assert observed_modes == ["rb+"]
    assert (old.read_bytes(), old.stat().st_mtime_ns) == before
    assert not (root / "part-two.dxf").exists()


def test_private_multidxf_real_save_reload_commit_receipt_and_lease_release(tmp_path):
    store, root, old, stage1, stage2, req, ledger, journal, original = _w06_committing_context(tmp_path)
    plan = journal.arm(req)
    assert len(plan["items"]) == 2
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.complete(req, _w06_result(req), trusted_artifacts={"part-one": old})
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"
    outputs = journal.apply(req)
    assert journal._read(req)[0] == "applied"
    assert set(outputs) == {"part-one", "part-two"}
    assert all(len(ezdxf.readfile(p).modelspace().query("CIRCLE")) == 1 for p in outputs.values())
    assert not stage1.exists() and not stage2.exists()
    ledger.complete(req, _w06_result(req), trusted_artifacts=outputs)
    assert journal._read(req)[0] == "committed"
    retry = deepcopy(req)
    retry["request_id"] = "transport-new-after-commit"
    assert DurableJobIdentityLedger(store).claim(retry).state == "committed"
    with pytest.raises(PrepareEvidenceError):
        journal.recover_rollback(req)
    other = _w06_request(operation="export", job="another-export")
    assert ledger.claim(other).state == "new"
    assert ledger.reserve_output_directories(other, trusted_directories=[root])
    immutable = Path(plan["items"][0]["backup"]["path"])
    assert (immutable.read_bytes(), immutable.stat().st_mtime_ns) == original


@pytest.mark.parametrize("interrupt_after", [1, 2])
def test_private_multidxf_hard_stop_between_renames_rolls_back_after_restart(
    tmp_path, interrupt_after,
):
    store, root, old, first, second, req, ledger, journal, original = _w06_committing_context(tmp_path)
    journal.arm(req)
    def hard_stop(n):
        if n == interrupt_after:
            raise SystemExit("emulated power loss")
    with pytest.raises(SystemExit):
        journal.apply(req, after_replace=hard_stop)
    assert journal._read(req)[0] == "applying"
    with pytest.raises(PrepareEvidenceError) as exc:
        DurableJobIdentityLedger(store).claim(req)
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"
    contender = _w06_request(operation="export", job="another-job")
    ledger.claim(contender)
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.reserve_output_directories(contender, trusted_directories=[root])
    assert exc.value.code == "WHD_OUTPUT_PATH_LOCKED"
    recovered = DurableMultiDXFRollbackJournal(DurableJobIdentityLedger(store))
    assert recovered.recover_rollback(req) == "rolled_back"
    assert recovered.recover_rollback(req) == "rolled_back"
    assert (old.read_bytes(), old.stat().st_mtime_ns) == original
    assert not (root / "part-two.dxf").exists()
    assert DurableJobIdentityLedger(store).claim(req).state == "rolled_back"
    assert ledger.reserve_output_directories(contender, trusted_directories=[root])


def test_private_multidxf_modified_customer_file_blocks_unsafe_rollback(tmp_path):
    store, root, old, _, _, req, ledger, journal, _ = _w06_committing_context(tmp_path)
    journal.arm(req)
    def stop(_):
        raise SystemExit("stop")
    with pytest.raises(SystemExit):
        journal.apply(req, after_replace=stop)
    old.write_bytes(old.read_bytes() + b"\n999\nthird-party-modified")
    altered = old.read_bytes(), old.stat().st_mtime_ns
    with pytest.raises(PrepareEvidenceError) as exc:
        DurableMultiDXFRollbackJournal(DurableJobIdentityLedger(store)).recover_rollback(req)
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"
    assert (old.read_bytes(), old.stat().st_mtime_ns) == altered
    other = _w06_request(operation="export", job="other-job")
    ledger.claim(other)
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.reserve_output_directories(other, trusted_directories=[root])
    assert exc.value.code == "WHD_OUTPUT_PATH_LOCKED"


def test_private_multidxf_corrupted_original_backup_blocks_rollback(tmp_path):
    store, root, old, _, _, req, _, journal, _ = _w06_committing_context(tmp_path)
    plan = journal.arm(req)
    with pytest.raises(SystemExit):
        journal.apply(req, after_replace=lambda _: (_ for _ in ()).throw(SystemExit()))
    backup = Path(plan["items"][0]["backup"]["path"])
    backup.write_bytes(backup.read_bytes() + b"\n999\ncorrupted")
    with pytest.raises(PrepareEvidenceError) as exc:
        DurableMultiDXFRollbackJournal(DurableJobIdentityLedger(store)).recover_rollback(req)
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"
    assert old.exists()


def test_private_multidxf_armed_without_replacement_can_rollback_unchanged(tmp_path):
    store, root, old, first, second, req, _, journal, previous = _w06_committing_context(tmp_path)
    journal.arm(req)
    assert journal.recover_rollback(req) == "rolled_back"
    assert (old.read_bytes(), old.stat().st_mtime_ns) == previous
    assert first.exists() and second.exists()
    assert not (root / "part-two.dxf").exists()
    assert DurableJobIdentityLedger(store).claim(req).state == "rolled_back"


def test_private_multidxf_digest_collision_and_sqlite_journal_corruption_refuse(tmp_path):
    import sqlite3
    store, root, old, _, _, req, _, journal, previous = _w06_committing_context(tmp_path)
    journal.arm(req)
    changed = deepcopy(req)
    changed["items"][0]["part"]["dimensions_mm"]["width"] += 1
    changed["request_digest"] = compute_wire_request_digest(changed)
    with pytest.raises(PrepareEvidenceError) as exc:
        journal.apply(changed)
    assert exc.value.code == "WHD_JOB_ID_CONFLICT"
    with sqlite3.connect(store / "job_identity.sqlite3") as conn:
        conn.execute("UPDATE batch_replace_journals SET plan_json='{}' WHERE job_id=?", (req["job_id"],))
    with pytest.raises(PrepareEvidenceError) as exc:
        DurableMultiDXFRollbackJournal(DurableJobIdentityLedger(store)).apply(req)
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"
    assert (old.read_bytes(), old.stat().st_mtime_ns) == previous


def test_private_multidxf_partial_receipt_cannot_release_durable_lease(tmp_path):
    store, root, old, _, _, req, ledger, journal, _ = _w06_committing_context(tmp_path)
    journal.arm(req)
    journal.apply(req)
    with pytest.raises(PrepareEvidenceError):
        journal.apply(req)
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.complete(req, _w06_result(req), trusted_artifacts={"part-one": old})
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"
    assert journal._read(req)[0] == "applied"


def test_real_subprocess_exit_mid_multidxf_commit_then_recovery_preserves_customer(tmp_path):
    store, root, old, _, _, req, _, journal, previous = _w06_committing_context(tmp_path)
    code = (
        "import sys,os,json;"
        "from pathlib import Path;"
        "from integration_cli.job_identity_ledger import DurableJobIdentityLedger;"
        "from integration_cli.batch_commit_journal import DurableMultiDXFRollbackJournal;"
        "j=DurableMultiDXFRollbackJournal(DurableJobIdentityLedger(Path(sys.argv[1])));"
        "q=json.loads(sys.argv[2]);"
        "j.arm(q);"
        "j.apply(q,after_replace=lambda i: os._exit(71) if i==1 else None)"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code, str(store), json.dumps(req, ensure_ascii=False)],
        cwd=ROOT, capture_output=True, text=True, timeout=20,
    )
    assert proc.returncode == 71, proc.stderr
    recovered = DurableMultiDXFRollbackJournal(DurableJobIdentityLedger(store))
    assert recovered._read(req)[0] == "applying"
    assert recovered.recover_rollback(req) == "rolled_back"
    assert (old.read_bytes(), old.stat().st_mtime_ns) == previous
    assert not (root / "part-two.dxf").exists()
    assert DurableJobIdentityLedger(store).claim(req).state == "rolled_back"


def test_private_multidxf_journal_rejects_per_part_mode(tmp_path):
    store, _, original, _, _, req, _, journal, before = _w06_committing_context(tmp_path)
    req["transaction_mode"] = "per_part"
    req["request_digest"] = compute_wire_request_digest(req)
    with pytest.raises(PrepareEvidenceError) as exc:
        journal.arm(req)
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"
    assert (original.read_bytes(), original.stat().st_mtime_ns) == before


# #2380: a *second* abrupt stop inside rollback must not publish a false
# terminal result or release another job's durable output-directory lock.
def test_real_subprocess_exit_during_rollback_then_second_process_resumes(tmp_path):
    store, root, old, _, _, req, ledger, journal, before = _w06_committing_context(tmp_path)
    journal.arm(req)
    # Both actual output files become new customer DXFs before interruption.
    with pytest.raises(SystemExit):
        journal.apply(req, after_replace=lambda n: (_ for _ in ()).throw(SystemExit()) if n == 2 else None)
    command = (
        "import sys,os,json;"
        "from pathlib import Path;"
        "from integration_cli.job_identity_ledger import DurableJobIdentityLedger;"
        "from integration_cli.batch_commit_journal import DurableMultiDXFRollbackJournal;"
        "q=json.loads(sys.argv[2]);"
        "j=DurableMultiDXFRollbackJournal(DurableJobIdentityLedger(Path(sys.argv[1])));"
        "j.recover_rollback(q,after_restored=lambda n: os._exit(72) if n==1 else None)"
    )
    p = subprocess.run(
        [sys.executable, "-c", command, str(store), json.dumps(req, ensure_ascii=False)],
        cwd=ROOT, capture_output=True, text=True, timeout=20,
    )
    assert p.returncode == 72, p.stderr
    # Rollback has only partially restored the batch. The *terminal* readback
    # must not advertise rolled_back, and another job cannot own this folder.
    resumed = DurableMultiDXFRollbackJournal(DurableJobIdentityLedger(store))
    assert resumed._read(req)[0] == "rolling_back"
    contender = _w06_request(operation="export", job="another-after-rollback-crash")
    ledger.claim(contender)
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.reserve_output_directories(contender, trusted_directories=[root])
    assert exc.value.code == "WHD_OUTPUT_PATH_LOCKED"
    assert resumed.recover_rollback(req) == "rolled_back"
    assert (old.read_bytes(), old.stat().st_mtime_ns) == before
    assert not (root / "part-two.dxf").exists()
    assert DurableJobIdentityLedger(store).claim(req).state == "rolled_back"
    assert ledger.reserve_output_directories(contender, trusted_directories=[root])


@pytest.mark.parametrize("mutation", ["customer_bytes", "customer_removed", "new_customer", "journal_json"])
def test_terminal_rollback_readback_refuses_lost_customer_evidence(tmp_path, mutation):
    import sqlite3

    store, root, original, _, _, req, _, journal, before = _w06_committing_context(tmp_path)
    journal.arm(req)
    journal.apply(req)
    assert journal.recover_rollback(req) == "rolled_back"
    if mutation == "customer_bytes":
        original.write_bytes(original.read_bytes() + b"\n999\nmodified-after-rollback")
    elif mutation == "customer_removed":
        original.unlink()
    elif mutation == "new_customer":
        _w06_real_output(root / "part-two.dxf")
    else:
        with sqlite3.connect(store / "job_identity.sqlite3") as conn:
            conn.execute(
                "UPDATE batch_replace_journals SET plan_json='{}' WHERE job_id=?",
                (req["job_id"],),
            )
    with pytest.raises(PrepareEvidenceError) as exc:
        DurableJobIdentityLedger(store).claim(req)
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"
    with pytest.raises(PrepareEvidenceError):
        DurableMultiDXFRollbackJournal(DurableJobIdentityLedger(store)).recover_rollback(req)
    # A terminal read failure must not silently rewrite or remove unexpected
    # customer data. No rerender or automatic restore is attempted.
    if mutation == "customer_bytes":
        assert original.read_bytes().endswith(b"modified-after-rollback")
