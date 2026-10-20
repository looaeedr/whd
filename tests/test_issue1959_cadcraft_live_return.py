"""#1959 live CADCraft TCP capture must rejoin existing WHD Session atomically."""
from __future__ import annotations

import base64
from dataclasses import replace
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine.sheetmetal_features import (
    CircleFeature, FeatureAnchor, Vec2, feature_surface_from_rect,
)
from gui_modules.editors.cadcraft_control_bridge import CadcraftDrawingSnapshot
from gui_modules.editors.cadcraft_live_return_bridge import (
    capture_unsaved_cadcraft_return,
)
from gui_modules.editors.cadcraft_manual_hole_return_bridge import (
    create_manual_return_ticket, stage_manual_cadcraft_return,
)
from phase6_hole_editor_session import HoleEditorAction, Phase6HoleEditorSession
from tools.issue1959_whd_cadcraft_command_draw import CadcraftCommandProofError


class StableClient:
    def __init__(self, observation, content):
        self.observation = observation
        self.content = content
        self.calls = []

    def inspect(self):
        self.calls.append("inspect")
        return self.observation

    def request(self, method, params):
        self.calls.append((method, params))
        return {
            "data": base64.b64encode(self.content).decode("ascii"),
            "bytes": len(self.content),
        }


def setup(tmp_path):
    surface = feature_surface_from_rect("1959-tcp", Vec2(0, 0), Vec2(200, 200))
    original = CircleFeature(10, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(40, 40))
    features = [original]
    session = Phase6HoleEditorSession("1959-tcp", features)
    issued = tmp_path / "whd-issued.dxf"
    doc = ezdxf.new("R2010", units=ezdxf.units.MM)
    doc.modelspace().add_circle((40, 40), 5)
    doc.saveas(issued)
    ticket = create_manual_return_ticket(
        output=issued, features=features, session=session,
        surface=surface, width=200, height=200,
    )
    proposed = tmp_path / "cadcraft-in-memory.dxf"
    doc = ezdxf.new("R2010", units=ezdxf.units.MM)
    doc.modelspace().add_circle((45, 37), 5)
    doc.saveas(proposed)
    payload = proposed.read_bytes()
    observation = CadcraftDrawingSnapshot(
        space="Model", entity_count=1,
        entities=({"handle": "AB", "type": "Circle", "layer": "0",
                   "geometry": {"Circle": {"center": [45, 37], "radius": 5}}},),
        counts={"Circle": 1}, dirty=True, path=str(issued),
    )
    return original, features, session, issued, ticket, payload, observation


def test_live_bytes_reuse_whd_session_without_manual_save(tmp_path):
    original, features, session, issued, ticket, payload, observation = setup(tmp_path)
    checksum = issued.read_bytes()
    control = StableClient(observation, payload)
    captured = capture_unsaved_cadcraft_return(ticket, port=32001, client=control)
    assert issued.read_bytes() == checksum
    assert captured.output != issued and captured.output.read_bytes() == payload
    assert features == [original] and not session.has_active_edit
    assert control.calls == [
        "inspect",
        ("engine.execute", {"command": "document.bytes",
                            "params": {"format": "dxf", "version": 2010}}),
        "inspect",
    ]
    pending = stage_manual_cadcraft_return(captured)
    assert pending.moves == ((0, 5, -3),)
    assert session.has_active_edit
    pending.confirm()
    assert features[0].offset == Vec2(45, 37)
    session.execute(HoleEditorAction.undo())
    assert features == [original]


@pytest.mark.parametrize("variant,error", [
    ("other_document", "WRONG_ACTIVE_DOCUMENT"),
    ("wrong_space", "WRONG_ACTIVE_DOCUMENT"),
    ("broken_base64", "INVALID_BASE64"),
    ("changed_snapshot", "CHANGED_DURING_CAPTURE"),
    ("dead_process", "PROCESS_EXITED"),
])
def test_untrusted_or_changed_live_state_fails_without_session_edits(tmp_path, variant, error):
    original, features, session, issued, ticket, payload, observation = setup(tmp_path)
    control = StableClient(observation, payload)
    process = SimpleNamespace(poll=lambda: None)
    if variant == "other_document":
        control.observation = replace(observation, path=str(tmp_path / "another.dxf"))
    if variant == "wrong_space":
        control.observation = replace(observation, space="Layout1")
    if variant == "broken_base64":
        def bad_request(*a, **kw):
            return {"data": "!!", "bytes": 1}
        control.request = bad_request
    if variant == "changed_snapshot":
        old_inspect = control.inspect
        counter = [0]
        def changed():
            counter[0] += 1
            return old_inspect() if counter[0] == 1 else replace(observation, dirty=False)
        control.inspect = changed
    if variant == "dead_process":
        process = SimpleNamespace(poll=lambda: 5)
    with pytest.raises(CadcraftCommandProofError, match=error):
        capture_unsaved_cadcraft_return(
            ticket, port=32001, client=control, process=process
        )
    assert features == [original] and not session.has_active_edit


def test_dirty_issued_file_and_stale_whd_session_are_rejected(tmp_path):
    original, features, session, issued, ticket, payload, observation = setup(tmp_path)
    control = StableClient(observation, payload)
    issued.write_bytes(issued.read_bytes() + b"tamper")
    with pytest.raises(CadcraftCommandProofError, match="ISSUED_SOURCE_CHANGED"):
        capture_unsaved_cadcraft_return(ticket, port=32001, client=control)
    assert features == [original] and not session.has_active_edit
