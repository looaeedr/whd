"""#2517: GUI project exports enter Engine public API; Engine never imports GUI."""
from __future__ import annotations

import importlib
import inspect
from pathlib import Path

import pytest

from ae_engine import manufacturing_api
from ae_engine.manufacturing_equivalence import ManufacturingParameters
from ae_engine.receiving_nfb_model_identity import parse_numeric_model_ref


def test_engine_public_export_primitives_reuse_existing_sources():
    assert manufacturing_api.parse_numeric_model_ref is parse_numeric_model_ref
    assert manufacturing_api.ManufacturingParameters is ManufacturingParameters
    assert manufacturing_api.safe_dxf_part_stem("a/b") == "a_b"
    assert callable(manufacturing_api.door_layout_export_filename)
    assert callable(manufacturing_api.normalize_receiving_layout)
    assert callable(manufacturing_api.project_common_box)


@pytest.mark.parametrize("name,module_name,args,kwargs", [
    ("export_current_csv_quantity_manufacturing",
     "ae_engine.receiving_csv_quantity_manufacturing",
     ("batch", "folder"), {"flags": {"door": True}, "overwrite": True}),
    ("export_current_receiving_multibay_dxf",
     "ae_engine.receiving_csv_multibay_manufacturing",
     ("snapshot",), {"physical_bay_geometry_provider": None,
                      "flags": {"door": True}, "output_dir": "folder",
                      "overwrite": True}),
    ("export_receiving_ear_side_manufacturing_marking_dxf",
     "ae_engine.receiving_ear_side_manufacturing_marking",
     ("snapshot", "geometry", "folder"),
     {"dimensions": (800, 1600, 350), "sheet_thickness": 2,
      "overwrite": False}),
    ("export_receiving_ear_side_check_only_dxf",
     "ae_engine.receiving_fixed_plate_side_check_dxf",
     ("snapshot", "geometry", "folder"),
     {"dimensions": (800, 1600, 350), "sheet_thickness": 2,
      "overwrite": False}),
    ("export_verified_pad_base_part_only",
     "ae_engine.receiving_nfb_pad_pair_manufacturing",
     ("snapshot", ("parts",), "folder"),
     {"version_id": "v1", "box_count": 2,
      "parameters": ManufacturingParameters("steel", 2, "process")}),
])
def test_public_export_routes_exact_arguments_without_bypass(
    monkeypatch, name, module_name, args, kwargs,
):
    module = importlib.import_module(module_name)
    marker = object()
    seen = []
    def implementation(*a, **k):
        seen.append((a, k))
        return marker
    monkeypatch.setattr(module, name, implementation)
    assert getattr(manufacturing_api, name)(*args, **kwargs) is marker
    assert seen == [(args, kwargs)]


def test_engine_quantity_selection_no_gui_reverse_import():
    from ae_engine import receiving_csv_quantity_manufacturing as quantity
    source = inspect.getsource(quantity.export_current_csv_quantity_manufacturing)
    assert "from .manufacturing_export_selection import resolved_export_intention_key" in source
    assert "gui_modules.project.export_actions" not in source


def test_gui_export_never_imports_private_manufacturing_modules():
    root = Path(__file__).resolve().parents[1]
    source = (root / "gui_modules/project/export_actions.py").read_text(encoding="utf-8")
    assert "from ae_engine import manufacturing_api" in source
    assert "from ae_engine." not in source
    for name in (
        "export_current_csv_quantity_manufacturing",
        "export_current_receiving_multibay_dxf",
        "export_receiving_ear_side_manufacturing_marking_dxf",
        "export_receiving_ear_side_check_only_dxf",
        "export_verified_pad_base_part_only",
    ):
        assert f"manufacturing_api.{name}(" in source
