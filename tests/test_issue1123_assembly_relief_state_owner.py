from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from shapely.geometry import box

from ae_engine.manufacturing_api import (
    RELIEF_CONTRACT_VERSION,
    build_current_source_signature,
    build_persisted_relief_state,
    committed_relief_cuts,
    relief_profile_fingerprint,
    source_matches_current,
    structure_fingerprint,
)

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "ae_engine" / "assembly_relief_state.py"
FACADE = ROOT / "phase6_assembly_relief_state.py"
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
    facade = FACADE.read_text(encoding="utf-8")
    from ae_engine import manufacturing_api as public
    from phase6_assembly_relief_state import (
        build_current_source_signature as old_builder,
        committed_relief_cuts as old_replay,
        source_matches_current as old_match,
        build_persisted_relief_state as old_persist,
    )
    assert old_builder is public.build_current_source_signature
    assert old_replay is public.committed_relief_cuts
    assert old_match is public.source_matches_current
    assert old_persist is public.build_persisted_relief_state
    assert "def source_matches_current" not in facade
    assert "def build_persisted_relief_state" not in facade
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
    assert "manufacturing_api.resolve_operator_committed_relief_cuts(" in body
    assert "build_current_source_signature(" not in body
    assert "committed_relief_cuts(" not in body
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

    assert source_body is not None and "current_relief_source_signature(" in source_body
    assert match_body is not None and "manufacturing_api.source_matches_current(" in match_body
    assert serialize_body is not None and "serialize_assembly_relief_state(" in serialize_body
    assert fingerprint_body is not None and "manufacturing_api.relief_profile_fingerprint(" in fingerprint_body
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

def test_composition_save_and_replay_are_public_engine_only():
    source = (
        ROOT / "gui_modules" / "application" / "fold_designer_composition_state.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    methods = {
        node.name: ast.get_source_segment(source, node)
        for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    assert "manufacturing_api.build_current_source_signature(" in (
        methods["current_relief_source_signature"] or ""
    )
    assert "manufacturing_api.build_persisted_relief_state(" in (
        methods["serialize_assembly_relief_state"] or ""
    )
    assert "from phase6_assembly_relief_state" not in source
    from ae_engine import (
        build_current_source_signature as root_source,
        committed_relief_cuts as root_replay,
    )
    assert root_source is build_current_source_signature
    assert root_replay is committed_relief_cuts


def test_headless_save_reload_rejects_source_and_profile_drift():
    import json
    from copy import deepcopy
    saved = _source()
    reloaded = json.loads(json.dumps(saved, ensure_ascii=False))
    assert source_matches_current(reloaded, saved, ["head"])
    changed = deepcopy(saved)
    changed["part_profiles"]["head"]["Y"][0]["len"] += 1.0
    assert not source_matches_current(reloaded, changed, ["head"])
    changed = deepcopy(saved)
    changed["box_body_formed_fw"]["right"] += 0.01
    assert not source_matches_current(reloaded, changed, ["head"])
    changed = deepcopy(saved)
    changed["cabinet_family"] = "受電箱"
    assert not source_matches_current(reloaded, changed, ["head"])


def test_gui_operator_replay_source_is_forwarded_without_physical_manufacture(monkeypatch):
    from ae_engine import manufacturing_api
    from gui_modules.application.manufacturing_adapter import (
        _resolved_committed_assembly_relief_cuts,
    )
    from types import SimpleNamespace
    sentinel = (((1.0, 1.0), (2.0, 1.0), (1.0, 2.0)),)
    seen = []
    def port(key, values, **kwargs):
        seen.append((key, values, kwargs))
        return sentinel
    monkeypatch.setattr(
        manufacturing_api, "resolve_operator_committed_relief_cuts", port,
    )
    class Controller:
        def box_body_profile(self):
            return [{"phase6_key": "fw_left", "len": 25}]
        def box_body_structure_state(self):
            return {"active_type": "three_piece"}
    host = SimpleNamespace(
        assembly_relief_state={"enabled": True},
        assembly_joint_state={"assembly_joint_schema_version": 3, "assembly_joints": []},
        workspace_controller=Controller(),
        _baseline_source_model=lambda: "受電箱",
    )
    values = {"t": 2, "w": 400}
    part_profiles = {"X": [{"phase6_key": "w", "len": 400}]}
    assert _resolved_committed_assembly_relief_cuts(host, "head", values, part_profiles) is sentinel
    assert seen == [("head", values, {
        "relief_state": {"enabled": True},
        "joint_state": host.assembly_joint_state,
        "structure_state": {"active_type": "three_piece"},
        "cabinet_family": "受電箱",
        "box_body_profile": [{"phase6_key": "fw_left", "len": 25}],
        "part_profiles": part_profiles,
    })]


def test_public_operator_replay_validates_real_source_and_stale_save_reload(monkeypatch):
    from copy import deepcopy
    import json
    from ae_engine import manufacturing_api
    from ae_engine import operator_relief_replay as owner
    captured = []
    with monkeypatch.context() as mp:
        mp.setattr(owner, "committed_relief_cuts", lambda state, part, source: captured.append(deepcopy(source)) or ())
        original = {"w": 400, "h": 500, "d": 200, "t": 2, "fw": 25}
        fold = [
            {"phase6_key": "fw_left", "len": 25, "angle": -90},
            {"phase6_key": "box_w", "len": 350, "core": "W"},
            {"phase6_key": "fw_right", "len": 25},
        ]
        request = dict(
            relief_state={"enabled": True},
            joint_state={"assembly_joints": []},
            structure_state={"active_type": "integral"},
            cabinet_family="金庫型",
            box_body_profile=fold,
            part_profiles={"X": [{"phase6_key": "w", "len": 400}]},
        )
        manufacturing_api.resolve_operator_committed_relief_cuts("head", original, **request)
    assert captured
    source = captured[0]
    assert source["box_body_formed_fw"]["left"] is not None
    saved = json.loads(json.dumps({
        "enabled": True,
        "source": source,
        "parts": {"head": {
            "verified": True, "trust_level": "CERTIFIED",
            "cuts": [[(0, 0), (2, 0), (1, 1)]],
        }},
    }, ensure_ascii=False))
    request["relief_state"] = saved
    cut = manufacturing_api.resolve_operator_committed_relief_cuts("head", original, **request)
    assert cut == (((0.0, 0.0), (2.0, 0.0), (1.0, 1.0)),)
    updated = dict(original, w=401)
    assert manufacturing_api.resolve_operator_committed_relief_cuts("head", updated, **request) == ()
    request["cabinet_family"] = "受電箱"
    assert manufacturing_api.resolve_operator_committed_relief_cuts("head", original, **request) == ()
    assert source == captured[0]
