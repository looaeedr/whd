"""#2517: EndCap bottom FW family policy is an Engine API, not GUI manufacturing."""
from __future__ import annotations

from dataclasses import dataclass
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import apply_cabinet_family_endcap_policy, manufacturing_api
from ae_engine.cabinet_types import policy as family_policy
from gui_modules.application import fold_designer_manufacturing_projection as gui_adapter


@dataclass(frozen=True)
class CornerPolicy:
    fw: float = 25.0
    bottom_fw: float | None = None
    selection: str = "operator-corner"


def test_public_engine_api_owns_receiving_family_bottom_fw(monkeypatch):
    calls = []
    def family_bottom(source, state, *, thickness, default_fw):
        calls.append((source, state, thickness, default_fw))
        return 28.0
    monkeypatch.setattr(family_policy, "supports_bottom_wrap_controls", lambda source: source == "受電箱")
    monkeypatch.setattr(family_policy, "effective_endcap_bottom_fw", family_bottom)
    original = CornerPolicy(bottom_fw=21.0)
    snapshot = {"active_type": "three_piece"}
    result = apply_cabinet_family_endcap_policy(
        original, "head", family_source="受電箱", structure_state=snapshot, thickness=2.0
    )
    assert apply_cabinet_family_endcap_policy is manufacturing_api.apply_cabinet_family_endcap_policy
    assert result.bottom_fw == 28.0
    assert original.bottom_fw == 21.0
    assert result.selection == original.selection
    assert calls == [("受電箱", snapshot, 2.0, 21.0)]


def test_vault_and_non_endcap_inputs_never_change_family_geometry(monkeypatch):
    def no_call(*args, **kwargs):
        raise AssertionError("unexpected family geometry calculation")
    monkeypatch.setattr(family_policy, "effective_endcap_bottom_fw", no_call)
    policy = CornerPolicy(bottom_fw=None)
    assert apply_cabinet_family_endcap_policy(
        policy, "head", family_source="金庫型", thickness=2.0
    ) is policy
    assert apply_cabinet_family_endcap_policy(
        policy, "door", family_source="受電箱", thickness=2.0
    ) is policy
    assert apply_cabinet_family_endcap_policy(
        None, "tail", family_source="受電箱"
    ) is None


def test_gui_forwards_current_inputs_through_public_engine_api(monkeypatch):
    seen = []
    sentinel = object()
    def engine(policy, part, *, family_source, thickness, structure_state):
        seen.append((policy, part, family_source, thickness, structure_state))
        return sentinel
    monkeypatch.setattr(manufacturing_api, "apply_cabinet_family_endcap_policy", engine)
    class Var:
        def get(self):
            return "2.5"
    state = {"active_type": "receiving-three-piece"}
    host = SimpleNamespace(
        _current_cabinet_type_name=lambda: "受電箱",
        t_var=Var(),
        workspace_controller=SimpleNamespace(box_body_structure_state=lambda: state),
    )
    policy = CornerPolicy()
    assert gui_adapter._apply_cabinet_family_endcap_policy(host, policy, "tail") is sentinel
    assert seen == [(policy, "tail", "受電箱", 2.5, state)]
    assert gui_adapter._apply_cabinet_family_endcap_policy(
        host, None, "tail",
    ) is None
    assert len(seen) == 1
    src = inspect.getsource(gui_adapter._apply_cabinet_family_endcap_policy)
    assert "manufacturing_api.apply_cabinet_family_endcap_policy(" in src
    assert "effective_endcap_bottom_fw" not in src
    assert "supports_bottom_wrap_controls" not in src
    assert "bottom_fw=" not in src


def test_missing_gui_thickness_defers_factory_default_to_engine(monkeypatch):
    calls = []
    class Var:
        def get(self):
            raise ValueError("not available")
    monkeypatch.setattr(manufacturing_api, "apply_cabinet_family_endcap_policy",
                        lambda policy, part, **kwargs: calls.append(kwargs) or policy)
    host = SimpleNamespace(
        _current_cabinet_type_name=lambda: "金庫型",
        t_var=Var(),
        workspace_controller=SimpleNamespace(box_body_structure_state=lambda: {}),
    )
    p = CornerPolicy()
    assert gui_adapter._apply_cabinet_family_endcap_policy(host, p, "head") is p
    assert calls[0]["thickness"] is None
