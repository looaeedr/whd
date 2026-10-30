# -*- coding: utf-8 -*-
"""W-06 private Windows Worker HMAC key custody via current-user DPAPI.

The key is not a license key, a client JSON parameter or a build artifact.
It is generated only at first explicit trusted Worker initialization and
stored encrypted outside the onedir EXE/config.ini/customer directory.
Missing/corrupt existing custody never rekeys on a normal read: previously
issued prepare tokens must not silently change trust identity.

This owner is PRIVATE. Public cadsplit_worker prepare/export remain disabled
until authenticated job/prepare/export custody has separate Gate A evidence.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import os
from pathlib import Path
import re
import stat
import sys

from integration_cli.prepare_evidence import PrepareEvidenceError

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_FILENAME = "worker_hmac_v1.dpapi"
_ENVELOPE = b"WHD-W06-WORKER-KEY-v1\x00"
_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_UI_FORBIDDEN = 0x1


def _fail(detail: str) -> PrepareEvidenceError:
    # Do not include absolute profile paths, raw Windows errors or secret bytes.
    return PrepareEvidenceError("WHD_PREPARE_KEY_UNAVAILABLE", detail)


def _check_existing(path: Path, *, directory: bool) -> None:
    """Reject reparse points, hard-linked secret files and non-regular targets."""
    try:
        info = path.lstat()
        if info.st_file_attributes & _REPARSE or path.is_symlink():
            raise _fail("Worker key store uses an untrusted path alias")
        if directory:
            if not stat.S_ISDIR(info.st_mode):
                raise _fail("Worker key store is not a directory")
        elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise _fail("Worker encrypted key file is not a unique regular file")
    except OSError as exc:
        raise _fail("Worker key store is unreadable") from exc


def _check_ancestors(path: Path) -> None:
    for ancestor in (path, *path.parents):
        if ancestor == ancestor.parent:
            continue  # Drive root is owned by Windows.
        _check_existing(ancestor, directory=True)


def _store_root(installation_id: str, *, initialize: bool) -> Path:
    if sys.platform != "win32":
        raise _fail("Windows DPAPI is required for durable Worker key custody")
    if not isinstance(installation_id, str) or not _ID.fullmatch(installation_id):
        raise _fail("Trusted Worker installation identity is invalid")
    profile = os.environ.get("LOCALAPPDATA", "")
    if not profile or profile.startswith(("\\\\", "//")):
        raise _fail("Local Windows user profile unavailable")
    root = Path(profile)
    if not root.is_absolute():
        raise _fail("Local Windows user profile unavailable")
    _check_ancestors(root)
    # Opaque directory identifier, never a user-controlled filesystem path.
    identity = hashlib.sha256(installation_id.encode("ascii")).hexdigest()
    for label in ("WHD", "Engine", "install-" + identity):
        root = root / label
        if not root.exists() and not root.is_symlink():
            if not initialize:
                raise _fail("Worker installation key was never initialized")
            try:
                root.mkdir()
            except FileExistsError:
                pass
            except OSError as exc:
                raise _fail("Cannot create private Worker key directory") from exc
        _check_existing(root, directory=True)
    return root


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.c_void_p)]


def _blob(data: bytes) -> tuple[_Blob, ctypes.Array]:
    buf = ctypes.create_string_buffer(data)
    return _Blob(len(data), ctypes.cast(buf, ctypes.c_void_p)), buf


def _dpapi(payload: bytes, entropy: bytes, *, protect: bool) -> bytes:
    """Windows CryptProtectData / CryptUnprotectData, UI strictly forbidden."""
    if sys.platform != "win32":
        raise _fail("Windows DPAPI is required")
    crypt = ctypes.WinDLL("Crypt32.dll", use_last_error=True)
    kernel = ctypes.WinDLL("Kernel32.dll", use_last_error=True)
    api = crypt.CryptProtectData if protect else crypt.CryptUnprotectData
    # Using c_void_p for optional parameters; no UI and no machine-scope flag.
    api.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p,
                    ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.c_void_p,
                    wintypes.DWORD, ctypes.POINTER(_Blob)]
    api.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    source, source_buffer = _blob(payload)
    salt, salt_buffer = _blob(entropy)
    dest = _Blob()
    description = ctypes.c_void_p()
    try:
        if protect:
            success = api(ctypes.byref(source), None, ctypes.byref(salt),
                          None, None, _UI_FORBIDDEN, ctypes.byref(dest))
        else:
            # Second argument is LPWSTR* description on UnprotectData.
            success = api(ctypes.byref(source), ctypes.byref(description),
                          ctypes.byref(salt), None, None, _UI_FORBIDDEN,
                          ctypes.byref(dest))
        if not success or dest.cbData < 1 or not dest.pbData:
            raise _fail("Windows rejected the Worker installation key")
        return ctypes.string_at(dest.pbData, dest.cbData)
    finally:
        if dest.pbData:
            kernel.LocalFree(dest.pbData)
        if description.value:
            kernel.LocalFree(description)
        # Keep C buffers alive for the entire DPAPI call.
        del source_buffer, salt_buffer


def _entropy(installation_id: str) -> bytes:
    return hashlib.sha256(_ENVELOPE + installation_id.encode("ascii")).digest()


def load_installation_key(installation_id: str, *, initialize: bool = False) -> bytes:
    """Return same 32-byte installation key after process restart.

    initialize=True is ONLY for trusted installation bootstrap. Public JSON
    may not control this flag or installation_id. A valid existing key always
    wins, and missing/tampered records never regenerate on ordinary access.
    """
    folder = _store_root(installation_id, initialize=initialize)
    target = folder / _FILENAME
    entropy = _entropy(installation_id)
    if not target.exists() and not target.is_symlink():
        if not initialize:
            raise _fail("Worker installation key was never initialized")
        # No plaintext copy is ever written to disk or included in the EXE.
        sealed = _dpapi(os.urandom(32), entropy, protect=True)
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
            fd = os.open(target, flags, 0o600)
        except FileExistsError:
            pass  # Racing initializer: read and verify, never overwrite.
        except OSError as exc:
            raise _fail("Cannot initialize private Worker key") from exc
        else:
            with os.fdopen(fd, "wb") as output:
                output.write(sealed)
                output.flush()
                os.fsync(output.fileno())
    _check_existing(target, directory=False)
    try:
        size = target.stat().st_size
        if not 32 <= size <= 8192:
            raise _fail("Worker encrypted key has invalid length")
        sealed = target.read_bytes()
        secret = _dpapi(sealed, entropy, protect=False)
        if len(secret) != 32:
            raise _fail("Worker key length is invalid")
        return secret
    except OSError as exc:
        raise _fail("Cannot read private Worker key") from exc
