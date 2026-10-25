"""#1959 isolated CADCraft v0.8.0 desktop control transport.

This is a bounded, opt-in adapter. It never imports entities into WHD, changes
a HoleEditorSession, or writes manufacturing DXF. Call from a background worker,
not Tk's event thread. The remote desktop server is not an HTTP endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass
import itertools
import json
import math
import socket
from typing import Any


class CadcraftControlError(RuntimeError):
    """No trustworthy control response: leave WHD and its source unchanged."""


@dataclass(frozen=True)
class CadcraftDrawingSnapshot:
    space: str
    entity_count: int
    entities: tuple[dict, ...]
    counts: dict[str, int]
    dirty: bool
    path: str | None = None


class CadcraftControlClient:
    """One JSON-line request per loopback connection, without implicit retries."""

    MAX_REPLY_BYTES = 8 * 1024 * 1024
    MAX_ENTITIES = 100

    def __init__(self, port: int, *, timeout: float = 3.0):
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise CadcraftControlError("CADCRAFT_INVALID_CONTROL_PORT")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise CadcraftControlError("CADCRAFT_INVALID_CONTROL_TIMEOUT")
        try:
            finite_timeout = float(timeout)
        except (OverflowError, ValueError) as exc:
            raise CadcraftControlError("CADCRAFT_INVALID_CONTROL_TIMEOUT") from exc
        if not math.isfinite(finite_timeout) or finite_timeout <= 0:
            raise CadcraftControlError("CADCRAFT_INVALID_CONTROL_TIMEOUT")
        self.port = port
        self.timeout = finite_timeout
        self._ids = itertools.count(1)

    def request(self, method: str, params: dict | None = None) -> Any:
        """Return a reply's result only after exact id/error/framing validation.

        All failures are fail-closed; a timeout after send MAY have executed.
        Never automatically retry a drawing command on any ambiguous failure.
        """
        allowed = {"ping", "control.methods", "engine.commands",
                   "drawing.inspect", "engine.execute"}
        if (not isinstance(method, str) or method not in allowed
                or params is not None and not isinstance(params, dict)):
            raise CadcraftControlError("CADCRAFT_CONTROL_METHOD_NOT_ALLOWED")
        # Narrow engine.execute to the commands this isolated bridge actually
        # owns. A TCP method allowlist alone would still permit SAVEAS/ERASE.
        if method == "engine.execute":
            command = (params or {}).get("command")
            if (not isinstance(command, str)
                    or command not in {"new", "document.bytes", "circle", "pline"}):
                raise CadcraftControlError("CADCRAFT_ENGINE_COMMAND_NOT_ALLOWED")
        ident = next(self._ids)
        try:
            wire = (json.dumps({"id": ident, "method": method,
                                "params": params or {}},
                               allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise CadcraftControlError("CADCRAFT_INVALID_COMMAND_PARAMETERS") from exc
        if len(wire) > 1024 * 1024:
            raise CadcraftControlError("CADCRAFT_COMMAND_TOO_LARGE")
        try:
            with socket.create_connection(("127.0.0.1", self.port), self.timeout) as conn:
                conn.settimeout(self.timeout)
                conn.sendall(wire)
                with conn.makefile("rb") as incoming:
                    raw = incoming.readline(self.MAX_REPLY_BYTES + 1)
        except (OSError, TimeoutError) as exc:
            raise CadcraftControlError("CADCRAFT_CONTROL_UNCERTAIN_MAY_HAVE_RUN") from exc
        if not raw or len(raw) > self.MAX_REPLY_BYTES or not raw.endswith(b"\n"):
            raise CadcraftControlError("CADCRAFT_CONTROL_INCOMPLETE_REPLY")
        try:
            reply = json.loads(raw.decode("utf-8"),
                               parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (UnicodeError, ValueError, TypeError) as exc:
            raise CadcraftControlError("CADCRAFT_CONTROL_INVALID_JSON") from exc
        if not isinstance(reply, dict) or reply.get("id") != ident or not isinstance(reply.get("ok"), bool):
            raise CadcraftControlError("CADCRAFT_CONTROL_REPLY_ID_OR_STATUS")
        if not reply["ok"]:
            state = reply.get("state")
            if state == "not-run":
                raise CadcraftControlError("CADCRAFT_COMMAND_NOT_RUN:" + str(reply.get("error", ""))[:200])
            raise CadcraftControlError("CADCRAFT_COMMAND_UNCERTAIN_MAY_HAVE_RUN:" + str(reply.get("error", ""))[:200])
        if "result" not in reply:
            raise CadcraftControlError("CADCRAFT_CONTROL_MISSING_RESULT")
        return reply["result"]

    def probe(self) -> dict:
        if self.request("ping") != "pong":
            raise CadcraftControlError("CADCRAFT_UNEXPECTED_PING")
        methods = self.request("control.methods")
        commands = self.request("engine.commands")
        if not isinstance(methods, list) or not isinstance(commands, list):
            raise CadcraftControlError("CADCRAFT_UNKNOWN_COMMAND_CATALOG")
        available = {row.get("method") for row in methods if isinstance(row, dict)}
        if not {"drawing.inspect", "engine.execute"}.issubset(available):
            raise CadcraftControlError("CADCRAFT_REQUIRED_METHOD_UNAVAILABLE")
        return {"method_count": len(methods), "command_count": len(commands)}

    def inspect(self, *, limit: int = MAX_ENTITIES) -> CadcraftDrawingSnapshot:
        """Reject truncated/unsupported snapshots: not yet a manufacturing import."""
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= self.MAX_ENTITIES:
            raise CadcraftControlError("CADCRAFT_INSPECTION_LIMIT_INVALID")
        result = self.request("drawing.inspect", {"entities": True, "limit": limit})
        if not isinstance(result, dict):
            raise CadcraftControlError("CADCRAFT_INSPECTION_NOT_OBJECT")
        rows = result.get("entities")
        counts = result.get("counts")
        total = result.get("entityCount")
        skipped = result.get("skipped")
        if (not isinstance(rows, list) or not isinstance(counts, dict)
                or isinstance(total, bool) or not isinstance(total, int) or total < 0
                or not isinstance(skipped, dict)
                or isinstance(skipped.get("count"), bool)
                or not isinstance(skipped.get("count"), int)
                or skipped["count"] != 0):
            raise CadcraftControlError("CADCRAFT_INSPECTION_INCOMPLETE_OR_SKIPPED")
        if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in counts.values()):
            raise CadcraftControlError("CADCRAFT_INVALID_ENTITY_COUNTS")
        if sum(counts.values()) != len(rows) or len(rows) > limit:
            raise CadcraftControlError("CADCRAFT_INSPECTION_TRUNCATED")
        if total < len(rows):
            raise CadcraftControlError("CADCRAFT_INSPECTION_COUNT_INCONSISTENT")
        handles = set()
        for row in rows:
            if (not isinstance(row, dict)
                    or not isinstance(row.get("handle"), str)
                    or not isinstance(row.get("type"), str)
                    or not isinstance(row.get("layer"), str)
                    or not isinstance(row.get("geometry"), dict)):
                raise CadcraftControlError("CADCRAFT_INSPECTION_UNSUPPORTED_ENTITY")
            if row["handle"] in handles:
                raise CadcraftControlError("CADCRAFT_DUPLICATE_ENTITY_HANDLE")
            handles.add(row["handle"])
        if (not isinstance(result.get("space"), str)
                or not isinstance(result.get("dirty"), bool)
                or result.get("path") is not None and not isinstance(result["path"], str)):
            raise CadcraftControlError("CADCRAFT_INSPECTION_UNKNOWN_DOCUMENT_STATE")
        return CadcraftDrawingSnapshot(
            space=result["space"], entity_count=total,
            entities=tuple(rows), counts=dict(counts), dirty=result["dirty"],
            path=result.get("path"),
        )

    def execute_whd_draw(self, instructions: tuple) -> CadcraftDrawingSnapshot:
        """Only send existing WHD-resolved instructions into an EMPTY isolated drawing.

        No automatic rollback is asserted: if any reply is ambiguous, the caller
        must discard this external document rather than replaying the command.
        """
        from tools.issue1959_whd_cadcraft_command_draw import (
            DrawInstruction, _number, _ring,
        )
        if not isinstance(instructions, tuple) or not 1 <= len(instructions) <= self.MAX_ENTITIES:
            raise CadcraftControlError("CADCRAFT_INVALID_DRAW_BATCH")
        operations = []
        for item in instructions:
            if not isinstance(item, DrawInstruction):
                raise CadcraftControlError("CADCRAFT_NOT_WHD_RESOLVED_INSTRUCTION")
            if item.kind == "circle" and len(item.points) == 1:
                x, y = item.points[0]
                coords = [_number(x), _number(y)]
                radius = _number(item.radius)
                if radius <= 0:
                    raise CadcraftControlError("CADCRAFT_INVALID_CIRCLE")
                operations.append(("circle", {"center": coords, "radius": radius}))
            elif item.kind in ("rectangle", "profile"):
                pts = tuple(tuple(_number(v) for v in pt) for pt in item.points)
                _ring(pts)
                operations.append(("pline", {"vertices": [list(p) for p in pts],
                                             "closed": True}))
            else:
                raise CadcraftControlError("CADCRAFT_UNSUPPORTED_DRAW_INSTRUCTION")
        initial = self.inspect()
        if initial.entity_count != 0 or initial.entities or initial.dirty:
            raise CadcraftControlError("CADCRAFT_DOCUMENT_NOT_ISOLATED_EMPTY")
        if initial.space.lower() not in ("model",):
            raise CadcraftControlError("CADCRAFT_NOT_MODEL_SPACE")
        for command, payload in operations:
            self.request("engine.execute", {"command": command, "params": payload})
        final = self.inspect()
        if len(final.entities) != len(operations):
            raise CadcraftControlError("CADCRAFT_DRAW_ENTITY_COUNT_NOT_VERIFIED")
        # Raw snapshot is inspection evidence, not geometric parity or WHD Features.
        return final
