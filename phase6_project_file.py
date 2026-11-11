# -*- coding: utf-8 -*-
"""Phase6 all-in-one fold workspace project file support."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile

from ae_engine import manufacturing_api

PROJECT_SCHEMA_V1 = manufacturing_api.PROJECT_SCHEMA_V1
PROJECT_SCHEMA_V2 = manufacturing_api.PROJECT_SCHEMA_V2
PROJECT_SCHEMA_V3 = manufacturing_api.PROJECT_SCHEMA_V3
# Existing generic callers still construct v1 payloads. Receiving projects are
# promoted to v2 by write_project once ReceivingLayout is present.
PROJECT_SCHEMA = PROJECT_SCHEMA_V1
PROJECT_EXTENSION = ".p6fold"
PROJECT_CLASS = "Phase6.FoldProject"

def _normalize_authoritative_door_state(snapshot):
    """Compatibility adapter: Engine owns saved physical Door authority."""
    return manufacturing_api.normalize_authoritative_door_state(snapshot)


# Backward-compatible public Engine codec aliases: no GUI Feature parser.
_encode = manufacturing_api.encode_project_value
_as_vec2 = manufacturing_api.project_vec2_from_raw
_decode_feature = manufacturing_api.decode_project_feature
_decode = manufacturing_api.decode_project_value


def validate_project(payload, *, for_read=False):
    """Compatibility port: Engine owns the saved project schema decision."""
    return manufacturing_api.validate_operator_project_payload(
        payload, for_read=for_read,
    )


def _materialize_project_snapshot(snapshot):
    """Compatibility adapter: Engine owns saved source normalization."""
    return manufacturing_api.normalize_project_snapshot_authority(snapshot)


def write_project(path, payload):
    materialized = manufacturing_api.project_operator_project_for_write(payload)
    target = Path(path)
    if target.suffix.lower() != PROJECT_EXTENSION:
        target = target.with_suffix(PROJECT_EXTENSION)
    # Encode the authoritative Engine snapshot before touching the target.
    # Direct Path.write_text truncates the last verified project first: a
    # disk/full/interrupted write can destroy the only re-loadable source
    # from which 2D/3D/DXF must be regenerated.
    encoded = json.dumps(_encode(materialized), ensure_ascii=False, indent=2)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, pending = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stage:
            stage.write(encoded)
            stage.flush()
            os.fsync(stage.fileno())
        # Same-directory atomic replacement: retain the previous valid
        # .p6fold until the new complete Engine-normalized JSON is durable.
        os.replace(pending, target)
    finally:
        if os.path.exists(pending):
            os.unlink(pending)
    return target


def read_project(path):
    source = Path(path)
    raw = json.loads(source.read_text(encoding="utf-8"))
    return manufacturing_api.project_operator_project_for_read(_decode(raw))


def project_path_from_argv(argv):
    for raw in argv or ():
        try:
            path = Path(raw)
        except TypeError:
            continue
        if path.suffix.lower() == PROJECT_EXTENSION and path.is_file():
            return path
    return None


def windows_open_command(executable=None, *, script_path=None, frozen=None):
    executable = str(executable or sys.executable)
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        return f'"{executable}" "%1"'
    script = str(script_path or Path(__file__).with_name("gui.py"))
    return f'"{executable}" "{script}" "%1"'


def register_windows_file_association(*, executable=None, script_path=None, frozen=None):
    """Register .p6fold per-user; no administrator privilege is required."""
    if os.name != "nt":
        return False
    import winreg

    command = windows_open_command(executable, script_path=script_path, frozen=frozen)
    base = r"Software\Classes"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\.p6fold") as key:
        winreg.SetValueEx(key, None, 0, winreg.REG_SZ, PROJECT_CLASS)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + rf"\{PROJECT_CLASS}") as key:
        winreg.SetValueEx(key, None, 0, winreg.REG_SZ, "Phase6 折彎專案")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + rf"\{PROJECT_CLASS}\shell\open\command") as key:
        winreg.SetValueEx(key, None, 0, winreg.REG_SZ, command)
    return True
