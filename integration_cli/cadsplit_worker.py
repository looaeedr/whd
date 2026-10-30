# -*- coding: utf-8 -*-
"""WHD-owned, Tk-free CADSplit Worker CLI boundary (#2377 / W-01).

This entry point does not implement manufacturing. W-03 / W-04 install the
prepare/export execution handlers only after their canonical acceptance gates.
A schema accepted by this process is NOT a manufacturing authorization.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

PROTOCOL_VERSION = "1.0.0"
SCHEMA_ROOT = Path(__file__).resolve().parent / "schemas"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MAX_REQUEST_BYTES = 16 * 1024 * 1024
MAX_BATCH_ITEMS = 20
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
# Metadata is intentionally source-only: never a signed release or EXE claim.
_SOURCE_VERSION = "source-only-unreleased"


class WorkerFailure(Exception):
    def __init__(self, code: str, message: str, *, exit_code: int = 3):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-JSON numeric constant: {value}")


def _strict_json(source: str) -> Any:
    return json.loads(
        source,
        object_pairs_hook=_no_duplicate_keys,
        parse_constant=_reject_constant,
    )


def _validator(name: str) -> Draft202012Validator:
    path = SCHEMA_ROOT / name
    definition = _strict_json(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(definition)
    return Draft202012Validator(definition)


def _read_request(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file() or path.is_symlink():
            raise WorkerFailure("WHD_REQUEST_UNREADABLE", "request must be a regular file", exit_code=4)
        size = path.stat().st_size
        if size < 1 or size > MAX_REQUEST_BYTES:
            raise WorkerFailure("WHD_REQUEST_SIZE_INVALID", "request is empty or too large", exit_code=4)
        request = _strict_json(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise WorkerFailure("WHD_REQUEST_UNREADABLE", f"request read failed: {exc}", exit_code=4) from exc
    except (UnicodeError, ValueError) as exc:
        raise WorkerFailure("WHD_JSON_INVALID", f"invalid UTF-8 JSON: {exc}", exit_code=2) from exc
    if not isinstance(request, dict):
        raise WorkerFailure("WHD_SCHEMA_INVALID", "request must be an object", exit_code=2)
    return request


def _git_commit() -> str:
    """Read exact source SHA; packaging must supply a verified manifest in W-05."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPOSITORY_ROOT, capture_output=True, text=True,
            check=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise WorkerFailure("WHD_BUILD_UNATTESTED", "verified build identity is unavailable", exit_code=4) from exc
    sha = proc.stdout.strip()
    if not COMMIT_RE.fullmatch(sha):
        raise WorkerFailure("WHD_BUILD_UNATTESTED", "invalid source build identity", exit_code=4)
    return sha


def _source_fingerprint() -> str:
    """Deterministic source code hash in development mode, NOT an EXE hash."""
    digest = hashlib.sha256()
    paths = sorted((REPOSITORY_ROOT / "ae_engine").rglob("*.py"))
    paths.append(Path(__file__).resolve())
    if not paths or not (REPOSITORY_ROOT / "ae_engine").is_dir():
        raise WorkerFailure("WHD_ENGINE_UNAVAILABLE", "manufacturing package is unavailable", exit_code=4)
    for path in paths:
        if path.is_symlink() or not path.is_file():
            raise WorkerFailure("WHD_ENGINE_UNAVAILABLE", "untrusted source code path", exit_code=4)
        relative = path.relative_to(REPOSITORY_ROOT).as_posix()
        content = path.read_bytes()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _packaged_identity() -> dict[str, Any]:
    # PyInstaller's --contents-directory . puts metadata and baseline beside
    # the actual EXE. Never fall back to Git or an unverified manifest.
    try:
        from packaged_identity import PackageIdentityError, verify_manifest
        return verify_manifest(Path(sys.executable).resolve().parent)
    except (ImportError, ValueError, OSError) as exc:
        raise WorkerFailure(
            "WHD_BUILD_UNATTESTED",
            f"packaged Engine identity/resource validation failed: {exc}",
            exit_code=4,
        ) from exc


def _identity() -> tuple[str, str, str]:
    if getattr(sys, "frozen", False):
        manifest = _packaged_identity()
        return (
            manifest["engine_commit"],
            manifest["build_id"],
            manifest["engine_sha256"],
        )
    sha = _git_commit()
    return sha, f"source-only-{sha[:16]}", _source_fingerprint()


def _capabilities(commit: str, build_id: str, code_hash: str) -> dict[str, Any]:
    # W-03/04/05/06 must replace source-only metadata with verified
    # build/resource manifests BEFORE enabling any capability.
    flags = {
        key: False for key in (
            "batch_prepare", "batch_export", "atomic_batch",
            "internal_verify_on_export", "idempotent_job_submission",
            "output_path_locking", "job_result_readback",
            "per_part_transactions", "cancellation", "crash_recovery",
        )
    }
    result = {
        "protocol_version": PROTOCOL_VERSION,
        "operation": "capabilities",
        "installation_id": "source-only-" + commit[:16],
        "engine_version": _SOURCE_VERSION,
        "engine_commit": commit,
        "build_id": build_id,
        # Source tree hash only. No EXE is claimed to exist.
        "engine_sha256": code_hash,
        "resource_revision": None,
        "registry_sha256": None,
        "baseline_manifest_sha256": None,
        "policy_sha256": None,
        "coordinate_contract_revision": "1",
        "min_client_version": "1.0.0",
        "max_batch_items": MAX_BATCH_ITEMS,
        "supported_part_kinds": [],
        "capability_flags": flags,
        "capabilities": [],
        "resource_health": {
            "registry": "invalid", "baseline": "invalid", "policy": "invalid"
        },
        "job_result_readback": {
            "available": False, "store_root": "not-implemented",
            "manifest_name": "job_manifest.json"
        },
    }
    if getattr(sys, "frozen", False):
        # Resource integrity does not authorize manufacturing: all capability
        # flags and supported kinds stay FALSE/EMPTY until W-03/04/06 Gate A.
        manifest = _packaged_identity()
        if (
            manifest["engine_commit"] != commit
            or manifest["build_id"] != build_id
            or manifest["engine_sha256"] != code_hash
        ):
            raise WorkerFailure("WHD_BUILD_UNATTESTED", "packaged metadata changed", exit_code=4)
        result["installation_id"] = "w05-private-" + commit[:16]
        result["engine_version"] = "w05-private-onedir"
        result["resource_revision"] = manifest["resource_revision"]
        for field in ("registry_sha256", "baseline_manifest_sha256", "policy_sha256"):
            result[field] = manifest[field]
        result["resource_health"] = {"registry": "ready", "baseline": "ready", "policy": "ready"}
    _validator("capabilities_v1.schema.json").validate(result)
    return result


def _diagnostic(code: str, message: str, *, item_count: int | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message, "retryable": False}
    if item_count is not None:
        error["context"] = {"item_count": item_count}
    return error


def _failure_response(
    operation: str, commit: str, build_id: str,
    failure: WorkerFailure, request: dict[str, Any] | None = None
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "operation": operation,
        "status": "failed",
        "engine_commit": commit,
        "build_id": build_id,
        "manufacturing_verified": False,
        "items": [],
        "diagnostics": [_diagnostic(failure.code, str(failure))],
    }
    if request is not None:
        for key in ("client_installation_id", "request_id", "job_id", "request_digest"):
            value = request.get(key)
            if not isinstance(value, str):
                continue
            if key == "request_digest":
                valid = re.fullmatch(r"[a-f0-9]{64}", value) is not None
            elif key in {"request_id", "job_id"}:
                valid = re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value) is not None
            else:
                valid = 1 <= len(value) <= 256
            if valid:
                response[key] = value
    _validator("response_v1.schema.json").validate(response)
    return response


def _execute_request(
    operation: str, path: Path, commit: str, build_id: str
) -> tuple[dict[str, Any], int]:
    request: dict[str, Any] | None = None
    try:
        request = _read_request(path)
        if request.get("operation") != operation:
            raise WorkerFailure("WHD_OPERATION_MISMATCH", "operation does not match CLI", exit_code=2)
        _validator("request_v1.schema.json").validate(request)
        items = request["items"]
        if len(items) > MAX_BATCH_ITEMS:
            raise WorkerFailure("WHD_BATCH_TOO_LARGE", "batch exceeds current CLI item limit", exit_code=2)
        # Zero import or initialization of Tk/AE/Registry here. W-03 and W-04
        # will connect a single once-per-batch manufacturing execution context.
        raise WorkerFailure(
            "WHD_OPERATION_NOT_IMPLEMENTED",
            "manufacturing handler is not certified; no files were exported",
            exit_code=3,
        )
    except ValidationError as exc:
        failure = WorkerFailure("WHD_SCHEMA_INVALID", f"invalid protocol: {exc.message}", exit_code=2)
    except WorkerFailure as exc:
        failure = exc
    return _failure_response(operation, commit, build_id, failure, request), failure.exit_code


def _write_response(path: Path, result: dict[str, Any]) -> None:
    """Create a new response atomically; never replace an existing customer file."""
    if path.suffix.lower() != ".json":
        raise WorkerFailure("WHD_RESPONSE_PATH_INVALID", "response suffix must be .json", exit_code=4)
    parent = path.parent.resolve(strict=True)
    dest = parent / path.name
    if not parent.is_dir() or dest.exists() or dest.is_symlink():
        raise WorkerFailure("WHD_RESPONSE_PATH_INVALID", "response path is unsafe or occupied", exit_code=4)
    if parent == REPOSITORY_ROOT or REPOSITORY_ROOT in parent.parents:
        raise WorkerFailure("WHD_RESPONSE_PATH_INVALID", "cannot write inside installation source", exit_code=4)
    encoded = (json.dumps(result, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n").encode("utf-8")
    fd, staged = tempfile.mkstemp(prefix=".whd-response-", suffix=".tmp", dir=str(parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        # Link is atomic and fails rather than clobbering an existing response.
        os.link(staged, dest)
    except FileExistsError as exc:
        raise WorkerFailure("WHD_RESPONSE_EXISTS", "response already exists", exit_code=4) from exc
    finally:
        Path(staged).unlink(missing_ok=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="WHD-Engine", description="WHD-owned headless Worker (safe disabled source mode)")
    commands = parser.add_subparsers(dest="operation", required=True)
    for name in ("capabilities", "prepare", "export"):
        command = commands.add_parser(name)
        if name != "capabilities":
            command.add_argument("--request", type=Path, required=True)
        command.add_argument("--response", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.response.exists() or args.response.is_symlink():
        print("WHD_RESPONSE_EXISTS: refusing to overwrite a response", file=sys.stderr)
        return 4
    try:
        commit, build_id, code_hash = _identity()
        if args.operation == "capabilities":
            data = _capabilities(commit, build_id, code_hash)
            exit_code = 0
        else:
            data, exit_code = _execute_request(args.operation, args.request, commit, build_id)
        _write_response(args.response, data)
        return exit_code
    except (WorkerFailure, OSError, UnicodeError, ValueError) as exc:
        code = exc.code if isinstance(exc, WorkerFailure) else "WHD_IO_FAILURE"
        print(f"{code}: {exc}", file=sys.stderr)
        return exc.exit_code if isinstance(exc, WorkerFailure) else 4


if __name__ == "__main__":
    raise SystemExit(main())
