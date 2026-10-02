from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from shapely.geometry import box

from phase6_assembly_relief_state import (
    RELIEF_CONTRACT_VERSION,
    build_current_source_signature,
    build_persisted_relief_state,
    committed_relief_cuts,
    relief_profile_fingerprint,
    source_matches_current,
    structure_fingerprint,
)

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "phase6_assembly_relief_state.py"
ADAPTER = ROOT / "gui_modules" / "application" / "manufacturing_adapter.py"
BRIDGE = ROOT / "fold_designer_bridge.py"


def _source(*, graph="G1", structure=None, family="金庫型", assembly_type="INSERT"):
    return {
        "relief_contract_version": RELIEF_CONTRACT_VERSION,
        "assembly_type": assembly_type,
        "joint_graph_fingerprint": graph,
        "family_structure_fingerprint": structure_fingerprint(structure or {}),
        "cabinet_family": family,
        "box_body_formed_fw": {"left": 29.0, "right": 29.0},
        "box_body_profile": [{"phase6_key": "fw_left", "len": 25.0, "angle": -90}],
        "part_profiles": {
            "head": {
                "X": [{"phase6_key": "w", "len": 100.0, "angle": None, "core": "W"}],
                "Y": [{"phase6_key": "h", "len": 80.0, "angle": None, "core": "H"}],
            }
        },
        "registry_rules": {
            "head": {"rule_id": "ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1", "revision": 1}
        },
        "w": 100.0,
        "h": 80.0,
        "d": 40.0,
        "t": 2.0,
        "fw": 29.0,
    }


def test_neutral_owner_exists_without_bridge_gui_or_solver_imports():
    text = OWNER.read_text(encoding="utf-8")
    tree = ast.parse(text)
    names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert {
        "relief_profile_fingerprint",
        "structure_fingerprint",
        "source_matches_current",
        "committed_relief_cuts",
        "build_current_source_signature",
        "build_persisted_relief_state",
    } <= names
    assert "import fold_designer_bridge" not in text
    assert "from fold_designer_bridge" not in text
    assert "import gui" not in text
    assert "from gui" not in text
    assert "assembly_collision" not in text
    assert "solve_world" not in text


def test_disabled_replay_does_not_require_initialized_box_body_profile():
    from gui_modules.application.manufacturing_adapter import (
        _resolved_committed_assembly_relief_cuts,
    )

    host = SimpleNamespace(
        assembly_relief_state={"enabled": False},
        workspace_controller=SimpleNamespace(box_body_profile=lambda: None),
    )
    assert _resolved_committed_assembly_relief_cuts(host, "head", {"t": 2.0}, {}) == ()


def test_manufacturing_adapter_delegates_replay_contract_to_neutral_owner():
    text = ADAPTER.read_text(encoding="utf-8")
    tree = ast.parse(text)
    func = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_resolved_committed_assembly_relief_cuts")
    body = ast.get_source_segment(text, func)
    assert body is not None
    assert "build_current_source_signature(" in body
    assert "committed_relief_cuts(" in body
    assert "certified_rule_revision_exists" not in body
    assert "RELIEF_CONTRACT_VERSION" not in body
    assert "structure_fingerprint" not in body
    assert "registry_rules" not in body


def test_bridge_delegates_persisted_contract_to_neutral_owner():
    text = BRIDGE.read_text(encoding="utf-8")
    tree = ast.parse(text)
    funcs = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}

    source_body = ast.get_source_segment(text, funcs["_phase6_current_relief_source_signature"])
    match_body = ast.get_source_segment(text, funcs["_phase6_relief_source_matches_current"])
    serialize_body = ast.get_source_segment(text, funcs["_phase6_serialize_assembly_relief_state"])
    fingerprint_body = ast.get_source_segment(text, funcs["_phase6_relief_profile_fingerprint"])

    assert source_body is not None and "build_current_source_signature(" in source_body
    assert match_body is not None and "source_matches_current(" in match_body
    assert serialize_body is not None and "build_persisted_relief_state(" in serialize_body
    assert fingerprint_body is not None and "relief_profile_fingerprint(" in fingerprint_body
    for body in (source_body, match_body, serialize_body, fingerprint_body):
        assert "certified_rule_revision_exists" not in body
        assert "RELIEF_CONTRACT_VERSION" not in body
        assert "structure_fingerprint" not in body
        assert "registry_rules" not in body


def test_source_signature_builder_is_shared_and_deterministic():
    source = build_current_source_signature(
        scalar_source={"w": 100, "t": 2, "assembly_type": "INSERT"},
        joint_graph_fingerprint="G1",
        structure_state={"mode": "three_piece"},
        cabinet_family="金庫型",
        formed_left=29,
        formed_right=29,
        box_body_profile=[{"phase6_key": "fw", "len": 25}],
        part_profiles={"head": {"X": [{"phase6_key": "w", "len": 100}]}},
    )
    assert source["relief_contract_version"] == RELIEF_CONTRACT_VERSION
    assert source["joint_graph_fingerprint"] == "G1"
    assert source["cabinet_family"] == "金庫型"
    assert source["box_body_formed_fw"] == {"left": 29.0, "right": 29.0}
    assert source["assembly_type"] == "INSERT"
    assert source["family_structure_fingerprint"] == structure_fingerprint({"mode": "three_piece"})


def test_profile_fingerprint_is_stable_and_normalized():
    assert relief_profile_fingerprint([
        {"phase6_key": "a", "len": "12.0000004", "angle": "90", "core": "x"},
        {"phase6_key": "b", "length": 3, "angle": None, "core": ""},
    ]) == (
        ("a", 12.0, 90.0, "x"),
        ("b", 3.0, None, ""),
    )


def test_source_match_uses_mechanics_not_high_level_assembly_mirror():
    saved = _source(assembly_type="INSERT")
    current = _source(assembly_type="OVERLAY")
    assert source_matches_current(saved, current, ["head"]) is True

    changed_graph = _source(graph="G2")
    assert source_matches_current(saved, changed_graph, ["head"]) is False

    changed_structure = _source(structure={"mode": "different"})
    assert source_matches_current(saved, changed_structure, ["head"]) is False


def test_committed_replay_rejects_stale_rule_revision_and_accepts_current_rule():
    current = _source()
    state = {
        "enabled": True,
        "source": _source(),
        "parts": {
            "head": {
                "verified": True,
                "trust_level": "CERTIFIED",
                "rule_id": "ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1",
                "rule_revision": 1,
                "cuts": [[(0, 0), (2, 0), (2, 2), (0, 2)]],
            }
        },
    }
    assert len(committed_relief_cuts(state, "head", current)) == 1

    state["source"]["registry_rules"]["head"]["revision"] = 999
    state["parts"]["head"]["rule_revision"] = 999
    assert committed_relief_cuts(state, "head", current) == ()


def test_persisted_state_is_atomic_and_preserves_only_current_prior_transaction():
    source = _source()
    solution = SimpleNamespace(
        verified=True,
        trust_level="CERTIFIED",
        rule_id="ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1",
        rule_revision=1,
        joint_signature=({"relation": "INSERT"},),
        shadow_validation={"verified": True},
        cut_polygon_2d=box(0, 0, 2, 2),
        corner_reliefs=(),
    )
    state = build_persisted_relief_state(
        required_parts=["head"],
        solutions={"head": solution},
        source_signature=source,
        fallback_enabled=True,
        clearance=0.0,
    )
    assert state["enabled"] is True
    assert state["source"]["registry_rules"]["head"] == {
        "rule_id": "ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1",
        "revision": 1,
    }
    assert len(state["parts"]["head"]["cuts"]) == 1

    preserved = build_persisted_relief_state(
        required_parts=["head"],
        solutions={},
        source_signature=source,
        prior_state=state,
        fallback_enabled=False,
        clearance=1.0,
    )
    assert preserved == state

    disabled = build_persisted_relief_state(
        required_parts=["head"],
        solutions={},
        source_signature=_source(graph="G2"),
        prior_state=state,
        fallback_enabled=False,
        clearance=1.0,
    )
    assert disabled == {
        "enabled": False,
        "fallback_enabled": False,
        "clearance": 1.0,
        "source": {},
        "parts": {},
    }
