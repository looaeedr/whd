from dataclasses import is_dataclass
from types import SimpleNamespace

import pytest


class FakeVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class FakeWorkspace:
    def __init__(self):
        self.available_parts = [
            "box_body",
            "head",
            "box_body:piece:side_left",
        ]
        self.active_part = "head"
        self._profiles = {
            "head": {"X": [{"len": 10}], "Y": [{"len": 20}]},
        }
        self._features = {
            "head": [{"kind": "hole", "diameter": 6.4}],
            "box_body": [{"kind": "notch"}],
        }
        self._face_features = {
            "head": {"front": [{"kind": "slot"}]},
        }

    def profiles_for(self, key, default):
        return self._profiles.get(key, default)

    def features_for(self, key):
        return self._features.get(key, [])

    def face_features_for(self, key):
        return self._face_features.get(key, {})

    def box_body_structure_state(self):
        return {"piece_count": 3, "mode": "THREE_PIECE"}


def _fake_app():
    snapshot = {
        "model": "受電箱",
        "w": 800,
        "h": 1800,
        "d": 400,
        "t": 2.0,
        "assembly_joint_schema_version": 1,
        "assembly_joints": [],
    }
    workspace = FakeWorkspace()
    state = SimpleNamespace(
        profiles_vault={"箱身": [{"len": 100}, {"len": 200}]},
        profiles={"X": [{"len": 10}], "Y": [{"len": 20}]},
    )
    app = SimpleNamespace(
        _phase6_input_snapshot=snapshot,
        _settings_values={"t": 2.0, "fw": 29},
        _phase6_box_whd={"w": 800, "h": 1800, "d": 400},
        _phase6_corner_state={"head": {"top_left": {"type": "A"}}},
        _phase6_endcap_fw_state={"head": 29},
        _phase6_endcap_bottom_wrap_state={"head": {"enabled": True}},
        _phase6_assembly_type=SimpleNamespace(value="INSERT_OVERLAY"),
        assembly_ignore_fixed_corner_var=FakeVar(False),
        assembly_relief_clearance_var=FakeVar("1.25"),
        baseline_model_var=FakeVar("受電箱"),
        _phase6_sync_revision=17,
        designer_workspace=workspace,
        state=state,
    )

    def scene_payload(key):
        return {
            "part_key": key,
            "model": "受電箱",
            "features": workspace.features_for(key),
            "face_features": workspace.face_features_for(key),
            "box_body_structure": workspace.box_body_structure_state(),
        }

    def finished_dimensions(key=None, *, triangles=None):
        return {
            "part_key": key or "",
            "width": 800.0 if key == "box_body" else 100.0,
            "height": 1800.0 if key == "box_body" else 50.0,
        }

    app._phase6_scene_query_payload_for_part = scene_payload
    app._phase6_operator_finished_dimensions = finished_dimensions
    return app


def test_issue356_builds_deterministic_immutable_request_from_app_state():
    from phase6_manufacturing_adapter import build_manufacturing_request
    from phase6_manufacturing_contracts import (
        ManufacturingResolveRequest,
        manufacturing_request_fingerprint,
    )

    app = _fake_app()
    request = build_manufacturing_request(app)

    assert isinstance(request, ManufacturingResolveRequest)
    assert request.canonical_part_keys == ("box_body", "head")
    assert tuple(part.part_key for part in request.parts) == ("box_body", "head")
    assert request.assembly_intent == "INSERT_OVERLAY"
    assert request.allow_3d_fallback is False
    assert request.relief_clearance == 1.25
    assert request.cabinet_model == "受電箱"
    assert request.source_revision == "17"
    assert request.source_fingerprint == manufacturing_request_fingerprint(request)

    head = next(part for part in request.parts if part.part_key == "head")
    assert head.scene_values["part_key"] == "head"
    assert head.x_profile[0]["len"] == 10.0
    assert head.y_profile[0]["len"] == 20.0
    assert head.finished_dimensions["part_key"] == "head"
    assert head.features[0]["diameter"] == 6.4
    assert head.face_features["front"][0]["kind"] == "slot"
    assert head.box_body_structure["piece_count"] == 3.0

    # Builder result must be isolated from later app/workspace mutations.
    app._phase6_input_snapshot["w"] = 999
    app.designer_workspace._profiles["head"]["X"][0]["len"] = 999
    app.designer_workspace._features["head"][0]["diameter"] = 99

    assert request.input_snapshot["w"] == 800.0
    assert head.x_profile[0]["len"] == 10.0
    assert head.features[0]["diameter"] == 6.4


def test_issue356_same_app_state_builds_same_request_fingerprint():
    from phase6_manufacturing_adapter import build_manufacturing_request
    from phase6_manufacturing_contracts import manufacturing_request_fingerprint

    a = build_manufacturing_request(_fake_app())
    b = build_manufacturing_request(_fake_app())
    assert manufacturing_request_fingerprint(a) == manufacturing_request_fingerprint(b)


def test_issue356_adapter_has_no_solver_or_domain_loop_ownership():
    import ast
    from pathlib import Path

    path = Path("phase6_manufacturing_adapter.py")
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    forbidden = {
        "_phase6_resolve_explicit_joint_reliefs",
        "_phase6_build_joint_world_geometry",
        "solve_world_backprojected_endcap_relief",
        "discover_joint_relief_candidate",
        "project_joint_interference_to_relief_owner",
    }
    loaded = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
    }
    assert not (loaded & forbidden)
    assert "fold_designer_bridge" not in source


def test_issue356_adapter_contract_survives_later_phase2_resolver_cutover():
    import ast
    from pathlib import Path

    path = Path("phase6_manufacturing_adapter.py")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    assert "build_manufacturing_request" in names

def test_issue362_committed_endcap_second_pass_thaws_nested_scene_payload():
    from phase6_manufacturing_adapter import build_manufacturing_request

    app = _fake_app()
    app.designer_workspace.available_parts = ["box_body", "head", "tail"]
    calls = []

    def scene_payload(key):
        return {
            "part_key": key,
            "nested": {
                "profile": [
                    {"len": 10, "angle": 90},
                    {"len": 20},
                ],
            },
        }

    def render_provider(key, payload):
        calls.append((key, payload["_use_committed_relief"]))
        profile = payload["nested"]["profile"]
        if payload["_use_committed_relief"]:
            # Legacy render providers are allowed to annotate their detached
            # compatibility payload. The immutable DTO must not leak here.
            profile[0]["ui_len_add"] = 2.0
        return {"profile": profile}

    request = build_manufacturing_request(
        app,
        scene_payload_builder=scene_payload,
        render_data_provider=render_provider,
    )

    assert calls == [
        ("box_body", False),
        ("head", False),
        ("tail", False),
        ("head", True),
        ("tail", True),
    ]
    head = next(part for part in request.parts if part.part_key == "head")
    assert head.committed_render_data["profile"][0]["ui_len_add"] == 2.0
    assert "ui_len_add" not in head.scene_values["nested"]["profile"][0]

