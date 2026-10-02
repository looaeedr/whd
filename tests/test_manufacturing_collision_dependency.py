from __future__ import annotations

import ast
from pathlib import Path

from shapely.geometry import box

from ae_engine.contracts import FinalMaterialCollisionPart
from ae_engine.manufacturing_api import PartRenderData, collision_part_from_render_data


def test_assembly_collision_does_not_import_manufacturing_api():
    path = Path(__file__).parents[1] / "ae_engine" / "assembly_collision.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
    assert not any(name.endswith("manufacturing_api") for name in imported)


def test_neutral_collision_contract_is_gui_independent_and_immutable():
    material = box(0, 0, 10, 10)
    render = PartRenderData(scene=object(), material=material, metadata={"source": "test"})
    contract = collision_part_from_render_data("head", render, true_thickness=2.0)
    assert isinstance(contract, FinalMaterialCollisionPart)
    assert contract.part_id == "head"
    assert contract.material.equals(material)
    assert contract.true_thickness == 2.0
    assert contract.diagnostic_metadata == {"source": "test"}
