"""#2517: CornerType physical CUTTING/BEND thumbnails use the public Engine API."""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

import pytest

import ae_engine
from ae_engine import manufacturing_api
from ae_engine.corner_type_ui import build_corner_type_preview_geometry
from ae_engine.sheetmetal_geometry import (
    CornerTypeId, CornerTypeSelection, CrossCornerMode, CornerDirection,
)
from gui_modules.parts.panels import assembly_corner


@pytest.mark.parametrize("selection", (
    CornerTypeSelection(CornerTypeId.CROSS),
    CornerTypeSelection(CornerTypeId.INSERT),
    CornerTypeSelection(CornerTypeId.OVERLAY),
    CornerTypeSelection(CornerTypeId.INSERT_OVERLAY),
    CornerTypeSelection(CornerTypeId.C02, 1),
    CornerTypeSelection(
        CornerTypeId.CROSS, cross_mode=CrossCornerMode.RETAIN,
        direction=CornerDirection.WIDTH, amount_t=1.0,
    ),
))
def test_public_preview_is_exact_original_canonical_cutting_and_bend_geometry(selection):
    assert manufacturing_api.project_operator_corner_type_preview_geometry is build_corner_type_preview_geometry
    assert ae_engine.project_operator_corner_type_preview_geometry is build_corner_type_preview_geometry
    assert "project_operator_corner_type_preview_geometry" in ae_engine.__all__
    unchanged = deepcopy(selection)
    preview = manufacturing_api.project_operator_corner_type_preview_geometry(selection)
    assert preview == build_corner_type_preview_geometry(selection)
    assert preview.cut_paths and preview.bend_paths
    assert selection == unchanged


def test_gui_icon_calls_public_engine_preview_and_only_draws_returned_paths(monkeypatch):
    selected = CornerTypeSelection(CornerTypeId.CROSS)
    calls = []
    owner = manufacturing_api.project_operator_corner_type_preview_geometry

    def capture(selection):
        calls.append(selection)
        return owner(selection)

    monkeypatch.setattr(
        manufacturing_api, "project_operator_corner_type_preview_geometry", capture,
    )

    class Canvas:
        def __init__(self):
            self.paths = []
            self.deleted = []

        def delete(self, target):
            self.deleted.append(target)

        def cget(self, name):
            return {"width": "110", "height": "90"}[name]

        def create_line(self, *coords, **kwargs):
            self.paths.append((coords, kwargs))

    canvas = Canvas()
    assembly_corner.draw_corner_type_icon(None, canvas, selected)
    assert calls == [selected]
    preview = owner(selected)
    assert canvas.deleted == ["all"]
    assert len(canvas.paths) == len(preview.cut_paths) + len(preview.bend_paths)
    assert sum(row[1]["fill"] == "#30d158" for row in canvas.paths) == len(preview.cut_paths)
    assert sum(row[1]["fill"] == "#0a84ff" for row in canvas.paths) == len(preview.bend_paths)


def test_gui_source_does_not_import_internal_canonical_corner_preview():
    path = Path(assembly_corner.__file__)
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert not any(
        isinstance(node, ast.ImportFrom) and node.module == "ae_engine.corner_type_ui"
        and any(alias.name == "build_corner_type_preview_geometry" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert "manufacturing_api.project_operator_corner_type_preview_geometry(selection)" in source


def test_bad_public_preview_source_is_rejected_without_changing_real_selection():
    selection = CornerTypeSelection(CornerTypeId.CROSS)
    unchanged = deepcopy(selection)
    with pytest.raises((ValueError, TypeError, AttributeError)):
        manufacturing_api.project_operator_corner_type_preview_geometry("NOT_A_CORNER")
    assert selection == unchanged
