# -*- coding: utf-8 -*-
"""#2380 private durable identity only; neither public Worker nor DXF commit journal."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import ezdxf
import pytest
from jsonschema import Draft202012Validator

from integration_cli.job_identity_ledger import DurableJobIdentityLedger
from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.request_canonical import compute_wire_request_digest

ROOT = Path(__file__).resolve().parents[1]


def _request(*, operation="prepare", job="job-2378"):
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


def _result(req):
    return {
        "operation": req["operation"],
        "client_installation_id": req["client_installation_id"],
        "job_id": req["job_id"],
        "status": "success",
        "request_digest": req["request_digest"],
        "manufacturing_verified": False,
    }


def test_private_ledger_restarts_and_replays_same_semantics_without_new_job(tmp_path):
    req = _request()
    store = tmp_path / "trusted-installation-store"
    store.mkdir()
    first = DurableJobIdentityLedger(store)
    assert first.claim(req).state == "new"
    original = _result(req)
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
    req = _request(operation="export")
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
    req = _request(operation="export")
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
    req = _request(operation="export")
    ledger = DurableJobIdentityLedger(store)
    ledger.claim(req)
    receipt = _result(req)
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
    req = _request(operation="export")
    ledger = DurableJobIdentityLedger(store)
    ledger.claim(req)
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.complete(req, _result(req), trusted_artifacts={})
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"
    ledger.complete(req, _result(req), trusted_artifacts={"part": output})
    output.unlink()
    with pytest.raises(PrepareEvidenceError) as exc:
        ledger.claim(req)
    assert exc.value.code == "WHD_JOB_RECOVERY_REQUIRED"


def test_same_job_parallel_claims_have_one_winner_and_no_second_run(tmp_path):
    store = tmp_path / "worker-store"
    store.mkdir()
    req = _request()
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
    req = _request()
    ledger = DurableJobIdentityLedger(store)
    assert ledger.claim(req).state == "new"
    ledger.complete(req, _result(req), trusted_artifacts={})
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
    req = _request()
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
    assert ledger.claim(_request(operation="prepare")).state == "new"
    assert ledger.claim(_request(operation="export")).state == "new"
