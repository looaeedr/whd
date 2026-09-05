# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

import pytest
from shapely.geometry import box

from ae_engine.certified_relief_registry import CertifiedReliefStatus
from ae_engine.sheetmetal_geometry import CornerTypeId


def test_certified_lookup_runs_even_when_3d_fallback_is_disabled():
    from tests.test_certified_relief_registry import _insert_fixture
    from ae_engine.assembly_collision import solve_world_backprojected_endcap_relief

    body, endcap, body_profile, profiles = _insert_fixture("head")
    solution = solve_world_backprojected_endcap_relief(
        box_body_render_data=body,
        endcap_render_data=endcap,
        box_body_x_profile=body_profile,
        endcap_x_profile=profiles["X"],
        endcap_y_profile=profiles["Y"],
        finished_dimensions=(400, 600, 250),
        endcap_placement="top",
        sheet_thickness=2,
        assembly_intent=CornerTypeId.INSERT,
        allow_3d_fallback=False,
    )
    assert solution.verified is True
    assert solution.trust_level == CertifiedReliefStatus.CERTIFIED.value
    assert solution.rule_id == "ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1"
    assert solution.rule_revision == 1


def test_unknown_combination_does_not_discover_when_fallback_is_disabled():
    from tests.test_certified_relief_registry import _insert_fixture
    from ae_engine.assembly_collision import solve_world_backprojected_endcap_relief

    body, endcap, body_profile, profiles = _insert_fixture("head")
    solution = solve_world_backprojected_endcap_relief(
        box_body_render_data=body,
        endcap_render_data=endcap,
        box_body_x_profile=body_profile,
        endcap_x_profile=profiles["X"],
        endcap_y_profile=profiles["Y"],
        finished_dimensions=(400, 600, 250),
        endcap_placement="top",
        sheet_thickness=2,
        assembly_intent=None,
        allow_3d_fallback=False,
    )
    assert solution.verified is False
    assert solution.trust_level == CertifiedReliefStatus.FAILED.value
    assert solution.rule_id is None
    assert solution.cut_polygon_2d is None


def test_assembly_relief_save_state_persists_rule_revision_and_trust(monkeypatch):
    import fold_designer_bridge as bridge

    class Var:
        def __init__(self, value): self.value = value
        def get(self): return self.value

    solution = SimpleNamespace(
        verified=True,
        trust_level="CERTIFIED",
        rule_id="ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1",
        rule_revision=1,
        joint_signature=({"relation": "INSERT", "subject_role": "HEAD_OR_TAIL", "target_role": "BOX_SIDE"},),
        shadow_validation={"verified": True},
        cut_polygon_2d=box(0, 0, 2, 2),
        corner_reliefs=(),
    )
    self = SimpleNamespace(
        assembly_ignore_fixed_corner_var=Var(False),  # fallback OFF must not disable certified save
        assembly_relief_clearance_var=Var("0"),
        _phase6_last_relief_solutions={"head": solution, "tail": solution},
        designer_workspace=SimpleNamespace(available_parts=("box_body", "head", "tail")),
        _phase6_input_snapshot={},
    )
    monkeypatch.setattr(bridge, "_phase6_current_relief_source_signature", lambda _self, _required: {"assembly_type": "INSERT"})

    state = bridge._phase6_serialize_assembly_relief_state(self)
    assert state["enabled"] is True
    assert state["fallback_enabled"] is False
    for key in ("head", "tail"):
        part = state["parts"][key]
        assert part["rule_id"] == "ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1"
        assert part["rule_revision"] == 1
        assert part["trust_level"] == "CERTIFIED"
        assert part["joint_signature"] == [
            {"relation": "INSERT", "subject_role": "HEAD_OR_TAIL", "target_role": "BOX_SIDE"}
        ]
        assert part["shadow_validation"] == {"verified": True}


def test_reload_rejects_stale_certified_rule_revision(monkeypatch):
    import hashlib
    import json
    import gui
    from ae_engine.assembly_joint import migrate_legacy_snapshot_joints, resolved_joint_graph_fingerprint

    joint_state = migrate_legacy_snapshot_joints({
        "assembly_type": "INSERT",
        "existing_parts": ["box_body", "head", "tail"],
    })
    graph_fp = resolved_joint_graph_fingerprint(joint_state)
    structure_fp = hashlib.sha256(
        json.dumps({}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    class Dummy:
        def __init__(self, revision):
            self.assembly_joint_state = joint_state
            self.workspace_controller = SimpleNamespace(
                box_body_structure_state=lambda: {},
                box_body_profile=lambda: (),
            )
            self.assembly_relief_state = {
                "enabled": True,
                "source": {
                    "assembly_type": "INSERT",
                    "relief_contract_version": 3,
                    "joint_graph_fingerprint": graph_fp,
                    "family_structure_fingerprint": structure_fp,
                    "cabinet_family": "金庫型",
                    "registry_rules": {
                        "head": {
                            "rule_id": "ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1",
                            "revision": revision,
                        }
                    },
                    "part_profiles": {},
                },
                "parts": {
                    "head": {
                        "verified": True,
                        "rule_id": "ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1",
                        "rule_revision": revision,
                        "trust_level": "CERTIFIED",
                        "cuts": [[(0, 0), (2, 0), (2, 2), (0, 2)]],
                    }
                },
            }
        def _current_box_assembly_type(self): return CornerTypeId.INSERT
        def _baseline_source_model(self): return "金庫型"
        _phase6_relief_profile_signature = staticmethod(gui.BoxCalculatorGUI._phase6_relief_profile_signature)

    val = {name: 0.0 for name in ("w", "h", "d", "t", "fw", "zl1", "zr1", "yl1", "yr1", "ytop1", "ybottom1")}
    good = gui.BoxCalculatorGUI._resolved_committed_assembly_relief_cuts(Dummy(1), "head", val, {})
    stale = gui.BoxCalculatorGUI._resolved_committed_assembly_relief_cuts(Dummy(999), "head", val, {})
    assert len(good) == 1
    assert stale == ()


def _bridge_fake_app(*, fallback_enabled):
    from ae_engine.sheetmetal_drawing import DrawingScene
    from phase6_designer_workspace import Phase6DesignerWorkspace

    class Var:
        def __init__(self, value): self.value = value
        def get(self): return self.value
        def set(self, value): self.value = value

    flat_x = [{"len": 100.0, "core": True}]
    flat_y = [{"len": 80.0, "core": True}]
    raw = {
        key: SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 100, 80), fold_guides=())
        for key in ("box_body", "head", "tail")
    }
    canonical = {
        "head": SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 91, 71), fold_guides=()),
        "tail": SimpleNamespace(scene=DrawingScene(), material=box(0, 0, 92, 72), fold_guides=()),
    }
    callback_calls = []
    def callback(part_key, payload):
        callback_calls.append((part_key, dict(payload)))
        if part_key in canonical and payload.get("resolved_assembly_relief_cuts"):
            return canonical[part_key]
        return raw[part_key]

    app = SimpleNamespace(
        designer_workspace=Phase6DesignerWorkspace.from_snapshot({
            "existing_parts": ["box_body", "head", "tail"], "active_part": "box_body",
            "part_profiles": {
                "head": {"X": flat_x, "Y": flat_y},
                "tail": {"X": flat_x, "Y": flat_y},
            },
        }),
        state=SimpleNamespace(profiles={"X": flat_x, "Y": flat_y}, profiles_vault={"箱身": flat_x}),
        _scene_query_callback=callback,
        _phase6_input_snapshot={"t": 2.0, "model": "金庫型"},
        _settings_values={"t": 2.0},
        _phase6_box_whd={"w": 100.0, "h": 80.0, "d": 40.0},
        _phase6_corner_state={}, _phase6_endcap_fw_state={},
        _phase6_assembly_type=CornerTypeId.INSERT,
        assembly_ignore_fixed_corner_var=Var(fallback_enabled),
        assembly_show_interference_var=Var(True),
        assembly_relief_clearance_var=Var("0"),
    )
    return app, raw, canonical, callback_calls


def test_bridge_fallback_toggle_does_not_disable_certified_lookup(monkeypatch):
    import ae_engine.assembly_collision as collision
    import fold_designer_bridge as bridge

    app, raw, canonical, _calls = _bridge_fake_app(fallback_enabled=False)
    solver_calls = []
    def fake_solver(**kwargs):
        solver_calls.append(kwargs)
        placement = kwargs["endcap_placement"]
        key = "head" if placement == "top" else "tail"
        return SimpleNamespace(
            verified=True, trust_level="CERTIFIED",
            rule_id="TEST_CERT", rule_revision=1,
            shadow_validation={"verified": True},
            cut_polygon_2d=box(0, 0, 7, 9),
            solved_render_data=canonical[key],
            corner_reliefs=(), residual_projection=SimpleNamespace(segments_2d=()),
        )
    monkeypatch.setattr(collision, "solve_world_backprojected_endcap_relief", fake_solver)
    monkeypatch.setattr(bridge, "_phase6_operator_finished_dimensions", lambda self: (100.0, 80.0, 40.0))
    monkeypatch.setattr(bridge, "_phase6_publish_live_state", lambda self, force=False: True)

    bundle = bridge._phase6_query_assembly_render_data(app)
    assert len(solver_calls) == 2
    assert all(call["allow_3d_fallback"] is False for call in solver_calls)
    assert all(call["cabinet_family"] == "金庫型" for call in solver_calls)
    by_key = {part.part_key: part.render_data for part in bundle.assembly_parts}
    assert by_key["head"] is canonical["head"]
    assert by_key["tail"] is canonical["tail"]


def test_bridge_commits_certified_formula_even_when_shadow_reports_engine_conflict(monkeypatch):
    import ae_engine.assembly_collision as collision
    import fold_designer_bridge as bridge

    app, raw, canonical, _calls = _bridge_fake_app(fallback_enabled=True)
    def fake_solver(**kwargs):
        placement = kwargs["endcap_placement"]
        key = "head" if placement == "top" else "tail"
        return SimpleNamespace(
            verified=False, trust_level="ENGINE_CONFLICT",
            rule_id="TEST_CERT", rule_revision=1,
            shadow_validation={"verified": False, "reason": "shadow conflict"},
            cut_polygon_2d=box(0, 0, 7, 9),
            solved_render_data=canonical[key],
            corner_reliefs=(), residual_projection=SimpleNamespace(segments_2d=((0, 0, 1, 1),)),
        )
    monkeypatch.setattr(collision, "solve_world_backprojected_endcap_relief", fake_solver)
    monkeypatch.setattr(bridge, "_phase6_operator_finished_dimensions", lambda self: (100.0, 80.0, 40.0))
    monkeypatch.setattr(bridge, "_phase6_publish_live_state", lambda self, force=False: True)

    bundle = bridge._phase6_query_assembly_render_data(app)
    by_key = {part.part_key: part.render_data for part in bundle.assembly_parts}
    assert by_key["head"] is canonical["head"]
    assert by_key["tail"] is canonical["tail"]
    assert set(app._phase6_last_relief_solutions) == {"head", "tail"}
    assert set(app._phase6_last_relief_errors) == {"head", "tail"}


def test_bridge_builds_promotion_manifest_without_mutating_registry():
    import fold_designer_bridge as bridge

    provisional = SimpleNamespace(
        verified=True, trust_level="PROVISIONAL_3D", rule_id=None, rule_revision=None,
        corner_reliefs=(), shadow_validation=None,
    )
    app = SimpleNamespace(
        _phase6_last_relief_solutions={"head": provisional, "tail": provisional},
        _phase6_input_snapshot={"model": "自訂", "w": 400, "t": 2},
        _phase6_assembly_type=CornerTypeId.OVERLAY,
    )
    candidates = bridge._phase6_create_relief_promotion_candidates(app)
    assert set(candidates) == {"head", "tail"}
    assert all(value["status"] == "PROMOTION_CANDIDATE" for value in candidates.values())
    assert all(value["mutates_registry"] is False for value in candidates.values())
    assert app._phase6_last_relief_promotion_candidates == candidates


def test_relief_contract_v2_rejects_missing_version_and_formed_fw_fingerprint():
    import gui

    class Dummy:
        def __init__(self, source):
            self.assembly_relief_state = {
                "enabled": True,
                "source": dict(source),
                "parts": {
                    "head": {
                        "verified": True,
                        "rule_id": "ENDCAP_TOP_OVERLAY_STANDARD_V1",
                        "rule_revision": 2,
                        "trust_level": "CERTIFIED",
                        "cuts": [[(0, 0), (40, 0), (40, 39), (0, 39)]],
                    }
                },
            }
            self.workspace_controller = SimpleNamespace(box_body_profile=lambda: [
                {"len": 25, "angle": -90, "phase6_key": "fw_left"},
                {"len": 396, "angle": -90, "phase6_key": "w", "core": "W"},
                {"len": 25, "angle": -90, "phase6_key": "fw_right"},
            ])
        def _current_box_assembly_type(self): return CornerTypeId.OVERLAY
        _phase6_relief_profile_signature = staticmethod(gui.BoxCalculatorGUI._phase6_relief_profile_signature)

    val = {
        "w": 400.0, "h": 600.0, "d": 250.0, "t": 2.0, "fw": 25.0,
        "zl1": 15.0, "zr1": 15.0, "yl1": 15.0, "yr1": 15.0,
        "ytop1": 16.0, "ybottom1": 15.0,
    }
    source = {**val, "assembly_type": "OVERLAY"}
    assert gui.BoxCalculatorGUI._resolved_committed_assembly_relief_cuts(Dummy(source), "head", val, {}) == ()


def test_serialized_relief_source_contains_contract_v3_formed_fw_and_registry_revision(monkeypatch):
    import fold_designer_bridge as bridge

    class Var:
        def __init__(self, value): self.value = value
        def get(self): return self.value

    solution = SimpleNamespace(
        verified=True,
        trust_level="CERTIFIED",
        rule_id="ENDCAP_TOP_OVERLAY_STANDARD_V1",
        rule_revision=3,
        joint_signature=({"relation": "OVERLAY"},),
        shadow_validation={"verified": True, "residual_pair_count": 0},
        cut_polygon_2d=box(0, 0, 29, 39),
        corner_reliefs=(),
    )
    self = SimpleNamespace(
        assembly_ignore_fixed_corner_var=Var(True),
        assembly_relief_clearance_var=Var("0"),
        _phase6_last_relief_solutions={"head": solution, "tail": solution},
        designer_workspace=SimpleNamespace(available_parts=("box_body", "head", "tail")),
        _phase6_input_snapshot={},
    )
    monkeypatch.setattr(
        bridge,
        "_phase6_current_relief_source_signature",
        lambda _self, _required: {
            "assembly_type": "OVERLAY",
            "relief_contract_version": 3,
            "box_body_formed_fw": {"left": 29.0, "right": 29.0},
        },
    )
    state = bridge._phase6_serialize_assembly_relief_state(self)
    assert state["source"]["relief_contract_version"] == 3
    assert state["source"]["box_body_formed_fw"] == {"left": 29.0, "right": 29.0}
    assert state["source"]["registry_rules"] == {
        "head": {"rule_id": "ENDCAP_TOP_OVERLAY_STANDARD_V1", "revision": 3},
        "tail": {"rule_id": "ENDCAP_TOP_OVERLAY_STANDARD_V1", "revision": 3},
    }
