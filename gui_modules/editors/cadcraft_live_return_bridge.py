"""#1959 read CADCraft *unsaved live* document bytes without changing WHD Session.

A live TCP drawing is not manufacturing truth. This adapter captures one
immutable, isolated DXF candidate and passes it to the EXISTING validated
manual-return ticket/Session path. Call it off Tk's event thread.
"""
from __future__ import annotations

import base64
from dataclasses import replace
from hashlib import sha256
import os
from pathlib import Path
import tempfile

from .cadcraft_control_bridge import CadcraftControlClient, CadcraftControlError
from .cadcraft_manual_hole_return_bridge import ManualReturnTicket
from tools.issue1959_whd_cadcraft_command_draw import CadcraftCommandProofError

_MAX_BYTES = 3_000_000


def reserve_cadcraft_control_port() -> int:
    """Reserve an ephemeral loopback port for one immediately spawned GUI.

    The OS may reuse the port between reservation and CADCraft bind; the caller
    must check process and verify document provenance before accepting data.
    """
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _same_document(expected: Path, actual: str | None) -> bool:
    if not actual:
        return False
    try:
        return os.path.normcase(str(Path(actual).resolve())) == os.path.normcase(
            str(Path(expected).resolve(strict=True))
        )
    except (OSError, ValueError):
        return False


def capture_unsaved_cadcraft_return(
    ticket: ManualReturnTicket, *, port: int, client=None, process=None,
) -> ManualReturnTicket:
    """Produce a new throwaway DXF ticket from live CADCraft; NO Session edits.

    Requirements: a WHD-issued source ticket, the SAME active CADCraft file,
    complete Model inspection with stable before/after entities, and bounded
    DXF bytes from the CADCraft engine. No manual user Save is required.
    """
    if not isinstance(ticket, ManualReturnTicket):
        raise CadcraftCommandProofError("WHD_CADCRAFT_RETURN_TICKET_REQUIRED")
    if process is not None and process.poll() is not None:
        raise CadcraftCommandProofError("CADCRAFT_CONTROL_PROCESS_EXITED")
    origin = Path(ticket.output).resolve(strict=True)
    try:
        source = origin.read_bytes()
    except OSError as exc:
        raise CadcraftCommandProofError("CADCRAFT_ISSUED_SOURCE_NOT_READABLE") from exc
    if sha256(source).hexdigest() != ticket.original_sha256:
        raise CadcraftCommandProofError("CADCRAFT_ISSUED_SOURCE_CHANGED")
    original_state = ticket.session.snapshot()
    if (ticket.session.has_active_edit or original_state.context_key != ticket.context_key
            or original_state.features != ticket.original):
        raise CadcraftCommandProofError("STALE_OR_MODIFIED_WHD_SESSION")
    control = client if client is not None else CadcraftControlClient(port, timeout=4.0)
    before = control.inspect()
    if (before.space.lower() != "model" or not _same_document(origin, before.path)
            or len(before.entities) > 100):
        raise CadcraftCommandProofError("CADCRAFT_CONTROL_WRONG_ACTIVE_DOCUMENT")
    try:
        reply = control.request("engine.execute", {
            "command": "document.bytes",
            "params": {"format": "dxf", "version": 2010},
        })
    except CadcraftControlError as exc:
        raise CadcraftCommandProofError("CADCRAFT_CONTROL_BYTES_UNAVAILABLE") from exc
    after = control.inspect()
    if before != after:
        raise CadcraftCommandProofError("CADCRAFT_CONTROL_DRAWING_CHANGED_DURING_CAPTURE")
    if ticket.session.snapshot() != original_state:
        raise CadcraftCommandProofError("WHD_SESSION_CHANGED_DURING_LIVE_CAPTURE")
    if not isinstance(reply, dict) or not isinstance(reply.get("data"), str):
        raise CadcraftCommandProofError("CADCRAFT_CONTROL_MISSING_DOCUMENT_BYTES")
    encoded = reply["data"]
    if len(encoded) > 4_100_000:
        raise CadcraftCommandProofError("CADCRAFT_CONTROL_TOO_MANY_BYTES")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise CadcraftCommandProofError("CADCRAFT_CONTROL_INVALID_BASE64") from exc
    if (not raw or len(raw) > _MAX_BYTES
            or type(reply.get("bytes")) is not int or reply["bytes"] != len(raw)):
        raise CadcraftCommandProofError("CADCRAFT_CONTROL_BYTE_COUNT_MISMATCH")
    # Do NOT overwrite the WHD-issued DXF, CADCraft's disk file, or project.
    directory = Path(tempfile.mkdtemp(prefix="whd-cadcraft-live-", dir=origin.parent))
    candidate = directory / "whd-live-return.dxf"
    try:
        with candidate.open("xb") as stream:
            stream.write(raw)
    except Exception:
        candidate.unlink(missing_ok=True)
        raise
    return replace(ticket, output=candidate)
