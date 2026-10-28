# -*- coding: utf-8 -*-
"""#2377 Tk-free CADSplit Worker CLI acceptance, independent of installed EXE."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "integration_cli" / "cadsplit_worker.py"
SCHEMAS = ROOT / "integration_cli" / "schemas"
HEX = "a" * 64


def _run(tmp_path: Path, operation: str, *, request=None, response_name="回應.json", env=None):
    response = tmp_path / response_name
    argv = [sys.executable, str(WORKER), operation]
    if operation in {"prepare", "export"}:
        request_path = tmp_path / "request-來源.json"
        if isinstance(request, bytes):
            request_path.write_bytes(request)
        else:
            request_path.write_text(
                json.dumps(request, ensure_ascii=False), encoding="utf-8"
            )
        argv.extend(["--request", str(request_path)])
    argv.extend(["--response", str(response)])
    result = subprocess.run(
        argv, cwd=tmp_path, capture_output=True, text=True, encoding="utf-8",
        env=env, timeout=40,
    )
    payload = json.loads(response.read_text(encoding="utf-8")) if response.is_file() else None
    return result, payload, response


def _schema(name):
    return Draft202012Validator(json.loads((SCHEMAS / name).read_text(encoding="utf-8")))


def _prepare(items=1):
    return {
        "protocol_version": "1.0.0",
        "client_installation_id": "cad-installation-1",
        "request_id": "q-0001",
        "job_id": "job-0001",
        "request_digest": HEX,
        "operation": "prepare",
        "coordinate_contract_revision": "1",
        "items": [
            {
                "item_id": f"門片-{index:02}",
                "source_document_sha256": HEX,
                "part": {
                    "kind": "door",
                    "cabinet_family": "金庫型",
                    "source_part_ref": f"DXF-door-{index:02}",
                    "dimension_semantics": "cabinet_outer",
                    "dimensions_mm": {
                        "width": 500.0, "height": 600.0, "thickness": 2.0,
                    },
                },
            }
            for index in range(items)
        ],
    }


def test_only_three_public_commands_with_headless_help(tmp_path):
    result = subprocess.run(
        [sys.executable, str(WORKER), "--help"],
        cwd=tmp_path, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0
    assert "{capabilities,prepare,export}" in result.stdout
    assert "verify" not in result.stdout
    unknown = subprocess.run(
        [sys.executable, str(WORKER), "verify", "--response", "unwanted.json"],
        cwd=tmp_path, capture_output=True, text=True, timeout=30,
    )
    assert unknown.returncode != 0
    assert not (tmp_path / "unwanted.json").exists()


def test_capabilities_are_source_only_and_never_enable_manufacturing(tmp_path):
    proc, payload, _ = _run(tmp_path, "capabilities")
    assert proc.returncode == 0, proc.stderr
    _schema("capabilities_v1.schema.json").validate(payload)
    assert payload["supported_part_kinds"] == []
    assert payload["capabilities"] == []
    assert not any(payload["capability_flags"].values())
    assert payload["resource_revision"] is None
    assert payload["registry_sha256"] is None
    assert payload["baseline_manifest_sha256"] is None
    assert payload["policy_sha256"] is None
    assert payload["build_id"].startswith("source-only-")
    assert payload["engine_version"] == "source-only-unreleased"


@pytest.mark.parametrize("item_count", [1, 20])
def test_prepare_batch_does_not_start_manufacturing_or_write_dxf(tmp_path, item_count):
    proc, payload, response = _run(tmp_path, "prepare", request=_prepare(item_count))
    assert proc.returncode == 3, proc.stderr
    _schema("response_v1.schema.json").validate(payload)
    assert payload["status"] == "failed"
    assert payload["manufacturing_verified"] is False
    assert payload["items"] == []
    assert payload["diagnostics"][0]["code"] == "WHD_OPERATION_NOT_IMPLEMENTED"
    assert response.read_text(encoding="utf-8").count("門") == 0
    assert len(list(tmp_path.glob("*.dxf"))) == 0


def test_malformed_duplicate_keys_and_bad_utf8_get_safe_error_json(tmp_path):
    for index, data in enumerate((
        b'{"job_id":"a","job_id":"b"}',
        b'\xff\xfe\xfa',
        b'{"operation":"prepare", "value": NaN}',
    )):
        proc, payload, _ = _run(
            tmp_path, "prepare", request=data, response_name=f"error-{index}.json"
        )
        assert proc.returncode == 2, proc.stderr
        _schema("response_v1.schema.json").validate(payload)
        assert payload["status"] == "failed"
        assert payload["diagnostics"][0]["code"] == "WHD_JSON_INVALID"


def test_malformed_correlation_ids_are_not_echoed_as_valid_receipt(tmp_path):
    request = _prepare()
    request["job_id"] = "不合規 job ID"
    request["request_digest"] = "BAD-digest"
    proc, payload, _ = _run(tmp_path, "prepare", request=request)
    assert proc.returncode == 2, proc.stderr
    _schema("response_v1.schema.json").validate(payload)
    assert "job_id" not in payload
    assert "request_digest" not in payload
    assert payload["manufacturing_verified"] is False


def test_existing_response_is_never_overwritten(tmp_path):
    protected = tmp_path / "客戶回應.json"
    protected.write_text('{"keep": "顧客原始內容"}', encoding="utf-8")
    before = protected.read_bytes()
    proc, payload, _ = _run(tmp_path, "capabilities", response_name=protected.name)
    assert proc.returncode == 4
    assert payload == {"keep": "顧客原始內容"}
    assert protected.read_bytes() == before


def test_export_cannot_commit_without_canonical_prepare(tmp_path):
    request = _prepare()
    request["operation"] = "export"
    proc, payload, _ = _run(tmp_path, "export", request=request)
    assert proc.returncode == 2
    _schema("response_v1.schema.json").validate(payload)
    assert payload["diagnostics"][0]["code"] == "WHD_SCHEMA_INVALID"
    assert list(tmp_path.glob("*.dxf")) == []


def test_worker_from_non_install_cwd_rejects_tk_cadsplit_ae_import(tmp_path):
    # Python injects this standard sitecustomize before executing the worker.
    # If a prohibited package is imported by the CLI, the process must fail.
    guard = tmp_path / "sitecustomize.py"
    guard.write_text(
        "import builtins\n"
        "_orig = builtins.__import__\n"
        "def guard(name, *args, **kwargs):\n"
        "    if name.split('.')[0] in {'tkinter', 'ae_engine', 'CADSplit'}:\n"
        "        raise RuntimeError('forbidden Worker dependency: ' + name)\n"
        "    return _orig(name, *args, **kwargs)\n"
        "builtins.__import__ = guard\n",
        encoding="utf-8",
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(tmp_path)
    proc, payload, _ = _run(
        tmp_path, "prepare", request=_prepare(20), response_name="獨立工作.json", env=env
    )
    assert proc.returncode == 3, proc.stderr
    assert payload["diagnostics"][0]["code"] == "WHD_OPERATION_NOT_IMPLEMENTED"
    assert payload["manufacturing_verified"] is False


def test_cli_requires_separate_request_and_response_paths(tmp_path):
    result = subprocess.run(
        [sys.executable, str(WORKER), "prepare", "--response", "only.json"],
        cwd=tmp_path, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 2
    assert not (tmp_path / "only.json").exists()
