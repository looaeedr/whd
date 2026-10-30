# -*- coding: utf-8 -*-
"""#2380 Windows private *packaged* WHD-Engine.exe invocation and custody proof.

Run after PyInstaller creates genuine engine, never in the public CADSplit CLI.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.private_worker_installation import (
    load_private_execution, provision_private_installation,
)
from integration_cli.worker_key_custody import load_installation_key
from test_issue2378_prepare_batch import _request, _root

WINDOWS = sys.platform == "win32"


@pytest.mark.skipif(not WINDOWS, reason="real Windows current-user DPAPI required")
def test_installer_seals_source_custody_and_refuses_tampered_record(tmp_path, monkeypatch):
    profile = tmp_path / "本機DPAPI"
    profile.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(profile))
    name = "trusted-engine-install-test"
    key = load_installation_key(name, initialize=True)
    root = tmp_path / "Worker 私有帳本"
    root.mkdir()
    output = tmp_path / "客戶 DXF 目錄"
    output.mkdir()
    source = tmp_path / "來源 原始檔.dxf"
    source.write_bytes(b"test source bytes")
    sha = "a" * 64
    provision_private_installation(
        name, store_root=root, output_dir=output,
        source_documents={"door-1": source}, expected_engine_sha256=sha,
    )
    loaded = load_private_execution(name, engine_sha256=sha)
    assert loaded.worker_key == key
    assert loaded.store_root == root
    assert loaded.output_dir == output
    assert loaded.source_documents == {"door-1": source}
    with pytest.raises(PrepareEvidenceError):
        provision_private_installation(
            name, store_root=root, output_dir=output,
            source_documents={"door-1": source}, expected_engine_sha256=sha,
        )
    with pytest.raises(PrepareEvidenceError):
        load_private_execution(name, engine_sha256="b" * 64)
    record, = profile.rglob("trusted_sources_v1.json")
    data = json.loads(record.read_text(encoding="utf-8"))
    data["payload"]["output_dir"] = str(tmp_path / "惡意轉址")
    record.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(PrepareEvidenceError):
        load_private_execution(name, engine_sha256=sha)
    assert not (tmp_path / "惡意轉址").exists()


@pytest.mark.skipif(not WINDOWS, reason="real Windows private executable required")
def test_actual_packaged_engine_private_prepare_and_restart(tmp_path, monkeypatch):
    exe = Path(os.environ.get("WHD_TEST_ENGINE_EXE", ""))
    if not exe.is_file():
        pytest.skip("run from Windows Engine packager with WHD_TEST_ENGINE_EXE")
    profile = tmp_path / "WHD Worker LocalAppData"
    profile.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(profile))
    name = "trusted-engine-private-exe"
    key = load_installation_key(name, initialize=True)
    store = tmp_path / "安裝持久狀態"
    output = tmp_path / "實際出圖"
    store.mkdir()
    output.mkdir()
    original = tmp_path / "既有來源.dxf"
    original.write_bytes(b"private worker input source proof")
    sha = hashlib.sha256(exe.read_bytes()).hexdigest()
    provision_private_installation(
        name, store_root=store, output_dir=output,
        source_documents={"門片-0": original},
        expected_engine_sha256=sha,
    )
    request = _request(count=1)
    wire = tmp_path / "交付請求.json"
    wire.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    response = tmp_path / "受信任結果.json"
    cmd = [
        str(exe), "_private_installed", "prepare",
        "--installation-id", name, "--request", str(wire),
        "--response", str(response),
    ]
    result = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-1200:]
    prepared = json.loads(response.read_text(encoding="utf-8"))
    assert prepared["operation"] == "prepare"
    assert prepared["status"] == "success"
    assert prepared["manufacturing_verified"] is False
    assert len(prepared["items"]) == 1
    from integration_cli.job_identity_ledger import DurableJobIdentityLedger
    original_from_disk, receipt = DurableJobIdentityLedger(store).load_trusted_prepare(
        client_installation_id=request["client_installation_id"],
        job_id=request["job_id"], worker_key=key,
    )
    assert original_from_disk == request
    assert receipt == prepared
    # Same executable in a separate process must replay exact receipt without
    # creating customer DXFs or a new signing key.
    retry = tmp_path / "重新要求.json"
    replay = tmp_path / "重啟結果.json"
    retry.write_text(wire.read_text(encoding="utf-8"), encoding="utf-8")
    cmd[cmd.index(str(wire))] = str(retry)
    cmd[cmd.index(str(response))] = str(replay)
    second = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True, timeout=120)
    assert second.returncode == 0, second.stderr[-1200:]
    assert json.loads(replay.read_text(encoding="utf-8")) == prepared
    assert not list(output.glob("*.dxf"))
    # Wrong installation identity is rejected without writing success output.
    cmd[cmd.index(name)] = "unprovisioned-install"
    cmd[cmd.index(str(replay))] = str(tmp_path / "無授權.json")
    denied = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True, timeout=120)
    assert denied.returncode != 0
    assert not (tmp_path / "無授權.json").exists()


def test_source_only_worker_private_command_denied(tmp_path):
    from integration_cli.cadsplit_worker import main
    assert main(["_private_installed", "prepare", "--installation-id", "not-provisioned"]) == 4
