# -*- coding: utf-8 -*-
"""#2380 W-06 Windows DPAPI HMAC custody: real native test, not a mock.

No actual customer/profile data is touched: LOCALAPPDATA is redirected to the
CI temporary user's private directory for each test. Public worker remains
disabled, and this test never serializes the plaintext key.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path
import subprocess
import sys

import pytest

from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.worker_key_custody import load_installation_key

WINDOWS = sys.platform == "win32"


def _setup(monkeypatch, tmp_path):
    profile = tmp_path / "中文 工作金鑰 private profile"
    profile.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(profile))
    return profile


def _failure(exc, code="WHD_PREPARE_KEY_UNAVAILABLE"):
    assert exc.value.code == code


def test_other_platforms_and_missing_key_fail_closed(monkeypatch, tmp_path):
    if WINDOWS:
        _setup(monkeypatch, tmp_path)
        with pytest.raises(PrepareEvidenceError) as exc:
            load_installation_key("private-worker-install-a")
        _failure(exc)
        assert not (tmp_path / "worker_hmac_v1.dpapi").exists()
    else:
        with pytest.raises(PrepareEvidenceError) as exc:
            load_installation_key("private-worker-install-a", initialize=True)
        _failure(exc)


@pytest.mark.skipif(not WINDOWS, reason="requires native Windows CryptProtectData")
def test_real_dpapi_restart_reuses_key_without_exposing_plaintext(monkeypatch, tmp_path):
    profile = _setup(monkeypatch, tmp_path)
    install = "trusted-install-cad-1"
    key = load_installation_key(install, initialize=True)
    assert isinstance(key, bytes) and len(key) == 32
    assert key == load_installation_key(install)
    assert key != load_installation_key("trusted-install-cad-2", initialize=True)
    files = list(profile.rglob("worker_hmac_v1.dpapi"))
    assert len(files) == 2
    ciphertext = files[0].read_bytes()
    assert len(ciphertext) > len(key)
    assert key not in ciphertext
    # Real new Windows Python process, same authenticated OS user.
    code = (
        "import hashlib,hmac,sys;"
        "from integration_cli.worker_key_custody import load_installation_key;"
        "print(hmac.new(load_installation_key(sys.argv[1]),"
        "b'WHD-W06-RESTART-TEST',hashlib.sha256).hexdigest())"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, install],
        cwd=Path(__file__).resolve().parents[1], env=os.environ.copy(),
        capture_output=True, text=True, check=True,
    )
    expected = hmac.new(key, b"WHD-W06-RESTART-TEST", hashlib.sha256).hexdigest()
    assert result.stdout.strip() == expected
    assert result.stderr == ""
    assert ciphertext == files[0].read_bytes()


@pytest.mark.skipif(not WINDOWS, reason="requires Windows user-DPAPI")
def test_tampered_or_missing_encrypted_key_never_implicitly_rotates(monkeypatch, tmp_path):
    profile = _setup(monkeypatch, tmp_path)
    name = "install-custody-tamper"
    original = load_installation_key(name, initialize=True)
    file, = profile.rglob("worker_hmac_v1.dpapi")
    original_ciphertext = file.read_bytes()
    file.write_bytes(original_ciphertext[:-1] + bytes([original_ciphertext[-1] ^ 0x40]))
    for bootstrap in (False, True):
        with pytest.raises(PrepareEvidenceError) as exc:
            load_installation_key(name, initialize=bootstrap)
        _failure(exc)
    assert file.read_bytes() != original_ciphertext
    assert original != file.read_bytes()
    file.unlink()
    with pytest.raises(PrepareEvidenceError) as exc:
        load_installation_key(name)
    _failure(exc)


@pytest.mark.skipif(not WINDOWS, reason="requires Windows user-DPAPI")
def test_wrong_installation_id_cannot_read_copied_protected_key(monkeypatch, tmp_path):
    profile = _setup(monkeypatch, tmp_path)
    one, two = "cad-owner-a", "cad-owner-b"
    first = load_installation_key(one, initialize=True)
    second = load_installation_key(two, initialize=True)
    files = sorted(profile.rglob("worker_hmac_v1.dpapi"))
    assert len(files) == 2
    first_file = next(path for path in files if load_installation_key(one) == first
                      and path.parent.name == "install-" + hashlib.sha256(one.encode()).hexdigest())
    second_file = next(path for path in files if path != first_file)
    second_file.write_bytes(first_file.read_bytes())
    with pytest.raises(PrepareEvidenceError) as exc:
        load_installation_key(two)
    _failure(exc)
    assert load_installation_key(one) == first
    assert second != load_installation_key(one)


@pytest.mark.skipif(not WINDOWS, reason="requires Windows user-DPAPI")
def test_reparse_parent_and_hardlink_are_not_trusted(monkeypatch, tmp_path):
    profile = _setup(monkeypatch, tmp_path)
    install = "reparse-check"
    load_installation_key(install, initialize=True)
    original, = profile.rglob("worker_hmac_v1.dpapi")
    hardlink = original.parent / "extra-link.dpapi"
    os.link(original, hardlink)
    with pytest.raises(PrepareEvidenceError) as exc:
        load_installation_key(install)
    _failure(exc)


def test_invalid_trusted_identity_refused(monkeypatch, tmp_path):
    if WINDOWS:
        _setup(monkeypatch, tmp_path)
    for name in ("", "../escape", "nested/name", "contains spaces", "bad\\name"):
        with pytest.raises(PrepareEvidenceError) as exc:
            load_installation_key(name, initialize=True)
        _failure(exc)
