"""#2517 Engine-native manufacturing resolver and Phase6 compatibility boundary."""
from pathlib import Path

import pytest

from ae_engine import manufacturing_api
from ae_engine import AssemblyScenePart, resolve_manufacturing_request
from ae_engine.manufacturing_contracts import ManufacturingResolveRequest
from ae_engine.manufacturing_resolver import resolve as canonical_resolve
import phase6_final_scene_contracts as old_scene
import phase6_manufacturing_service as old_service


def test_operator_and_headless_resolver_reference_same_engine_owner():
    assert resolve_manufacturing_request is canonical_resolve
    assert manufacturing_api.resolve_manufacturing_request is canonical_resolve
    assert old_scene.AssemblyScenePart is AssemblyScenePart
    assert AssemblyScenePart is manufacturing_api.AssemblyScenePart


def test_phase6_resolver_is_only_request_to_result_adapter():
    import inspect
    source = inspect.getsource(old_service.resolve)
    assert "ManufacturingResolveRequest" in source
    assert "ManufacturingResolveResult" in source
    assert "manufacturing_api.resolve_manufacturing_request(request)" in source
    for forbidden in ("resolve_receiving_nfb_assembly_parts", "joint_relief_state",
                      "solve_endcap_assembly_relief", "DrawingScene", "Tk"):
        assert forbidden not in source


def test_engine_resolver_does_not_import_phase6_or_tk():
    content = Path("ae_engine/manufacturing_resolver.py").read_text(encoding="utf-8")
    import ast
    tree = ast.parse(content)
    imported=[]
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
        elif isinstance(node, ast.Import):
            imported.extend(n.name for n in node.names)
    assert not any(x.startswith(("phase6_", "gui_modules", "tkinter",
                                 "fold_designer_bridge")) for x in imported)
    assert "from .manufacturing_contracts import (" in content
    assert "resolve_manufacturing_explicit_joint_reliefs(" in content
    assert "resolve_receiving_nfb_assembly_parts(snapshot, parts)" in content


def test_engine_and_phase6_reject_non_request_and_missing_physical_scene():
    with pytest.raises(TypeError, match="ManufacturingResolveRequest"):
        canonical_resolve(object())
    with pytest.raises(TypeError, match="ManufacturingResolveRequest"):
        old_service.resolve(object())
    request = ManufacturingResolveRequest(
        input_snapshot={"model": "金庫型"},
        cabinet_model="金庫型",
        canonical_part_keys=(),
    )
    with pytest.raises(ValueError, match="no parts available"):
        canonical_resolve(request)


def test_engine_scene_part_remains_immutable_and_adapter_identity():
    from dataclasses import FrozenInstanceError
    part = AssemblyScenePart(
        part_key="head", render_data=None,
        x_profile=(), y_profile=(),
    )
    assert old_scene.AssemblyScenePart is type(part)
    with pytest.raises(FrozenInstanceError):
        part.part_key = "tail"
