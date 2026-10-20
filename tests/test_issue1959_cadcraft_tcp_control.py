"""#1959 CADCraft real JSON-lines contract, tested without touching user files."""
from __future__ import annotations

from contextlib import contextmanager
import json
import socket
import threading
import time

import pytest

from gui_modules.editors.cadcraft_control_bridge import (
    CadcraftControlClient, CadcraftControlError,
)
from tools.issue1959_whd_cadcraft_command_draw import DrawInstruction


class FakeControl:
    """Real loopback sockets, not a mocked CadcraftControlClient.request."""

    def __init__(self, responder):
        self.responder = responder
        self.requests = []
        self.ready = threading.Event()
        self.stop = threading.Event()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.sock.settimeout(0.05)
        self.port = self.sock.getsockname()[1]
        self.worker = threading.Thread(target=self.serve, daemon=True)
        self.worker.start()
        assert self.ready.wait(2)

    def serve(self):
        self.ready.set()
        while not self.stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with conn:
                conn.settimeout(0.5)
                try:
                    with conn.makefile("rb") as source:
                        wire = source.readline(1024 * 1024 + 1)
                    request = json.loads(wire.decode("utf-8"))
                    self.requests.append(request)
                    result = self.responder(request)
                    if result is not None:
                        result.setdefault("id", request["id"])
                        conn.sendall((json.dumps(result) + "\n").encode("utf-8"))
                except (BrokenPipeError, ConnectionResetError, OSError):
                    continue

    def close(self):
        self.stop.set()
        self.sock.close()
        self.worker.join(2)


@contextmanager
def fake_server(responder):
    server = FakeControl(responder)
    try:
        yield server
    finally:
        server.close()


def snapshot(*, n=0, rows=None, skipped=0, space="Model", dirty=False):
    if rows is None:
        rows = [
            {"handle": format(i + 1, "X"), "type": "Circle", "layer": "0",
             "geometry": {"Circle": {"center": [40, 50], "radius": 5}}}
            for i in range(n)
        ]
    return {
        "space": space, "dirty": dirty,
        "entityCount": len(rows), "counts": {"Circle": len(rows)},
        "entities": rows, "skipped": {"count": skipped, "sections": {}},
    }


def test_ping_catalog_and_complete_inspection_over_real_loopback():
    def responder(req):
        data = {
            "ping": "pong",
            "control.methods": [{"method": "drawing.inspect"},
                                {"method": "engine.execute"}],
            "engine.commands": [{"id": "circle"}, {"id": "pline"}],
            "drawing.inspect": snapshot(n=2),
        }
        return {"ok": True, "result": data[req["method"]]}

    with fake_server(responder) as server:
        client = CadcraftControlClient(server.port)
        assert client.probe() == {"method_count": 2, "command_count": 2}
        got = client.inspect(limit=3)
        assert len(got.entities) == 2 and got.entity_count == 2
        assert got.entities[0]["handle"] == "1"
        assert [r["id"] for r in server.requests] == [1, 2, 3, 4]
        assert server.requests[-1]["params"] == {"entities": True, "limit": 3}
        assert {r["method"] for r in server.requests} == {
            "ping", "control.methods", "engine.commands", "drawing.inspect",
        }


@pytest.mark.parametrize("invalid", [
    {**snapshot(n=2), "counts": {"Circle": 3}},
    {**snapshot(n=1), "skipped": {"count": 1, "sections": {"ENTITIES": 1}}},
    {**snapshot(n=1), "entityCount": 0},
    {**snapshot(n=1), "entities": [{"handle": "x", "type": "Circle", "layer": "0"}]},
    {**snapshot(n=1), "entities": [snapshot(n=1)["entities"][0]] * 2,
     "counts": {"Circle": 2}, "entityCount": 2},
])
def test_incomplete_or_unknown_inspection_fails_closed(invalid):
    with fake_server(lambda req: {"ok": True, "result": invalid}) as server:
        with pytest.raises(CadcraftControlError):
            CadcraftControlClient(server.port).inspect()


@pytest.mark.parametrize("status,expected", [
    ({"ok": False, "state": "not-run", "error": "busy"}, "NOT_RUN"),
    ({"ok": False, "state": "may-have-run", "error": "timeout"}, "MAY_HAVE_RUN"),
    ({"ok": True, "id": 999, "result": "pong"}, "REPLY_ID"),
    ({"ok": True}, "MISSING_RESULT"),
])
def test_control_errors_never_replay_a_request(status, expected):
    with fake_server(lambda req: dict(status)) as server:
        with pytest.raises(CadcraftControlError, match=expected):
            CadcraftControlClient(server.port).request("ping")
        assert len(server.requests) == 1


def test_tcp_timeout_is_uncertain_and_never_retried():
    def slow(req):
        time.sleep(0.08)
        return {"ok": True, "result": "pong"}

    with fake_server(slow) as server:
        with pytest.raises(CadcraftControlError, match="MAY_HAVE_RUN"):
            CadcraftControlClient(server.port, timeout=0.02).request("ping")
        assert len(server.requests) == 1


def test_whd_commands_only_act_on_clean_empty_model_and_never_touch_session():
    sent = []

    def responder(req):
        if req["method"] == "drawing.inspect":
            return {"ok": True, "result": snapshot(n=len(sent))}
        assert req["method"] == "engine.execute"
        sent.append(req["params"])
        return {"ok": True, "result": {"changed": True}}

    with fake_server(responder) as server:
        client = CadcraftControlClient(server.port)
        proof = client.execute_whd_draw((
            DrawInstruction("circle", ((45.0, 60.0),), 5.0),
            DrawInstruction("profile", ((80.0, 80.0), (100.0, 80.0),
                                        (100.0, 100.0), (80.0, 100.0))),
        ))
        assert len(proof.entities) == 2
        assert [p["command"] for p in sent] == ["circle", "pline"]
        assert sent[0]["params"] == {"center": [45.0, 60.0], "radius": 5.0}
        assert sent[1]["params"]["closed"] is True
        assert [r["method"] for r in server.requests] == [
            "drawing.inspect", "engine.execute", "engine.execute", "drawing.inspect",
        ]


@pytest.mark.parametrize("invalid", [
    DrawInstruction("circle", ((40, 50),), -5),
    DrawInstruction("circle", ((40, float("nan")),), 5),
    DrawInstruction("profile", ((1, 1), (5, 5), (9, 9))),
    DrawInstruction("unknown", ((1, 1),), 5),
])
def test_invalid_whd_instruction_is_rejected_before_any_network_write(invalid):
    with fake_server(lambda req: {"ok": True, "result": snapshot()}) as server:
        with pytest.raises((CadcraftControlError, ValueError)):
            CadcraftControlClient(server.port).execute_whd_draw((invalid,))
        assert server.requests == []


def test_existing_dirty_drawing_blocks_all_commands():
    with fake_server(lambda req: {"ok": True, "result": snapshot(dirty=True)}) as server:
        with pytest.raises(CadcraftControlError, match="NOT_ISOLATED_EMPTY"):
            CadcraftControlClient(server.port).execute_whd_draw(
                (DrawInstruction("circle", ((2, 3),), 1),)
            )
        assert [r["method"] for r in server.requests] == ["drawing.inspect"]


def test_untrusted_method_cannot_escape_allowlist():
    client = CadcraftControlClient(1024)
    with pytest.raises(CadcraftControlError, match="NOT_ALLOWED"):
        client.request("app.save", {"path": "original.dxf"})
