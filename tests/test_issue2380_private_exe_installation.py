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
