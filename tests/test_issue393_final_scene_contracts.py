from __future__ import annotations

import ast
import dataclasses
import inspect
from pathlib import Path

import pytest


CONTRACTS = Path("phase6_final_scene_contracts.py")
VIEW = Path("phase6_final_scene_view.py")
BRIDGE = Path("fold_designer_bridge.py")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
    return out


def test_issue393_requires_typed_final_scene_contract_module():
    assert CONTRACTS.is_file(), "RED: T4 requires phase6_final_scene_contracts.py"
    from phase6_final_scene_contracts import (
        AssemblyScenePart,
        AssemblySceneRenderData,
        FinalSceneDependencies,
        FinalSceneEffects,
        FinalSceneRenderResult,
        FinalSceneRuntimeState,
        FinalSceneViewRequest,
    )

    for cls in (
        AssemblyScenePart,
        AssemblySceneRenderData,
        FinalSceneDependencies,
        FinalSceneEffects,
        FinalSceneRenderResult,
        FinalSceneRuntimeState,
        FinalSceneViewRequest,
    ):
        assert dataclasses.is_dataclass(cls)
        assert cls.__dataclass_params__.frozen is True

    deps_fields = {f.name for f in dataclasses.fields(FinalSceneDependencies)}
    required = {
        "number_text",
        "is_physical_piece_key",
        "physical_piece_render_data",
        "user_joint_parts",
        "resolve_geometry",
        "scene_payload_for_part",
        "publish_live_state",
        "corner_dimension_text",
        "formed_size_text",
        "blank_text",
        "refresh_box_body_piece_info",
        "operator_dimensions",
        "cabinet_family",
        "assembly_blank_text",
        "active_mesh_profiles",
        "assembly_render_data_cls",
        "assembly_part_cls",
        "final_render_provider",
        "assembly_render_provider",
        "request_provider",
        "after_render",
    }
    assert required <= deps_fields


def test_issue393_missing_required_dependency_fails_closed():
    from phase6_final_scene_contracts import FinalSceneDependencies

    with pytest.raises((TypeError, ValueError)):
        FinalSceneDependencies()


def test_issue393_adapter_has_no_generic_service_bag_or_string_dispatch():
    source = VIEW.read_text(encoding="utf-8")
    assert "def _service(" not in source
    assert "self.services" not in source
    assert "services.get(" not in source
    assert "services={" not in source

    tree = ast.parse(source, filename=str(VIEW))
    cls = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6FinalSceneViewAdapter"
    )
    init = next(
        node for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    )
    names = [arg.arg for arg in init.args.args + init.args.kwonlyargs]
    assert "dependencies" in names
    assert "services" not in names


def test_issue393_bridge_builds_explicit_typed_dependencies():
    source = BRIDGE.read_text(encoding="utf-8")
    composition = Path("gui_modules/application/fold_designer_adapter.py")
    composition_source = composition.read_text(encoding="utf-8")

    assert "services={" not in source
    assert ".services" not in source
    assert (
        "FinalSceneDependencies(" in source
        or "Phase6FoldDesignerComposition" in source
    )

    if "Phase6FoldDesignerComposition" in source:
        assert "FinalSceneDependencies(" in composition_source
        assert "Phase6FinalSceneViewAdapter(" in composition_source
    else:
        assert "Phase6FinalSceneViewAdapter(" in source

    tree = ast.parse(source, filename=str(BRIDGE))
    imports = _imports(BRIDGE)
    assert (
        "phase6_final_scene_contracts" in imports
        or "gui_modules.application.fold_designer_adapter" in imports
    )


def test_issue393_contracts_are_ui_and_bridge_independent():
    imports = _imports(CONTRACTS)
    forbidden = sorted(
        name for name in imports
        if name == "tkinter"
        or name.startswith("tkinter.")
        or name == "fold_designer_bridge"
        or name.startswith("gui")
        or name.startswith("matplotlib")
    )
    assert forbidden == []
