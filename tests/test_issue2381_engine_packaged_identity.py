# -*- coding: utf-8 -*-
"""#2381 W-05: actual resource bytes, not a guessed EXE identity.

The independent Windows CI builds/starts WHD-Engine.exe; these focused tests
defend manifest semantics without claiming public prepare/export readiness.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from integration_cli.packaged_identity import (
    PackageIdentityError, verify_manifest, write_manifest,
)

COMMIT = "a" * 40


@pytest.fixture
def fake_private_engine(tmp_path: Path) -> Path:
    root = tmp_path / "WHD-Engine 資源 空白"
    (root / "基準檔" / "截角資料庫").mkdir(parents=True)
    (root / "基準檔" / "金庫型").mkdir(parents=True)
    (root / "integration_cli" / "schemas").mkdir(parents=True)
    for name in ("request_v1.schema.json", "response_v1.schema.json", "capabilities_v1.schema.json"):
        (root / "integration_cli" / "schemas" / name).write_text('{"type":"object"}', encoding="utf-8")
    (root / "WHD-Engine.exe").write_bytes(b"private worker binary for manifest test")
    (root / "config.ini").write_text("[WHD]\nframe=25\n", encoding="utf-8")
    (root / "基準檔" / "截角資料庫" / "certified_relief_rules.json").write_bytes(
        b'{"rules":[{"id":"actual-resource"}]}'
    )
    (root / "基準檔" / "金庫型" / "門.dxf").write_bytes(b"0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n")
    (root / "基準檔" / "金庫型" / "封頭尾.dxf").write_bytes(b"0\nEOF\n")
    return root


def test_manifest_pins_actual_exe_registry_baselines_policy(fake_private_engine):
    root = fake_private_engine
    written = write_manifest(root, COMMIT)
    reread = verify_manifest(root)
    assert reread == written
    assert reread["engine_commit"] == COMMIT
    assert reread["build_id"].startswith("w05-private-" + COMMIT[:12])
    assert reread["engine_sha256"] == hashlib.sha256(
        (root / "WHD-Engine.exe").read_bytes()
    ).hexdigest()
    assert reread["registry_sha256"] == hashlib.sha256(
        (root / "基準檔" / "截角資料庫" / "certified_relief_rules.json").read_bytes()
    ).hexdigest()
    assert len(reread["baseline_manifest_sha256"]) == 64
    assert len(reread["schema_manifest_sha256"]) == 64
    assert len(reread["resource_revision"]) == 64
    assert not any(k in reread for k in ("manufacturing_verified", "capability_flags"))


@pytest.mark.parametrize("path", [
    "WHD-Engine.exe", "config.ini",
    "基準檔/截角資料庫/certified_relief_rules.json",
    "基準檔/金庫型/門.dxf",
    "integration_cli/schemas/capabilities_v1.schema.json",
])
def test_any_bundled_resource_change_refuses_capabilities(fake_private_engine, path):
    write_manifest(fake_private_engine, COMMIT)
    target = fake_private_engine / path
    target.write_bytes(target.read_bytes() + b"TAMPER")
    with pytest.raises(PackageIdentityError, match="WHD_PACKAGE_HASH_MISMATCH"):
        verify_manifest(fake_private_engine)


def test_missing_and_modified_manifest_fail_closed(fake_private_engine):
    root = fake_private_engine
    with pytest.raises(PackageIdentityError):
        verify_manifest(root)
    write_manifest(root, COMMIT)
    with pytest.raises(PackageIdentityError, match="ALREADY_EXISTS"):
        write_manifest(root, COMMIT)
    path = root / "WHD_ENGINE_BUILD.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["engine_commit"] = "b" * 40
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(PackageIdentityError, match="WHD_PACKAGE_HASH_MISMATCH"):
        verify_manifest(root)
    path.unlink()
    with pytest.raises(PackageIdentityError):
        verify_manifest(root)


def test_missing_baseline_fails_even_if_manifest_used_to_pass(fake_private_engine):
    root = fake_private_engine
    write_manifest(root, COMMIT)
    (root / "基準檔" / "金庫型" / "門.dxf").unlink()
    with pytest.raises(PackageIdentityError, match="HASH_MISMATCH"):
        verify_manifest(root)


def test_source_only_cli_does_not_fabricate_packaged_identity():
    from integration_cli.cadsplit_worker import PROTOCOL_VERSION, _SOURCE_VERSION
    assert PROTOCOL_VERSION == "1.0.0"
    assert _SOURCE_VERSION == "source-only-unreleased"
