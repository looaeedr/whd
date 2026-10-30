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
    authorize_private_job, load_private_authorized_execution,
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
    # A successful installed W-03 Prepare must attest a real customer DXF,
    # not an arbitrary byte string with a fabricated source SHA.
    import ezdxf
    from integration_cli.request_canonical import compute_wire_request_digest
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    doc.modelspace().add_circle((20, 30), 3, dxfattribs={"layer": "CUTTING"})
    doc.saveas(original)
    sha = hashlib.sha256(exe.read_bytes()).hexdigest()
    provision_private_installation(
        name, store_root=store, output_dir=output,
        source_documents={"門片-0": original},
        expected_engine_sha256=sha,
    )
    request = _request(count=1)
    request["items"][0]["source_document_sha256"] = hashlib.sha256(
        original.read_bytes()
    ).hexdigest()
    request["request_digest"] = compute_wire_request_digest(request)
    wire = tmp_path / "交付請求.json"
    wire.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    response = tmp_path / "受信任結果.json"
    # Installed custody by itself is not a ticket to manufacture any job.
    unapproved = subprocess.run([
        str(exe), "_private_installed", "prepare", "--installation-id", name,
        "--request", str(wire), "--response", str(response),
    ], cwd=tmp_path, capture_output=True, text=True, timeout=120)
    assert unapproved.returncode == 4
    assert not response.exists()
    authorize_private_job(name, request, engine_sha256=sha)
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



@pytest.mark.skipif(not WINDOWS, reason="requires actual Windows private Engine.exe")
def test_actual_packaged_engine_prepares_and_exports_real_source_dxf(tmp_path, monkeypatch):
    """Real EXE -> W-03 -> W-06 -> W-04 Save/Reload -> durable DXF replay."""
    import ezdxf
    from integration_cli.request_canonical import compute_wire_request_digest
    from test_issue2379_trusted_door_finalscene_batch import _real_batch
    from test_issue2380_private_worker_dispatch import _export_from_real_sources

    exe = Path(os.environ.get("WHD_TEST_ENGINE_EXE", ""))
    if not exe.is_file():
        pytest.skip("requires built actual onedir WHD-Engine.exe")
    profile = tmp_path / "DPAPI local 工作"
    profile.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(profile))
    name = "real-trusted-exe-export"
    key = load_installation_key(name, initialize=True)
    batch = _real_batch(tmp_path, count=1)
    original = batch[0]
    source_documents = batch[4]
    store, output = tmp_path / "worker-ledger", tmp_path / "private-dxf-output"
    store.mkdir()
    output.mkdir()
    exe_hash = hashlib.sha256(exe.read_bytes()).hexdigest()
    provision_private_installation(
        name, store_root=store, output_dir=output,
        source_documents=source_documents, expected_engine_sha256=exe_hash,
    )

    def invoke(operation, request, suffix):
        wire, reply = tmp_path / f"{suffix}-wire.json", tmp_path / f"{suffix}-reply.json"
        wire.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run([
            str(exe), "_private_installed", operation,
            "--installation-id", name, "--request", str(wire), "--response", str(reply),
        ], cwd=tmp_path, capture_output=True, text=True, timeout=120)
        if reply.is_file():
            body = json.loads(reply.read_text(encoding="utf-8"))
        else:
            body = None
        assert result.returncode == 0, (result.stderr[-1300:], body)
        return body

    authorize_private_job(name, original, engine_sha256=exe_hash)
    prepared = invoke("prepare", original, "first-prepare")
    assert prepared["status"] == "success"
    export = _export_from_real_sources(original, prepared, batch)
    export["output"]["directory"] = str(output)
    export["request_digest"] = compute_wire_request_digest(export)
    authorize_private_job(name, export, engine_sha256=exe_hash)
    finished = invoke("export", export, "first-export")
    assert finished["status"] == "success", finished
    assert finished["manufacturing_verified"] is False
    finals = {Path(x["path"]) for x in finished["items"]}
    assert len(finals) == 1
    assert all(p.is_file() and p.parent == output for p in finals)
    assert all(len(ezdxf.readfile(p).modelspace().query("CIRCLE")) > 0 for p in finals)
    immutable = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in finals}
    retried = dict(export)
    retried["request_id"] = "new-transport-only-replay"
    assert invoke("export", retried, "restarted-export") == finished
    assert immutable == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in finals}
    assert load_installation_key(name) == key



@pytest.mark.skipif(not WINDOWS, reason="Windows DPAPI required")
def test_sealed_job_approval_exact_digest_and_tamper_rejected(tmp_path, monkeypatch):
    from copy import deepcopy
    from integration_cli.request_canonical import compute_wire_request_digest

    profile = tmp_path / "worker-user-profile"
    profile.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(profile))
    name = "only-approved-job-owner"
    load_installation_key(name, initialize=True)
    store, output = tmp_path / "durable", tmp_path / "finished"
    store.mkdir()
    output.mkdir()
    source = tmp_path / "original-source.dxf"
    source.write_bytes(b"no manufacturing without approved job")
    sha = "a" * 64
    provision_private_installation(
        name, store_root=store, output_dir=output,
        source_documents={"door-1": source}, expected_engine_sha256=sha,
    )
    req = _request(count=1)
    with pytest.raises(PrepareEvidenceError):
        load_private_authorized_execution(name, req, engine_sha256=sha)
    authorize_private_job(name, req, engine_sha256=sha)
    approved = load_private_authorized_execution(name, req, engine_sha256=sha)
    from integration_cli.job_identity_ledger import _identity
    assert approved.approved_request_identity == _identity(req)
    updated = deepcopy(req)
    updated["items"][0]["part"]["dimensions_mm"]["width"] += 3
    updated["request_digest"] = compute_wire_request_digest(updated)
    with pytest.raises(PrepareEvidenceError):
        load_private_authorized_execution(name, updated, engine_sha256=sha)
    with pytest.raises(PrepareEvidenceError):
        authorize_private_job(name, req, engine_sha256=sha)
    ticket, = profile.rglob("approved-*.json")
    blob = json.loads(ticket.read_text(encoding="utf-8"))
    blob["payload"]["identity"][-1] = updated["request_digest"]
    ticket.write_text(json.dumps(blob), encoding="utf-8")
    with pytest.raises(PrepareEvidenceError):
        load_private_authorized_execution(name, req, engine_sha256=sha)
    assert not list(output.glob("*.dxf"))


def test_source_only_worker_private_command_denied(tmp_path):
    from integration_cli.cadsplit_worker import main
    assert main(["_private_installed", "prepare", "--installation-id", "not-provisioned"]) == 4


@pytest.mark.skipif(not WINDOWS, reason="requires actual Windows WHD-Engine.exe")
def test_actual_packaged_engine_twenty_attested_door_dxfs_replay_and_source_stale(
    tmp_path, monkeypatch,
):
    """Gate-A subset: one real EXE process per 20-item phase, immutable all-or-none replay.

    Not mixed-kind Gate A and not public manufacturing certification.
    """
    import ezdxf
    from integration_cli.request_canonical import compute_wire_request_digest
    from test_issue2379_trusted_door_finalscene_batch import _real_batch
    from test_issue2380_private_worker_dispatch import _export_from_real_sources

    exe = Path(os.environ.get("WHD_TEST_ENGINE_EXE", ""))
    if not exe.is_file():
        pytest.skip("requires built actual onedir WHD-Engine.exe")
    profile = tmp_path / "20件 Engine DPAPI 使用者"
    profile.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(profile))
    installation = "twenty-source-doors-private-exe"
    load_installation_key(installation, initialize=True)
    batch = _real_batch(tmp_path, count=20)
    prepare_request, _, _, _, trusted_sources, original_dxf, *_ = batch
    store = tmp_path / "20片持久工作狀態"
    destination = tmp_path / "20片實際製造輸出"
    store.mkdir()
    destination.mkdir()
    exe_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
    provision_private_installation(
        installation, store_root=store, output_dir=destination,
        source_documents=trusted_sources, expected_engine_sha256=exe_sha,
    )

    def invoke(operation, request, label, *, success=True):
        wire = tmp_path / f"{label}.json"
        response = tmp_path / f"{label}-response.json"
        wire.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
        proc = subprocess.run(
            [str(exe), "_private_installed", operation, "--installation-id",
             installation, "--request", str(wire), "--response", str(response)],
            cwd=tmp_path, capture_output=True, text=True, timeout=180,
        )
        if success:
            assert proc.returncode == 0, proc.stderr[-1400:]
            assert response.is_file()
            return json.loads(response.read_text(encoding="utf-8"))
        assert proc.returncode != 0
        return (json.loads(response.read_text(encoding="utf-8"))
                if response.exists() else None)

    authorize_private_job(installation, prepare_request, engine_sha256=exe_sha)
    prepared = invoke("prepare", prepare_request, "20件單次Prepare")
    assert prepared["status"] == "success"
    assert prepared["manufacturing_verified"] is False
    assert len(prepared["items"]) == 20
    assert len({part["physical_part_id"] for part in prepared["items"]}) == 20
    export = _export_from_real_sources(prepare_request, prepared, batch)
    export["output"]["directory"] = str(destination)
    export["request_digest"] = compute_wire_request_digest(export)
    authorize_private_job(installation, export, engine_sha256=exe_sha)
    result = invoke("export", export, "20件單次Export")
    assert result["status"] == "success"
    assert result["manufacturing_verified"] is False
    assert len(result["items"]) == 20
    paths = {Path(part["path"]) for part in result["items"]}
    assert len(paths) == 20 and all(path.parent == destination for path in paths)
    assert all(path.is_file() and ezdxf.readfile(path).modelspace().query("CIRCLE")
               for path in paths)
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}
    retry = dict(export)
    retry["request_id"] = "20-items-transport-retry"
    assert compute_wire_request_digest(retry) == export["request_digest"]
    assert invoke("export", retry, "20件重啟重送") == result
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths} == before
    # Even a previously committed job cannot be replayed against changed
    # original source bytes; failed recheck must not touch ANY final DXF.
    original_dxf.write_bytes(original_dxf.read_bytes() + b"\n")
    refused = invoke("export", retry, "20件原始來源竄改", success=False)
    if refused is not None:
        assert refused["status"] != "success"
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths} == before


@pytest.mark.skipif(not WINDOWS, reason="requires genuine packaged Windows WHD-Engine.exe")
def test_packaged_engine_twenty_mixed_door_small_door_dxf_and_immutable_replay(
    tmp_path, monkeypatch,
):
    """Actual Engine EXE: 10 Doors + 10 indicator small doors, WHD-only export.

    No public CLI capability or Gate A claim; same immutable W-06 job approval
    and actual WHD FinalScene/Save->Reload as the normal private EXE path.
    """
    from copy import deepcopy
    import ezdxf
    from integration_cli.request_canonical import compute_wire_request_digest
    from test_issue2378_prepare_batch import (
        _twenty_mixed_door_small_door_prepare,
        _export_request_from_prepared,
    )
    from test_issue2379_wire_feature_preflight import _circle

    exe = Path(os.environ.get("WHD_TEST_ENGINE_EXE", ""))
    if not exe.is_file():
        pytest.skip("requires built onedir Engine EXE")
    profile = tmp_path / "混合門板 LocalAppData"
    profile.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(profile))
    installation = "mixed-door-small-door-private-exe"
    load_installation_key(installation, initialize=True)
    _resource, _small_baseline, original = _twenty_mixed_door_small_door_prepare(
        tmp_path
    )
    source = tmp_path / "CADSplit 原始20件.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    handles = [
        doc.modelspace().add_circle(
            (12.0, 12.0), 2.0, dxfattribs={"layer": "CUTTING"},
        ).dxf.handle
        for _ in original["items"]
    ]
    doc.saveas(source)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    for part in original["items"]:
        part["source_document_sha256"] = source_sha
    original["request_digest"] = compute_wire_request_digest(original)
    sources = {part["item_id"]: source for part in original["items"]}
    store, output = tmp_path / "混合持久帳本", tmp_path / "混合製造輸出"
    store.mkdir()
    output.mkdir()
    engine_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
    provision_private_installation(
        installation, store_root=store, output_dir=output,
        source_documents=sources, expected_engine_sha256=engine_sha,
    )

    def run(operation, request, label, *, must_succeed=True):
        wire, response = tmp_path / f"{label}-req.json", tmp_path / f"{label}-resp.json"
        wire.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
        process = subprocess.run(
            [str(exe), "_private_installed", operation,
             "--installation-id", installation,
             "--request", str(wire), "--response", str(response)],
            cwd=tmp_path, capture_output=True, text=True, timeout=180,
        )
        body = (json.loads(response.read_text(encoding="utf-8"))
                if response.is_file() else None)
        if must_succeed:
            assert process.returncode == 0, (process.stderr[-1200:], body)
        else:
            assert process.returncode != 0
        return body

    authorize_private_job(installation, original, engine_sha256=engine_sha)
    receipt = run("prepare", original, "混合Prepare")
    assert receipt["status"] == "success" and len(receipt["items"]) == 20
    export = _export_request_from_prepared(original, receipt)
    for i, part in enumerate(export["items"]):
        frame = receipt["items"][i]["target_frames"][0]
        feature = _circle(frame)
        feature["feature_id"] = f"mixed-exe-{i}"
        feature["source_ref"] = f"dxf-handle-{i}"
        feature["center_mm"] = [12.0, 12.0]
        feature["radius_mm"] = 2.0
        feature["source_transform"]["source_entity_refs"] = [handles[i]]
        feature["source_transform"]["target_dimensions_mm"] = deepcopy(
            frame["finished_face_dimensions_mm"]
        )
        part["features"] = [feature]
    export["output"]["directory"] = str(output)
    export["request_digest"] = compute_wire_request_digest(export)
    authorize_private_job(installation, export, engine_sha256=engine_sha)
    result = run("export", export, "混合Export")
    assert result["status"] == "success"
    assert result["manufacturing_verified"] is False
    assert len(result["items"]) == 20
    paths = {Path(row["path"]) for row in result["items"]}
    assert len(paths) == 20 and all(path.parent == output for path in paths)
    assert all(
        any(entity.dxf.layer == "BEND" for entity in ezdxf.readfile(path).modelspace())
        and len(ezdxf.readfile(path).modelspace().query("CIRCLE")) >= 1
        for path in paths
    )
    original_outputs = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}
    replay = dict(export)
    replay["request_id"] = "mixed-20-cad-transport-retry"
    assert run("export", replay, "混合重新啟動") == result
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths} == original_outputs
    source.write_bytes(source.read_bytes() + b"\n")
    denied = run("export", replay, "混合來源變更", must_succeed=False)
    assert denied is None or denied["status"] != "success"
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths} == original_outputs


@pytest.mark.skipif(not WINDOWS, reason="real Windows DPAPI and filesystem required")
@pytest.mark.parametrize("collision", [
    "same_store_output", "store_inside_output", "output_inside_store",
    "source_inside_output", "source_inside_store",
])
def test_private_installer_never_seals_originals_inside_worker_writable_trees(
    tmp_path, monkeypatch, collision,
):
    """Unsafe custody is denied BEFORE any signed installation mapping exists."""
    profile = tmp_path / "DPAPI 隔離設定"
    profile.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(profile))
    installation = "private-custody-" + collision
    load_installation_key(installation, initialize=True)
    store, output = tmp_path / "state", tmp_path / "customer-output"
    store.mkdir()
    output.mkdir()
    if collision == "same_store_output":
        output = store
    elif collision == "store_inside_output":
        store = output / "state"
        store.mkdir()
    elif collision == "output_inside_store":
        output = store / "completed"
        output.mkdir()
    source = tmp_path / "customer-original.dxf"
    if collision == "source_inside_output":
        source = output / "customer-original.dxf"
    elif collision == "source_inside_store":
        source = store / "customer-original.dxf"
    source.write_bytes(b"keep-original-source-bytes")
    with pytest.raises(PrepareEvidenceError) as exc:
        provision_private_installation(
            installation, store_root=store, output_dir=output,
            source_documents={"door-1": source}, expected_engine_sha256="a" * 64,
        )
    assert exc.value.code == "WHD_JOB_STORE_UNAVAILABLE"
    assert source.read_bytes() == b"keep-original-source-bytes"
    assert not list(profile.rglob("trusted_sources_v1.json"))


@pytest.mark.skipif(not WINDOWS, reason="requires genuine Windows path namespace")
def test_private_installer_rejects_unc_device_namespace_before_filesystem_probe():
    """The private installer must share W-06's UNC/device fail-closed policy."""
    from integration_cli.private_worker_installation import _trusted_dir, _trusted_file

    for raw in (
        r"\\server\share\untrusted", r"\\?\C:\untrusted",
        r"\\.\C:\untrusted",
    ):
        candidate = Path(raw)
        with pytest.raises(PrepareEvidenceError) as directory:
            _trusted_dir(candidate)
        assert directory.value.code == "WHD_JOB_STORE_UNAVAILABLE"
        with pytest.raises(PrepareEvidenceError) as original:
            _trusted_file(candidate)
        assert original.value.code == "WHD_JOB_STORE_UNAVAILABLE"


@pytest.mark.skipif(not WINDOWS, reason="real Windows Engine.exe and DPAPI required")
def test_packaged_engine_indicator_box_size_only_prepare_and_export_denial(
    tmp_path, monkeypatch,
):
    """Genuine EXE seals WHD shared-box size; never manufactures unowned Features."""
    from integration_cli.request_canonical import compute_wire_request_digest
    from test_issue2378_prepare_batch import (
        _indicator_box_request, _export_request_from_prepared,
    )
    import ezdxf

    exe = Path(os.environ.get("WHD_TEST_ENGINE_EXE", ""))
    if not exe.is_file():
        pytest.skip("requires genuine packaged onedir Engine.exe")
    profile = tmp_path / "Box DPAPI private profile"
    profile.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(profile))
    installation = "box-size-only-real-exe"
    load_installation_key(installation, initialize=True)
    _, _, request = _indicator_box_request(tmp_path)
    original_dxf = tmp_path / "CADSplit 原始盒子.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    doc.modelspace().add_circle((12, 12), 2, dxfattribs={"layer": "CUTTING"})
    doc.saveas(original_dxf)
    request["items"][0]["source_document_sha256"] = hashlib.sha256(
        original_dxf.read_bytes()
    ).hexdigest()
    request["request_digest"] = compute_wire_request_digest(request)
    item_id = request["items"][0]["item_id"]
    store, output = tmp_path / "box-ledger", tmp_path / "box-out"
    store.mkdir()
    output.mkdir()
    exe_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
    provision_private_installation(
        installation, store_root=store, output_dir=output,
        source_documents={item_id: original_dxf}, expected_engine_sha256=exe_sha,
    )

    def invoke(operation, body, label):
        wire, reply = tmp_path / f"{label}-request.json", tmp_path / f"{label}-reply.json"
        wire.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        proc = subprocess.run(
            [str(exe), "_private_installed", operation,
             "--installation-id", installation,
             "--request", str(wire), "--response", str(reply)],
            cwd=tmp_path, capture_output=True, text=True, timeout=150,
        )
        return proc.returncode, (
            json.loads(reply.read_text(encoding="utf-8")) if reply.exists() else None
        )

    authorize_private_job(installation, request, engine_sha256=exe_sha)
    code, receipt = invoke("prepare", request, "box-prepare")
    assert code == 0 and receipt["status"] == "success", receipt
    assert receipt["manufacturing_verified"] is False
    frame = receipt["items"][0]["target_frames"][0]
    assert frame["frame_id"].startswith("indicator_box:")
    assert frame["allowed_feature_types"] == []
    export = _export_request_from_prepared(request, receipt)
    export["output"]["directory"] = str(output)
    export["request_digest"] = compute_wire_request_digest(export)
    authorize_private_job(installation, export, engine_sha256=exe_sha)
    code, denied = invoke("export", export, "box-export-denied")
    assert code != 0, denied
    assert denied is None or denied["status"] != "success"
    assert not list(output.glob("*.dxf"))
    assert original_dxf.is_file()
    # A new source SHA cannot be smuggled under the original no-feature job.
    original_dxf.write_bytes(original_dxf.read_bytes() + b"\\nchanged-after-prepare")
    code, stale = invoke("export", export, "box-after-original-source-mutated")
    assert code != 0
    assert stale is not None
    assert stale["diagnostics"][0]["code"] == "WHD_SOURCE_UNVERIFIED"
    assert not list(output.glob("*.dxf"))


@pytest.mark.skipif(not WINDOWS, reason="true Windows packaged Engine.exe and DPAPI required")
@pytest.mark.parametrize("kind", ["end_cap_head", "end_cap_tail"])
def test_packaged_engine_vault_endcap_size_only_prepare_and_export_denial(
    tmp_path, monkeypatch, kind,
):
    """Proof through actual installed executable, not a Python-only adapter."""
    from integration_cli.request_canonical import compute_wire_request_digest
    from test_issue2378_prepare_batch import _vault_endcap_request, _export_request_from_prepared
    import ezdxf

    exe = Path(os.environ.get("WHD_TEST_ENGINE_EXE", ""))
    if not exe.is_file():
        pytest.skip("requires real packaged private Engine.exe")
    profile = tmp_path / f"EndCap DPAPI {kind}"
    profile.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(profile))
    installation = "endcap-size-only-" + kind
    load_installation_key(installation, initialize=True)
    _, _, request = _vault_endcap_request(tmp_path, kind=kind)
    original_dxf = tmp_path / f"CADSplit 原始{kind}.dxf"
    dxf = ezdxf.new("R2010")
    dxf.header["$INSUNITS"] = 4
    dxf.modelspace().add_circle((12, 12), 2, dxfattribs={"layer": "CUTTING"})
    dxf.saveas(original_dxf)
    request["items"][0]["source_document_sha256"] = hashlib.sha256(
        original_dxf.read_bytes()
    ).hexdigest()
    request["request_digest"] = compute_wire_request_digest(request)
    item_id = request["items"][0]["item_id"]
    store = tmp_path / "Worker private journal"
    output = tmp_path / "Customer output"
    store.mkdir()
    output.mkdir()
    sha = hashlib.sha256(exe.read_bytes()).hexdigest()
    provision_private_installation(
        installation, store_root=store, output_dir=output,
        source_documents={item_id: original_dxf}, expected_engine_sha256=sha,
    )

    def run(operation, body, label):
        wire = tmp_path / f"{label}.json"
        reply = tmp_path / f"{label}.reply.json"
        wire.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run([
            str(exe), "_private_installed", operation,
            "--installation-id", installation,
            "--request", str(wire), "--response", str(reply),
        ], cwd=tmp_path, capture_output=True, text=True, timeout=150)
        return result.returncode, (
            json.loads(reply.read_text(encoding="utf-8")) if reply.is_file() else None
        )

    authorize_private_job(installation, request, engine_sha256=sha)
    code, receipt = run("prepare", request, "endcap-prepare")
    assert code == 0 and receipt["status"] == "success", receipt
    frame = receipt["items"][0]["target_frames"][0]
    assert frame["frame_id"].startswith(kind + ":")
    assert frame["allowed_feature_types"] == []
    assert receipt["manufacturing_verified"] is False
    export = _export_request_from_prepared(request, receipt)
    export["output"]["directory"] = str(output)
    export["request_digest"] = compute_wire_request_digest(export)
    authorize_private_job(installation, export, engine_sha256=sha)
    status, refused = run("export", export, "endcap-export-denied")
    assert status != 0, refused
    assert refused is None or refused["status"] != "success"
    assert not list(output.glob("*.dxf"))
    assert original_dxf.is_file()
    original_dxf.write_bytes(original_dxf.read_bytes() + b"\\nsource-changed-after-EndCap-prepare")
    status, stale = run("export", export, "endcap-export-source-stale")
    assert status != 0
    assert stale is not None
    assert stale["diagnostics"][0]["code"] == "WHD_SOURCE_UNVERIFIED"
    assert not list(output.glob("*.dxf"))


@pytest.mark.skipif(not WINDOWS, reason="requires real Windows packaged Engine.exe and DPAPI")
@pytest.mark.parametrize("fault", ["wrong_source_sha", "malformed_source_dxf"])
def test_packaged_engine_rejects_unattested_original_before_persisting_prepare(
    tmp_path, monkeypatch, fault,
):
    """Real EXE must not create a signed W-03 job for an invalid original."""
    import ezdxf
    from integration_cli.request_canonical import compute_wire_request_digest
    from integration_cli.job_identity_ledger import DurableJobIdentityLedger

    exe = Path(os.environ.get("WHD_TEST_ENGINE_EXE", ""))
    if not exe.is_file():
        pytest.skip("requires built onedir Engine.exe")
    profile = tmp_path / "private-preflight-profile"
    profile.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(profile))
    name = "prepare-source-preflight-" + fault
    load_installation_key(name, initialize=True)
    store = tmp_path / "private-state"
    output = tmp_path / "trusted-output"
    store.mkdir()
    output.mkdir()
    source = tmp_path / "原始來源.dxf"
    if fault == "malformed_source_dxf":
        source.write_bytes(b"not an actual source DXF")
    else:
        doc = ezdxf.new("R2010")
        doc.header["$INSUNITS"] = 4
        doc.modelspace().add_circle((12, 13), 2, dxfattribs={"layer": "CUTTING"})
        doc.saveas(source)
    exe_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
    request = _request(count=1)
    request["items"][0]["source_document_sha256"] = (
        "0" * 64 if fault == "wrong_source_sha" else
        hashlib.sha256(source.read_bytes()).hexdigest()
    )
    request["request_digest"] = compute_wire_request_digest(request)
    provision_private_installation(
        name, store_root=store, output_dir=output,
        source_documents={request["items"][0]["item_id"]: source},
        expected_engine_sha256=exe_sha,
    )
    authorize_private_job(name, request, engine_sha256=exe_sha)
    wire = tmp_path / "source-request.json"
    response = tmp_path / "source-response.json"
    wire.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run([
        str(exe), "_private_installed", "prepare",
        "--installation-id", name,
        "--request", str(wire), "--response", str(response),
    ], cwd=tmp_path, capture_output=True, text=True, timeout=150)
    assert proc.returncode != 0, proc.stdout
    assert response.is_file(), proc.stderr
    result = json.loads(response.read_text(encoding="utf-8"))
    assert result["status"] == "failed"
    assert result["diagnostics"][0]["code"] == "WHD_SOURCE_UNVERIFIED"
    with DurableJobIdentityLedger(store)._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
    assert not list(output.glob("*.dxf"))


@pytest.mark.skipif(not WINDOWS, reason="real packaged Engine.exe + DPAPI required")
def test_packaged_engine_exports_unperforated_door_and_small_door_native_dxfs(
    tmp_path, monkeypatch,
):
    """Installed EXE -> sealed W-03 -> staged W-04 -> durable W-06, no source holes."""
    from copy import deepcopy
    import ezdxf
    from integration_cli.request_canonical import compute_wire_request_digest
    from test_issue2378_prepare_batch import (
        _indicator_small_door_request, _export_request_from_prepared,
    )

    exe = Path(os.environ.get("WHD_TEST_ENGINE_EXE", ""))
    if not exe.is_file():
        pytest.skip("requires built private Windows Engine.exe")
    profile = tmp_path / "無孔門片 DPAPI"
    profile.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(profile))
    name = "door-noholes-real-exe"
    load_installation_key(name, initialize=True)
    root, _, small, _ = _indicator_small_door_request(tmp_path)
    request = _request(count=2)
    request["items"][1]["part"] = deepcopy(small["items"][0]["part"])
    request["items"][1]["part"]["source_part_ref"] = "WHD-small-door-empty-original"
    original = tmp_path / "CADSplit no-holes 客戶原圖.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    assert len(doc.modelspace()) == 0
    doc.saveas(original)
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    for row in request["items"]:
        row["source_document_sha256"] = digest
    request["request_digest"] = compute_wire_request_digest(request)
    store, output = tmp_path / "W06 保管資料", tmp_path / "W04 製造 DXF"
    store.mkdir()
    output.mkdir()
    exe_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
    provision_private_installation(
        name, store_root=store, output_dir=output,
        source_documents={row["item_id"]: original for row in request["items"]},
        expected_engine_sha256=exe_sha,
    )

    def invoke(operation, body, suffix):
        wire, response = tmp_path / f"{suffix}.json", tmp_path / f"{suffix}-reply.json"
        wire.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        proc = subprocess.run([
            str(exe), "_private_installed", operation, "--installation-id", name,
            "--request", str(wire), "--response", str(response),
        ], cwd=tmp_path, capture_output=True, text=True, timeout=150)
        return proc, (
            json.loads(response.read_text(encoding="utf-8")) if response.is_file() else None
        )

    authorize_private_job(name, request, engine_sha256=exe_sha)
    prepare_process, prepared = invoke("prepare", request, "prepare-unperforated")
    assert prepare_process.returncode == 0 and prepared["status"] == "success", (
        prepare_process.stderr, prepared,
    )
    assert all(not x["target_frames"][0].get("allowed_feature_types") == []
               for x in prepared["items"])  # exact WHD Door-local, not size-only
    export = _export_request_from_prepared(request, prepared)
    export["output"]["directory"] = str(output)
    export["request_digest"] = compute_wire_request_digest(export)
    authorize_private_job(name, export, engine_sha256=exe_sha)
    proc, finished = invoke("export", export, "export-unperforated")
    assert proc.returncode == 0 and finished["status"] == "success", (proc.stderr, finished)
    assert finished["manufacturing_verified"] is False  # private, not Gate A
    paths = {Path(item["path"]) for item in finished["items"]}
    assert len(paths) == 2 and all(p.is_file() and p.parent == output for p in paths)
    for path in paths:
        saved = ezdxf.readfile(path)
        assert any(e.dxf.layer == "CUTTING" for e in saved.modelspace())
        assert saved.modelspace().query('LINE[layer=="BEND"]')
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}
    retry = deepcopy(export)
    retry["request_id"] = "noholes-idempotent-retry"
    proc, repeated = invoke("export", retry, "export-replay-unperforated")
    assert proc.returncode == 0 and repeated == finished
    assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}


@pytest.mark.skipif(not WINDOWS, reason="packaged Windows Engine.exe and DPAPI required")
def test_packaged_engine_featureless_box_real_native_dxf_and_immutable_replay(
    tmp_path, monkeypatch,
):
    """Private onedir EXE: WHD box baseline -> FinalScene -> real DXF."""
    import ezdxf
    from copy import deepcopy
    from integration_cli.request_canonical import compute_wire_request_digest
    from test_issue2378_prepare_batch import _indicator_box_request, _export_request_from_prepared

    exe = Path(os.environ.get("WHD_TEST_ENGINE_EXE", ""))
    if not exe.is_file():
        pytest.skip("requires true Engine.exe")
    profile = tmp_path / "全域指示燈盒 DPAPI"
    profile.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(profile))
    name = "featureless-box-physical-dxf"
    load_installation_key(name, initialize=True)
    _, _, request = _indicator_box_request(tmp_path)
    source = tmp_path / "CADSplit 空白原圖盒.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    assert len(doc.modelspace()) == 0
    doc.saveas(source)
    request["items"][0]["source_document_sha256"] = hashlib.sha256(
        source.read_bytes()
    ).hexdigest()
    request["request_digest"] = compute_wire_request_digest(request)
    store, output = tmp_path / "W06 盒子帳本", tmp_path / "W04 盒子 DXF"
    store.mkdir()
    output.mkdir()
    sha = hashlib.sha256(exe.read_bytes()).hexdigest()
    provision_private_installation(
        name, store_root=store, output_dir=output,
        source_documents={request["items"][0]["item_id"]: source},
        expected_engine_sha256=sha,
    )

    def invoke(operation, body, tag):
        wire, result_file = tmp_path / f"{tag}.json", tmp_path / f"{tag}-out.json"
        wire.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        proc = subprocess.run([
            str(exe), "_private_installed", operation, "--installation-id", name,
            "--request", str(wire), "--response", str(result_file),
        ], cwd=tmp_path, capture_output=True, text=True, timeout=150)
        return proc, json.loads(result_file.read_text(encoding="utf-8")) if result_file.exists() else None

    authorize_private_job(name, request, engine_sha256=sha)
    proc, prepared = invoke("prepare", request, "box-signed-prepare")
    assert proc.returncode == 0 and prepared["status"] == "success", (
        proc.stderr, prepared,
    )
    assert prepared["items"][0]["target_frames"][0]["allowed_feature_types"] == []
    export = _export_request_from_prepared(request, prepared)
    export["output"]["directory"] = str(output)
    export["request_digest"] = compute_wire_request_digest(export)
    authorize_private_job(name, export, engine_sha256=sha)
    proc, finished = invoke("export", export, "box-physical-export")
    assert proc.returncode == 0 and finished["status"] == "success", (
        proc.stderr, finished,
    )
    assert finished["manufacturing_verified"] is False
    assert len(finished["items"]) == 1
    output_file = Path(finished["items"][0]["path"])
    assert output_file.is_file() and output_file.parent == output
    actual = ezdxf.readfile(output_file)
    assert any(e.dxf.layer == "CUTTING" for e in actual.modelspace())
    assert actual.modelspace().query('LINE[layer=="BEND"]')
    before = (output_file.read_bytes(), output_file.stat().st_mtime_ns)
    repeated = deepcopy(export)
    repeated["request_id"] = "box-transport-replay"
    proc, replayed = invoke("export", repeated, "box-replay")
    assert proc.returncode == 0 and replayed == finished
    assert (output_file.read_bytes(), output_file.stat().st_mtime_ns) == before


@pytest.mark.skipif(not WINDOWS, reason="genuine packaged Engine.exe + Windows DPAPI required")
@pytest.mark.parametrize("kind", ["end_cap_head", "end_cap_tail"])
def test_packaged_engine_vault_endcap_intrinsic_native_dxf_export_and_replay(
    tmp_path, monkeypatch, kind,
):
    """W-03 signed size-only EndCap to WHD native FinalScene DXF and durable replay."""
    import ezdxf
    from copy import deepcopy
    from integration_cli.request_canonical import compute_wire_request_digest
    from test_issue2378_prepare_batch import _vault_endcap_request, _export_request_from_prepared

    exe = Path(os.environ.get("WHD_TEST_ENGINE_EXE", ""))
    if not exe.is_file():
        pytest.skip("requires real onedir Engine.exe")
    profile = tmp_path / f"EndCap 正式幾何 {kind} DPAPI"
    profile.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(profile))
    name = "vault-native-" + kind
    load_installation_key(name, initialize=True)
    _, _, request = _vault_endcap_request(tmp_path, kind=kind)
    source = tmp_path / f"CADSplit-EMPTY-{kind}.dxf"
    drawing = ezdxf.new("R2010")
    drawing.header["$INSUNITS"] = 4
    assert len(drawing.modelspace()) == 0
    drawing.saveas(source)
    request["items"][0]["source_document_sha256"] = hashlib.sha256(
        source.read_bytes()
    ).hexdigest()
    request["request_digest"] = compute_wire_request_digest(request)
    store, output = tmp_path / "W06 Vault 持久帳本", tmp_path / "W04 Vault 正式DXF"
    store.mkdir()
    output.mkdir()
    engine_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
    provision_private_installation(
        name, store_root=store, output_dir=output,
        source_documents={request["items"][0]["item_id"]: source},
        expected_engine_sha256=engine_sha,
    )

    def invoke(operation, body, tag):
        wire = tmp_path / f"{tag}-wire.json"
        reply = tmp_path / f"{tag}-reply.json"
        wire.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        completed = subprocess.run([
            str(exe), "_private_installed", operation, "--installation-id", name,
            "--request", str(wire), "--response", str(reply),
        ], cwd=tmp_path, capture_output=True, text=True, timeout=150)
        return completed, json.loads(reply.read_text(encoding="utf-8")) if reply.is_file() else None

    authorize_private_job(name, request, engine_sha256=engine_sha)
    process, prepared = invoke("prepare", request, "vault-prepared")
    assert process.returncode == 0 and prepared["status"] == "success", (
        process.stderr, prepared,
    )
    frame = prepared["items"][0]["target_frames"][0]
    assert frame["allowed_feature_types"] == []
    assert frame["frame_id"].startswith(kind + ":")
    export = _export_request_from_prepared(request, prepared)
    export["output"]["directory"] = str(output)
    export["request_digest"] = compute_wire_request_digest(export)
    authorize_private_job(name, export, engine_sha256=engine_sha)
    process, result = invoke("export", export, "vault-output")
    assert process.returncode == 0 and result["status"] == "success", (
        process.stderr, result,
    )
    assert result["manufacturing_verified"] is False
    assert len(result["items"]) == 1
    part = Path(result["items"][0]["path"])
    assert part.is_file() and part.parent == output
    saved = ezdxf.readfile(part)
    assert any(e.dxf.layer == "CUTTING" for e in saved.modelspace())
    assert saved.modelspace().query('LINE[layer=="BEND"]')
    before = (part.read_bytes(), part.stat().st_mtime_ns)
    retry = deepcopy(export)
    retry["request_id"] = "vault-transmission-replay"
    process, again = invoke("export", retry, "vault-replayed")
    assert process.returncode == 0 and again == result
    assert (part.read_bytes(), part.stat().st_mtime_ns) == before


@pytest.mark.skipif(not WINDOWS, reason="genuine packaged Windows WHD-Engine.exe + DPAPI required")
def test_packaged_engine_twenty_mixed_five_physical_kinds_native_dxf_atomic_replay(
    tmp_path, monkeypatch,
):
    """One genuine installed EXE job: all 5 WHD physical kinds, 20 final DXFs.

    Not a public Worker Gate A release: external source Feature mapping and
    nonstandard EndCap assemblies remain deliberately disabled.
    """
    from copy import deepcopy
    import ezdxf
    from integration_cli.request_canonical import compute_wire_request_digest
    from test_issue2378_prepare_batch import _export_request_from_prepared
    from test_issue2379_trusted_door_finalscene_batch import _empty_vault_endcap_five_kind_batch

    exe = Path(os.environ.get("WHD_TEST_ENGINE_EXE", ""))
    if not exe.is_file():
        pytest.skip("requires actual packaged onedir WHD-Engine.exe")
    profile = tmp_path / "20件五類盒門封頭尾 DPAPI"
    profile.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(profile))
    installation = "twenty-five-physical-classes"
    load_installation_key(installation, initialize=True)
    original, _, _, _resource_root, trusted_sources, original_dxf = (
        _empty_vault_endcap_five_kind_batch(tmp_path, count=20)
    )
    kinds = {row["part"]["kind"] for row in original["items"]}
    assert kinds == {
        "door", "indicator_small_door", "indicator_box",
        "end_cap_head", "end_cap_tail",
    }
    store = tmp_path / "W06 真實20件 持久工作狀態"
    destination = tmp_path / "W04 真實20件 製造輸出"
    store.mkdir()
    destination.mkdir()
    engine_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
    provision_private_installation(
        installation, store_root=store, output_dir=destination,
        source_documents=trusted_sources, expected_engine_sha256=engine_sha,
    )

    def run(operation, request, label, *, success=True):
        wire = tmp_path / f"{label}.json"
        response_path = tmp_path / f"{label}-response.json"
        wire.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
        process = subprocess.run([
            str(exe), "_private_installed", operation,
            "--installation-id", installation,
            "--request", str(wire), "--response", str(response_path),
        ], cwd=tmp_path, capture_output=True, text=True, timeout=240)
        response = (
            json.loads(response_path.read_text(encoding="utf-8"))
            if response_path.is_file() else None
        )
        if success:
            assert process.returncode == 0, (process.stderr[-1400:], response)
            assert response is not None and response["status"] == "success"
        else:
            assert process.returncode != 0, response
            assert response is not None and response["status"] == "failed"
        return response

    authorize_private_job(installation, original, engine_sha256=engine_sha)
    prepared = run("prepare", original, "20件五類-Prepare")
    assert len(prepared["items"]) == 20
    assert len({p["physical_part_id"] for p in prepared["items"]}) == 20
    for source_part, receipt in zip(original["items"], prepared["items"]):
        if source_part["part"]["kind"] in (
            "indicator_box", "end_cap_head", "end_cap_tail",
        ):
            assert receipt["target_frames"][0]["allowed_feature_types"] == []
    export = _export_request_from_prepared(original, prepared)
    assert all(not row["features"] for row in export["items"])
    export["output"]["directory"] = str(destination)
    export["request_digest"] = compute_wire_request_digest(export)
    authorize_private_job(installation, export, engine_sha256=engine_sha)
    result = run("export", export, "20件五類-Export")
    assert result["manufacturing_verified"] is False
    assert len(result["items"]) == 20
    output_items = {
        row["physical_part_id"]: Path(row["path"]) for row in result["items"]
    }
    assert set(output_items) == {
        row["physical_part_id"] for row in prepared["items"]
    }
    for physical_id, path in output_items.items():
        assert path.is_file() and path.parent == destination
        drawing = ezdxf.readfile(path)
        assert any(entity.dxf.layer == "CUTTING" for entity in drawing.modelspace()), physical_id
        assert drawing.modelspace().query('LINE[layer=="BEND"]'), physical_id
    before = {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in output_items.values()
    }
    retry = deepcopy(export)
    retry["request_id"] = "five-kind-delivery-replay"
    assert compute_wire_request_digest(retry) == export["request_digest"]
    assert run("export", retry, "20件五類-重啟重送") == result
    assert {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in output_items.values()
    } == before
    original_dxf.write_bytes(original_dxf.read_bytes() + b"\\nsource stale")
    denied = run("export", retry, "20件五類-原圖竄改", success=False)
    assert denied["diagnostics"][0]["code"] == "WHD_SOURCE_UNVERIFIED"
    assert {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in output_items.values()
    } == before


@pytest.mark.skipif(not WINDOWS, reason="real Windows WHD-Engine.exe and DPAPI required")
@pytest.mark.parametrize("source_layer", ["MARKING", "BEND"])
def test_packaged_engine_never_converts_attested_noncutting_source_to_dxf_hole(
    tmp_path, monkeypatch, source_layer,
):
    """Actual EXE must refuse a signed source marker before durable output."""
    from copy import deepcopy
    import ezdxf
    from integration_cli.request_canonical import compute_wire_request_digest
    from test_issue2378_prepare_batch import _export_request_from_prepared
    from test_issue2379_trusted_door_finalscene_batch import _real_batch
    from integration_cli.job_identity_ledger import DurableJobIdentityLedger

    exe = Path(os.environ.get("WHD_TEST_ENGINE_EXE", ""))
    if not exe.is_file():
        pytest.skip("requires packaged Windows Engine.exe")
    profile = tmp_path / f"標記不可切割-DPAPI-{source_layer}"
    profile.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(profile))
    installation = "source-layer-must-remain-cutting-" + source_layer.lower()
    load_installation_key(installation, initialize=True)
    original, _, old_export, _, documents, source, *_ = _real_batch(tmp_path, count=1)
    doc = ezdxf.readfile(source)
    source_circle = next(iter(doc.modelspace().query("CIRCLE")))
    assert source_circle.dxf.layer == "CUTTING"
    source_circle.dxf.layer = source_layer
    doc.saveas(source)
    original["items"][0]["source_document_sha256"] = hashlib.sha256(
        source.read_bytes()
    ).hexdigest()
    original["request_digest"] = compute_wire_request_digest(original)
    state = tmp_path / "sealed-state"
    output = tmp_path / "existing-customer-dxf"
    state.mkdir()
    output.mkdir()
    engine_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
    provision_private_installation(
        installation, store_root=state, output_dir=output,
        source_documents=documents, expected_engine_sha256=engine_sha,
    )

    def run(operation, request, tag):
        wire = tmp_path / (tag + ".json")
        response = tmp_path / (tag + "-response.json")
        wire.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
        proc = subprocess.run([
            str(exe), "_private_installed", operation,
            "--installation-id", installation,
            "--request", str(wire), "--response", str(response),
        ], cwd=tmp_path, capture_output=True, text=True, timeout=180)
        return proc, (json.loads(response.read_text(encoding="utf-8"))
                      if response.is_file() else None)

    authorize_private_job(installation, original, engine_sha256=engine_sha)
    proc, receipt = run("prepare", original, "attested-noncut-prepare")
    assert proc.returncode == 0 and receipt["status"] == "success", (proc.stderr, receipt)
    export = _export_request_from_prepared(original, receipt)
    export["items"][0]["features"] = deepcopy(old_export["items"][0]["features"])
    fresh_frame = receipt["items"][0]["target_frames"][0]
    export["items"][0]["features"][0]["target_frame_id"] = fresh_frame["frame_id"]
    export["items"][0]["features"][0]["source_transform"]["target_dimensions_mm"] = (
        deepcopy(fresh_frame["finished_face_dimensions_mm"])
    )
    export["output"]["directory"] = str(output)
    export["output"]["overwrite"] = True
    export["request_digest"] = compute_wire_request_digest(export)
    original_customer_dxf = output / (receipt["items"][0]["physical_part_id"] + ".dxf")
    original_customer_dxf.write_bytes(b"previous-production-must-be-preserved")
    authorize_private_job(installation, export, engine_sha256=engine_sha)
    proc, denied = run("export", export, "attested-noncut-export")
    assert proc.returncode != 0
    assert denied is not None and denied["status"] == "failed", (proc.stderr, denied)
    assert denied["diagnostics"][0]["code"] == "WHD_SOURCE_UNVERIFIED"
    assert original_customer_dxf.read_bytes() == b"previous-production-must-be-preserved"
    assert list(output.glob("*.dxf")) == [original_customer_dxf]
    with DurableJobIdentityLedger(state)._connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE operation='export'"
        ).fetchone()[0] == 0


@pytest.mark.skipif(not WINDOWS, reason="actual packaged Windows Engine.exe + DPAPI required")
@pytest.mark.parametrize(("source_kind", "rotation"), [
    ("rect", 90),
    ("profile", 90),
])
def test_packaged_engine_real_original_rect_profile_cutting_native_dxf_and_replay(
    tmp_path, monkeypatch, source_kind, rotation,
):
    """Real installed EXE: source CUTTING shape and 90° transform reach final DXF.

    W-04 must not merely parse a shape in Python while failing to manufacture
    it with the frozen Engine.exe and WHD-only onedir resources.
    """
    from copy import deepcopy
    import ezdxf
    from integration_cli.request_canonical import compute_wire_request_digest
    from test_issue2378_prepare_batch import _export_request_from_prepared
    from test_issue2379_trusted_door_finalscene_batch import (
        _mixed_rect_batch, _mixed_source_profile_batch,
    )

    exe = Path(os.environ.get("WHD_TEST_ENGINE_EXE", ""))
    if not exe.is_file():
        pytest.skip("requires real packaged Windows WHD-Engine.exe")
    profile_dir = tmp_path / f"真實矩形輪廓來源 DPAPI {source_kind}"
    profile_dir.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(profile_dir))
    installation = "native-original-" + source_kind + "-90deg"
    load_installation_key(installation, initialize=True)

    batch = (
        _mixed_rect_batch(tmp_path, rotation=rotation)
        if source_kind == "rect" else
        _mixed_source_profile_batch(tmp_path, rotation=rotation)
    )
    original, _local_receipt, local_export, _root, sources, source, *_ = batch
    assert len(original["items"]) == 2
    assert {f["type"] for row in local_export["items"] for f in row["features"]} == {
        "circle", source_kind,
    }
    original_doc = ezdxf.readfile(source)
    for item in local_export["items"]:
        source_handle = item["features"][0]["source_transform"]["source_entity_refs"][0]
        entity = original_doc.entitydb.get(source_handle)
        assert entity is not None and entity.dxf.layer == "CUTTING"

    store = tmp_path / "W06 private-shape-durable-state"
    output = tmp_path / "W04 source-shape-native-DXF"
    store.mkdir()
    output.mkdir()
    engine_sha = hashlib.sha256(exe.read_bytes()).hexdigest()
    provision_private_installation(
        installation, store_root=store, output_dir=output,
        source_documents=sources, expected_engine_sha256=engine_sha,
    )

    def invoke(operation, payload, name):
        wire = tmp_path / f"{name}-wire.json"
        reply = tmp_path / f"{name}-response.json"
        wire.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        process = subprocess.run([
            str(exe), "_private_installed", operation,
            "--installation-id", installation,
            "--request", str(wire), "--response", str(reply),
        ], cwd=tmp_path, capture_output=True, text=True, timeout=180)
        result = json.loads(reply.read_text(encoding="utf-8")) if reply.is_file() else None
        return process, result

    authorize_private_job(installation, original, engine_sha256=engine_sha)
    proc, receipt = invoke("prepare", original, f"real-{source_kind}-prepare")
    assert proc.returncode == 0 and receipt["status"] == "success", (proc.stderr, receipt)
    assert len(receipt["items"]) == 2
    export = _export_request_from_prepared(original, receipt)
    for idx, old_item in enumerate(local_export["items"]):
        issued = receipt["items"][idx]["target_frames"][0]
        new_feature = deepcopy(old_item["features"][0])
        new_feature["target_frame_id"] = issued["frame_id"]
        new_feature["source_transform"]["target_dimensions_mm"] = deepcopy(
            issued["finished_face_dimensions_mm"]
        )
        export["items"][idx]["features"] = [new_feature]
    export["output"]["directory"] = str(output)
    export["request_digest"] = compute_wire_request_digest(export)
    authorize_private_job(installation, export, engine_sha256=engine_sha)
    proc, finished = invoke("export", export, f"real-{source_kind}-export")
    assert proc.returncode == 0 and finished["status"] == "success", (proc.stderr, finished)
    assert finished["manufacturing_verified"] is False
    assert len(finished["items"]) == 2
    files = {item["physical_part_id"]: Path(item["path"]) for item in finished["items"]}
    assert set(files) == {r["physical_part_id"] for r in receipt["items"]}
    for path in files.values():
        assert path.is_file() and path.parent == output
        assert ezdxf.readfile(path).modelspace().query('LINE[layer=="BEND"]')
    circle_part = ezdxf.readfile(files[receipt["items"][0]["physical_part_id"]])
    assert circle_part.modelspace().query('CIRCLE[layer=="CUTTING"]')
    shape_part = ezdxf.readfile(files[receipt["items"][1]["physical_part_id"]])
    closed_cutting = [
        p for p in shape_part.modelspace().query('LWPOLYLINE[layer=="CUTTING"]')
        if p.closed
    ]
    expected_vertex_count = 4 if source_kind == "rect" else 5
    assert any(len(p.get_points("xy")) == expected_vertex_count for p in closed_cutting)
    if source_kind == "rect":
        # Distinguish source RECT from the WHD exterior CUTTING contour.
        assert len(closed_cutting) >= 2
    immutable = {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in files.values()
    }
    replay = deepcopy(export)
    replay["request_id"] = "original-shape-90deg-transport-retry"
    proc, repeated = invoke("export", replay, f"real-{source_kind}-replay")
    assert proc.returncode == 0 and repeated == finished
    assert {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in files.values()
    } == immutable
    source.write_bytes(source.read_bytes() + b"\\nchanged-original-shape")
    proc, denied = invoke("export", replay, f"real-{source_kind}-stale")
    assert proc.returncode != 0 and denied["status"] == "failed"
    assert denied["diagnostics"][0]["code"] == "WHD_SOURCE_UNVERIFIED"
    assert {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in files.values()
    } == immutable


@pytest.mark.skipif(not WINDOWS, reason="real DPAPI + packaged WHD-Engine.exe required")
def test_packaged_engine_separately_authorized_rollback_after_crashed_two_dxf_export(
    tmp_path, monkeypatch,
):
    """Actual Windows EXE recovery cannot borrow an ordinary Export ticket.

    A half-applied journal recovers the original customer DXF bytes + mtime
    in a NEW process without rendering another DXF. Terminal replay is read-only.
    """
    from integration_cli.batch_commit_journal import DurableMultiDXFRollbackJournal
    from integration_cli.job_identity_ledger import DurableJobIdentityLedger
    from integration_cli.original_backup_manifest import DurableOriginalBackupEvidence
    from integration_cli.request_canonical import compute_wire_request_digest
    from integration_cli.private_worker_installation import authorize_private_recovery
    from test_issue2378_request_canonical import (
        _w06_request, _w06_real_output, _w06_staged_dxf,
    )

    exe = Path(os.environ.get("WHD_TEST_ENGINE_EXE", ""))
    assert exe.is_file(), "Windows packaged test requires real Engine.exe"
    profile = tmp_path / "WHD private recovery DPAPI"
    profile.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(profile))
    installation = "w06-real-exe-recovery"
    load_installation_key(installation, initialize=True)
    store, target = tmp_path / "state", tmp_path / "客戶 實際 DXF"
    store.mkdir()
    target.mkdir()
    customer = _w06_real_output(target / "part-one.dxf")
    before = customer.read_bytes(), customer.stat().st_mtime_ns
    staged = {
        "part-one": _w06_staged_dxf(target, "part-one"),
        "part-two": _w06_staged_dxf(target, "part-two"),
    }
    request = _w06_request(operation="export")
    request["output"]["directory"] = str(target)
    request["output"]["overwrite"] = True
    request["request_digest"] = compute_wire_request_digest(request)
    ledger = DurableJobIdentityLedger(store)
    assert ledger.claim(request).state == "new"
    ledger.reserve_output_directories(request, trusted_directories=[target])
    ledger.record_staged_batch_snapshot(
        request, trusted_output_dir=target, trusted_staged=staged, overwrite=True,
    )
    DurableOriginalBackupEvidence(ledger).create_verified_original_backups(
        request, trusted_output_dir=target,
    )
    journal = DurableMultiDXFRollbackJournal(ledger)
    journal.arm(request)
    with pytest.raises(SystemExit):
        journal.apply(
            request,
            after_replace=lambda i: (_ for _ in ()).throw(SystemExit()) if i == 1 else None,
        )
    assert (customer.read_bytes(), customer.stat().st_mtime_ns) != before
    assert not (target / "part-two.dxf").exists()

    source = _w06_real_output(tmp_path / "外部來源.dxf")
    exe_hash = hashlib.sha256(exe.read_bytes()).hexdigest()
    provision_private_installation(
        installation, store_root=store, output_dir=target,
        source_documents={"door-1": source}, expected_engine_sha256=exe_hash,
    )
    # A standard Export approval is deliberately not an approval to restore.
    authorize_private_job(installation, request, engine_sha256=exe_hash)
    wire = tmp_path / "unchanged-original-export.json"
    wire.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")

    def invoke(label, body=request):
        path = tmp_path / f"{label}-request.json"
        response = tmp_path / f"{label}-response.json"
        path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        process = subprocess.run([
            str(exe), "_private_installed", "recover-rollback",
            "--installation-id", installation,
            "--request", str(path), "--response", str(response),
        ], cwd=tmp_path, capture_output=True, text=True, timeout=120)
        return process, response

    refused, no_result = invoke("ordinary-export-ticket")
    assert refused.returncode == 4
    assert not no_result.exists()
    assert (customer.read_bytes(), customer.stat().st_mtime_ns) != before
    authorize_private_recovery(installation, request, engine_sha256=exe_hash)

    swapped = dict(request)
    swapped["job_id"] = "different-job"
    swapped["request_digest"] = compute_wire_request_digest(swapped)
    wrong, missing = invoke("wrong-original-job", swapped)
    assert wrong.returncode == 4 and not missing.exists()
    assert (customer.read_bytes(), customer.stat().st_mtime_ns) != before

    done, path = invoke("approved-rollback")
    assert done.returncode == 0, done.stderr[-1200:]
    outcome = json.loads(path.read_text(encoding="utf-8"))
    assert outcome["status"] == "rolled_back"
    assert outcome["manufacturing_verified"] is False
    assert outcome["request_digest"] == request["request_digest"]
    assert (customer.read_bytes(), customer.stat().st_mtime_ns) == before
    assert not (target / "part-two.dxf").exists()
    assert DurableJobIdentityLedger(store).claim(request).state == "rolled_back"

    again, replay = invoke("recover-result-lost-transport")
    assert again.returncode == 0, again.stderr[-1200:]
    assert json.loads(replay.read_text(encoding="utf-8")) == outcome
    assert (customer.read_bytes(), customer.stat().st_mtime_ns) == before
