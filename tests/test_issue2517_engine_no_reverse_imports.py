"""#2517: the manufacturing Engine must never reverse-import GUI/Phase6."""
from __future__ import annotations

import ast
from pathlib import Path

from ae_engine.assembly_geometry import build_joint_world_geometry
from ae_engine.box_body_structure_state import (
    back_panel_mode, set_side_back_back_panel_mode,
)
from ae_engine.receiving_quantity_versions import (
    QuantityModel, SCHEMA_V3, normalize_quantity_snapshot,
    quantity_inherited_nfb_brand_conflicts,
)
from phase6_box_body_structure import (
    back_panel_mode as old_back_panel_mode,
    set_side_back_back_panel_mode as old_set_back_panel_mode,
)
from phase6_quantity_model import (
    QuantityModel as old_quantity_model,
    SCHEMA_V3 as old_schema_v3,
    normalize_quantity_snapshot as old_normalize,
    quantity_inherited_nfb_brand_conflicts as old_brand_conflicts,
)


def test_phase6_aliases_preserve_exact_engine_owner_identity():
    assert back_panel_mode is old_back_panel_mode
    assert set_side_back_back_panel_mode is old_set_back_panel_mode
    assert QuantityModel is old_quantity_model
    assert SCHEMA_V3 == old_schema_v3
    assert normalize_quantity_snapshot is old_normalize
    assert quantity_inherited_nfb_brand_conflicts is old_brand_conflicts


def test_all_engine_modules_forbid_static_reverse_imports():
    paths = sorted(Path("ae_engine").rglob("*.py"))
    assert len(paths) >= 260, "the check must inspect the real whole Engine"
    blocked_roots = ("phase6_", "gui_modules", "fold_designer_bridge", "tkinter")
    for path in paths:
        code = path.read_text(encoding="utf-8")
        tree = ast.parse(code, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                name = node.module or ""
                # Dotted relative paths are Engine-internal, never Phase6.
                if node.level == 0:
                    assert not name.startswith(blocked_roots) and name != "gui", (
                        path, node.lineno, name,
                    )
            elif isinstance(node, ast.Import):
                for entry in node.names:
                    assert not entry.name.startswith(blocked_roots) and entry.name != "gui", (
                        path, node.lineno, entry.name,
                    )


def test_check_and_marking_use_original_engine_world_geometry():
    for path in (
        Path("ae_engine/receiving_fixed_plate_side_check_dxf.py"),
        Path("ae_engine/receiving_joint_marking.py"),
    ):
        code = path.read_text(encoding="utf-8")
        assert "from .assembly_geometry import build_joint_world_geometry as _phase6_build_joint_world_geometry" in code
    assert callable(build_joint_world_geometry)
