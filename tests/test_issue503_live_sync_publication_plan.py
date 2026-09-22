from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

import phase6_sync_envelope as envelope


def test_issue503_publication_plan_contract_is_frozen_and_pure():
    plan_type = envelope.LiveSyncPublicationPlan
    assert dataclasses.is_dataclass(plan_type)
    assert plan_type.__dataclass_params__.frozen

    tree = ast.parse(
        Path("phase6_sync_envelope.py").read_text(encoding="utf-8"),
        filename="phase6_sync_envelope.py",
    )
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    forbidden = {
        name for name in imports
        if name == "fold_designer_bridge"
        or name == "tkinter"
        or name.startswith("tkinter.")
        or "manufacturing" in name
        or "renderer" in name
    }
    assert forbidden == set()


def test_issue503_equivalent_state_does_not_publish_or_increment_revision():
    state = {"settings": {"w": 640.0}, "assembly_relief": {}}
    fingerprint = envelope.stable_fingerprint(state)
    plan = envelope.plan_live_sync_envelope(
        current_state=state,
        previous_state=state,
        previous_fingerprint=fingerprint,
        current_revision=7,
        active_transaction_id="",
        host_relief_present=True,
        host_relief={},
        force=True,
    )
    assert plan.should_publish is False
    assert plan.next_revision == 7
    assert plan.delta == {}
    assert plan.payload is None


def test_issue503_force_repairs_only_proven_host_relief_delta_once():
    state = {
        "settings": {"w": 640.0},
        "assembly_relief": {"enabled": True, "parts": {"divider": {"x": 1}}},
    }
    fingerprint = envelope.stable_fingerprint(state)
    host_relief = {"enabled": True, "parts": {}}

    plan = envelope.plan_live_sync_envelope(
        current_state=state,
        previous_state=state,
        previous_fingerprint=fingerprint,
        current_revision=2,
        active_transaction_id="tx:2",
        host_relief_present=True,
        host_relief=host_relief,
        force=True,
    )

    assert plan.should_publish is True
    assert plan.next_revision == 3
    assert plan.transaction_id == "tx:2"
    assert "assembly_relief" in plan.delta
    assert plan.host_relief_repair == state["assembly_relief"]

    with pytest.raises(TypeError):
        plan.payload["revision"] = 999


def test_issue503_default_transaction_id_and_delta_are_planned_purely():
    before = {"settings": {"w": 600.0}, "assembly_relief": {}}
    after = {"settings": {"w": 640.0}, "assembly_relief": {}}

    plan = envelope.plan_live_sync_envelope(
        current_state=after,
        previous_state=before,
        previous_fingerprint=envelope.stable_fingerprint(before),
        current_revision=4,
        active_transaction_id="",
        host_relief_present=True,
        host_relief={},
        force=False,
    )

    assert plan.should_publish is True
    assert plan.next_revision == 5
    assert plan.transaction_id == "fold_designer:5"
    assert plan.delta == {"settings": {"w": 640.0}}
    assert plan.payload["revision"] == 5
    assert plan.payload["transaction_id"] == "fold_designer:5"
    assert plan.payload["origin"] == "fold_designer"


def test_issue503_bridge_publish_is_plan_then_effect_boundary():
    source = Path("fold_designer_bridge.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="fold_designer_bridge.py")
    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_phase6_publish_live_state"
    )
    block = ast.get_source_segment(source, fn) or ""

    assert "plan_live_sync_envelope(" in block
    assert "materialize_sync_value(" in block

    forbidden = (
        "stable_fingerprint(",
        "mapping_delta(",
        'f"fold_designer:{revision}"',
        "force_host_relief_sync =",
        'payload.update({',
    )
    assert [token for token in forbidden if token in block] == []
