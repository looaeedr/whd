# -*- coding: utf-8 -*-
"""Permanent guard for the 2026-11-01 installed Worker/EXE retirement."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()


def test_installed_worker_exe_owner_files_are_removed():
    retired = (
        "integration_cli/private_worker_installation.py",
        "integration_cli/public_installed_adapter.py",
        "integration_cli/worker_key_custody.py",
        "integration_cli/packaged_identity.py",
        ".github/workflows/whd-engine-private-windows-exe.yml",
    )
    assert all(not (ROOT / path).exists() for path in retired)


def test_source_worker_has_no_installed_or_frozen_entrypoint():
    source = (ROOT / "integration_cli/cadsplit_worker.py").read_text(encoding="utf-8")
    for forbidden in (
        "_private_installed",
        "--installation-id",
        "public_installed_adapter",
        "private_worker_installation",
        "worker_key_custody",
        "packaged_identity",
        "sys._MEIPASS",
    ):
        assert forbidden not in source


def test_no_python_module_reimports_retired_installed_owners():
    forbidden = (
        "integration_cli.private_worker_installation",
        "integration_cli.public_installed_adapter",
        "integration_cli.worker_key_custody",
        "integration_cli.packaged_identity",
        "from integration_cli import private_worker_installation",
        "from integration_cli import public_installed_adapter",
    )
    for path in ROOT.rglob("*.py"):
        if path.resolve() == SELF or ".git" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in forbidden:
            assert token not in text, f"{path.relative_to(ROOT)} reintroduces {token}"
