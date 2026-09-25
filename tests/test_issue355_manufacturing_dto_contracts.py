import dataclasses
import json

import pytest


def _contains_mutable(value):
    from collections.abc import Mapping

    if isinstance(value, (dict, list, set)):
        return True
    if isinstance(value, Mapping):
        return any(_contains_mutable(k) or _contains_mutable(v) for k, v in value.items())
    if isinstance(value, tuple):
        return any(_contains_mutable(v) for v in value)
    if dataclasses.is_dataclass(value):
        return any(_contains_mutable(getattr(value, f.name)) for f in dataclasses.fields(value))
    return False


def test_issue355_nested_inputs_are_defensively_frozen():
    from phase6_manufacturing_contracts import (
        ManufacturingPartInput,
        ManufacturingResolveRequest,
    )

    scene = {"b": [2, {"x": 1}], "a": {"nested": [3, 4]}}
    x_profile = [{"len": 10.0, "angle": 90}, {"len": 20.0}]
    features = [{"kind": "hole", "diameter": 6.4}]

    part = ManufacturingPartInput(
        part_key="head",
        scene_values=scene,
        x_profile=x_profile,
        y_profile=[],
        finished_dimensions={"width": 100.0, "height": 50.0},
        features=features,
        face_features={"front": [{"kind": "slot"}]},
        box_body_structure={"piece_count": 3},
    )
    request = ManufacturingResolveRequest(
        source_revision="r1",
        source_fingerprint="source-a",
        input_snapshot={"w": 800, "h": 1800, "settings": {"ui_text_size": "medium"}},
        settings={"t": 2.0},
        box_dimensions={"w": 800, "h": 1800, "d": 400},
        corner_state={"head": {"top_left": {"type": "A"}}},
        endcap_fw={"head": 29},
        endcap_bottom_wrap={"head": {"enabled": True}},
        assembly_graph={"assembly_joints": [{"joint_id": "J1"}]},
        canonical_part_keys=["head"],
        parts=[part],
        assembly_intent="INSERT_OVERLAY",
        allow_3d_fallback=False,
        relief_clearance=1.0,
        cabinet_model="受電箱",
    )

    # Mutating every original mutable source after construction must not alter
    # the DTO graph.
    scene["b"][1]["x"] = 999
    x_profile[0]["len"] = 999
    features[0]["diameter"] = 99

    frozen_part = request.parts[0]
    assert frozen_part.scene_values["b"][1]["x"] == 1
    assert frozen_part.x_profile[0]["len"] == 10.0
    assert frozen_part.features[0]["diameter"] == 6.4
    assert not _contains_mutable(request)


def test_issue355_equal_semantic_mappings_have_same_canonical_fingerprint():
    from phase6_manufacturing_contracts import (
        ManufacturingResolveRequest,
        manufacturing_request_fingerprint,
    )

    a = ManufacturingResolveRequest(
        source_revision="rev-A",
        source_fingerprint="source-A",
        input_snapshot={"z": 3, "a": 1, "m": {"y": 2, "x": 1}},
        settings={"t": 2.0, "fw": 29},
        canonical_part_keys=["tail", "head"],
    )
    b = ManufacturingResolveRequest(
        source_revision="rev-B",
        source_fingerprint="source-B",
        input_snapshot={"m": {"x": 1, "y": 2}, "a": 1, "z": 3},
        settings={"fw": 29, "t": 2.0},
        canonical_part_keys=["head", "tail"],
    )

    assert manufacturing_request_fingerprint(a) == manufacturing_request_fingerprint(b)

    c = dataclasses.replace(b, settings={"fw": 30, "t": 2.0})
    assert manufacturing_request_fingerprint(c) != manufacturing_request_fingerprint(b)


def test_issue355_contract_rejects_callbacks_and_arbitrary_ui_objects():
    from phase6_manufacturing_contracts import freeze_manufacturing_value

    with pytest.raises(TypeError):
        freeze_manufacturing_value(lambda: None)

    class FakeTkVariable:
        __module__ = "tkinter"

        def get(self):
            return "x"

    with pytest.raises(TypeError):
        freeze_manufacturing_value(FakeTkVariable())


def test_issue355_canonical_serialization_is_order_stable_and_json_safe():
    from phase6_manufacturing_contracts import (
        canonical_manufacturing_json,
        freeze_manufacturing_value,
    )

    left = freeze_manufacturing_value({"b": {3, 1}, "a": [1, 2.0]})
    right = freeze_manufacturing_value({"a": [1, 2.0], "b": {1, 3}})

    ltext = canonical_manufacturing_json(left)
    rtext = canonical_manufacturing_json(right)
    assert ltext == rtext
    assert json.loads(ltext) == {"a": [1, 2.0], "b": [1.0, 3.0]}


def test_issue355_request_contract_is_consumed_after_phase2_cutover():
    import ast
    from pathlib import Path

    path = Path("phase6_manufacturing_service.py")
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    resolver = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "resolve"
    )
    resolver_source = ast.get_source_segment(source, resolver) or ""
    assert "ManufacturingResolveRequest" in resolver_source
    assert "_phase6_call_bridge" not in resolver_source
    assert "self" not in {node.id for node in ast.walk(resolver) if isinstance(node, ast.Name)}

def test_issue362_request_preserves_runtime_part_order_but_fingerprint_is_order_stable():
    from phase6_manufacturing_contracts import (
        ManufacturingPartInput,
        ManufacturingResolveRequest,
        manufacturing_request_fingerprint,
    )

    body = ManufacturingPartInput(part_key="box_body")
    head = ManufacturingPartInput(part_key="head")
    tail = ManufacturingPartInput(part_key="tail")

    runtime = ManufacturingResolveRequest(
        canonical_part_keys=("box_body", "head", "tail"),
        parts=(body, head, tail),
    )
    reordered = ManufacturingResolveRequest(
        canonical_part_keys=("tail", "box_body", "head"),
        parts=(tail, body, head),
    )

    assert runtime.canonical_part_keys == ("box_body", "head", "tail")
    assert tuple(item.part_key for item in runtime.parts) == ("box_body", "head", "tail")
    assert reordered.canonical_part_keys == ("tail", "box_body", "head")
    assert tuple(item.part_key for item in reordered.parts) == ("tail", "box_body", "head")
    assert manufacturing_request_fingerprint(runtime) == manufacturing_request_fingerprint(reordered)

