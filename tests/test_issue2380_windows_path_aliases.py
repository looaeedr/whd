# -*- coding: utf-8 -*-
"""#2380 W-06 physical lease identity and native Windows alias rejection.

No manufacturing fixtures are replaced. Windows creates a real junction and
checks the original output directory remains untouched after refusal.
"""
from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from integration_cli.job_identity_ledger import (
    DurableJobIdentityLedger, _output_directory_keys, _unsafe_windows_path,
)
from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.request_canonical import compute_wire_request_digest


def _export(job: str) -> dict:
    req = {
        "protocol_version": "1.1.0",
        "client_installation_id": "CAD-install-A",
        "request_id": "wire-001",
        "job_id": job,
        "operation": "export",
        "coordinate_contract_revision": "1",
        "transaction_mode": "all_or_nothing",
        "output": {"directory": "worker-owned", "overwrite": False},
        "items": [{
            "item_id": "door-1",
            "source_document_sha256": "f" * 64,
            "part": {"kind": "door", "cabinet_family": "金庫型",
                     "source_part_ref": "real-source-door",
                     "dimension_semantics": "cabinet_outer",
                     "dimensions_mm": {"width": 500, "height": 600, "thickness": 2},
                     "frame_edges": {"left": True, "right": True,
                                     "top": True, "bottom": True}},
            "physical_part_id": "whd-physical-door",
            "preparation_digest": "a" * 64,
            "target_frame_ids": ["frame-1"],
            "features": [],
        }],
    }
    req["request_digest"] = compute_wire_request_digest(req)
    return req


def test_existing_physical_lease_with_different_key_cannot_be_bypassed(tmp_path):
    """Simulates a previous path alias in the SQLite ledger without an OS alias."""
    store, out = tmp_path / "trusted-store", tmp_path / "客户 門板"
    store.mkdir()
    out.mkdir()
    led = DurableJobIdentityLedger(store)
    first, second = _export("first"), _export("second")
    assert led.claim(first).state == led.claim(second).state == "new"
    key, = led.reserve_output_directories(first, trusted_directories=[out])
    # Historical/in-flight lease using a distinct lexical alias but the
    # SAME pinned filesystem identity.  It must still hold the physical lock.
    alias = key + "-alternate-device-spelling"
    with sqlite3.connect(store / "job_identity.sqlite3") as db:
        db.execute("UPDATE output_directory_leases SET directory_key=? WHERE directory_key=?",
                   (alias, key))
        db.execute("UPDATE output_directory_identity SET directory_key=? WHERE directory_key=?",
                   (alias, key))
    with pytest.raises(PrepareEvidenceError) as exc:
        DurableJobIdentityLedger(store).reserve_output_directories(
            second, trusted_directories=[out]
        )
    assert exc.value.code == "WHD_OUTPUT_PATH_LOCKED"
    assert list(out.iterdir()) == []


@pytest.mark.skipif(sys.platform != "win32", reason="requires genuine Windows NTFS junction")
def test_real_windows_junction_and_ancestor_cannot_lease_customer_outputs(tmp_path):
    store, out = tmp_path / "trusted-store", tmp_path / "原始圖 客戶"
    store.mkdir()
    out.mkdir()
    customer = out / "keep-original.dxf"
    customer.write_bytes(b"customer-initial-dxf-content")
    junction = tmp_path / "junction-alias"
    made = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(out)],
        capture_output=True, text=True, check=False,
    )
    assert made.returncode == 0, made.stderr or made.stdout
    assert junction.is_junction(), "must prove actual Windows junction, not a simulated path"
    led = DurableJobIdentityLedger(store)
    req = _export("win-junction")
    assert led.claim(req).state == "new"
    for candidate in (junction, junction / ".." / "junction-alias"):
        with pytest.raises(PrepareEvidenceError) as exc:
            led.reserve_output_directories(req, trusted_directories=[candidate])
        assert exc.value.code == "WHD_OUTPUT_PATH_INVALID"
    with pytest.raises(PrepareEvidenceError) as exc:
        _output_directory_keys([out, junction])
    assert exc.value.code == "WHD_OUTPUT_PATH_INVALID"
    with pytest.raises(PrepareEvidenceError) as exc:
        DurableJobIdentityLedger(junction)
    assert exc.value.code == "WHD_JOB_STORE_UNAVAILABLE"
    assert customer.read_bytes() == b"customer-initial-dxf-content"
    # Ordinary canonical directory remains available after refused aliases.
    assert led.reserve_output_directories(req, trusted_directories=[out])


@pytest.mark.skipif(sys.platform != "win32", reason="Windows path namespace only")
def test_windows_unc_and_device_names_fail_closed_even_without_network_access():
    for raw in ("\\\\server\\share\\customer", "\\\\?\\C:\\customer",
                "\\\\.\\C:\\customer"):
        assert _unsafe_windows_path(Path(raw)), raw
