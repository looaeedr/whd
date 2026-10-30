# -*- coding: utf-8 -*-
"""Private, preprovisioned Windows installation custody for WHD-Engine.exe.

The regular CADSplit CLI cannot provision this record. This adapter reads
ONLY a Worker-owned, DPAPI-key-HMAC-authenticated record, then binds its
package resources / original DXF paths / output directory to private dispatch.
Not a public manufacturing authorization or Gate A certification.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.worker_key_custody import (
    _store_root, _check_existing, _check_ancestors, load_installation_key,
)
from integration_cli.private_worker_dispatch import TrustedWorkerExecution

_FILE = "trusted_sources_v1.json"
_PREFIX = b"WHD-W06-TRUSTED-INSTALL-CONTEXT-v1\x00"


def _deny(message="trusted installed Worker context unavailable"):
    raise PrepareEvidenceError("WHD_JOB_STORE_UNAVAILABLE", message)


def _trusted_dir(value: Path) -> Path:
    if not isinstance(value, Path) or not value.is_absolute():
        _deny()
    _check_ancestors(value)
    if not value.is_dir():
        _deny()
    return value


def _trusted_file(value: Path) -> Path:
    if not isinstance(value, Path) or not value.is_absolute():
        _deny()
    _check_ancestors(value.parent)
    _check_existing(value, directory=False)
    return value


def _signed_payload(key: bytes, payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hmac.new(key, _PREFIX + raw, hashlib.sha256).hexdigest()


def provision_private_installation(
    installation_id: str, *, store_root: Path, output_dir: Path,
    source_documents: dict[str, Path], expected_engine_sha256: str,
) -> None:
    """Trusted installer-only API; NEVER exposed by EXE CLI or wire JSON.

    Installs one immutable source/output custody mapping. Reprovisioning and
    untrusted paths are rejected rather than silently changing job authority.
    """
    folder, _ = _store_root(installation_id, initialize=False)
    key = load_installation_key(installation_id)
    if (not isinstance(expected_engine_sha256, str) or len(expected_engine_sha256) != 64
            or any(c not in "0123456789abcdef" for c in expected_engine_sha256)):
        _deny()
    store = _trusted_dir(store_root)
    output = _trusted_dir(output_dir)
    if not isinstance(source_documents, dict) or not source_documents:
        _deny()
    mapping = {}
    for item, src in source_documents.items():
        if not isinstance(item, str) or not item or len(item) > 128:
            _deny()
        mapping[item] = str(_trusted_file(src))
    payload = {
        "schema": "whd-private-install-custody-v1",
        "store_root": str(store),
        "output_dir": str(output),
        "source_documents": mapping,
        "engine_sha256": expected_engine_sha256,
    }
    record = {"payload": payload, "hmac": _signed_payload(key, payload)}
    destination = folder / _FILE
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(destination, flags, 0o600)
    except OSError as exc:
        raise PrepareEvidenceError("WHD_JOB_STORE_UNAVAILABLE", "installation already provisioned or not writable") from exc
    with os.fdopen(fd, "wb") as output:
        output.write(json.dumps(record, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        output.flush()
        os.fsync(output.fileno())


def load_private_execution(installation_id: str, *, engine_sha256: str) -> TrustedWorkerExecution:
    """Reopen pinned installer custody and validate actual EXE hash."""
    folder, _ = _store_root(installation_id, initialize=False)
    key = load_installation_key(installation_id)
    path = folder / _FILE
    _check_existing(path, directory=False)
    try:
        if path.stat().st_size > 256 * 1024:
            _deny()
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict) or set(record) != {"payload", "hmac"}:
            _deny()
        data, tag = record["payload"], record["hmac"]
        if not isinstance(data, dict) or not isinstance(tag, str):
            _deny()
        if (not hmac.compare_digest(tag, _signed_payload(key, data))
                or set(data) != {"schema","store_root","output_dir","source_documents","engine_sha256"}
                or data["schema"] != "whd-private-install-custody-v1"
                or not hmac.compare_digest(data["engine_sha256"], engine_sha256)):
            _deny()
        sources = data["source_documents"]
        if not isinstance(sources, dict) or not sources:
            _deny()
        return TrustedWorkerExecution(
            resource_root=(Path(sys._MEIPASS) if getattr(sys, "frozen", False)
                           else Path(__file__).resolve().parents[1]),
            store_root=_trusted_dir(Path(data["store_root"])),
            output_dir=_trusted_dir(Path(data["output_dir"])),
            source_documents={item: _trusted_file(Path(path)) for item, path in sources.items()},
            worker_key=key,
            engine_sha256=engine_sha256,
        )
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        raise PrepareEvidenceError("WHD_JOB_STORE_UNAVAILABLE", "installed Worker custody is invalid") from exc
