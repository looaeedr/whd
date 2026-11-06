"""#2517 CADCraft manual return geometry and DXF proof: one Engine API."""
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_features import (
    CircleFeature, FeatureAnchor, Vec2, feature_surface_from_rect,
)
from gui_modules.editors.cadcraft_manual_hole_return_bridge import _dxf_moves
from gui_modules.editors.cadcraft_new_hole_import import new_hole_from_cadcraft_entity
from tools.issue1959_whd_cadcraft_command_draw import (
    CadcraftCommandProofError, from_whd_resolved,
)


def test_manual_return_engine_and_legacy_bridge_agree_on_verified_features(tmp_path):
    surface = feature_surface_from_rect("engine-cadcraft", Vec2(0, 0), Vec2(300, 300))
    originals = (CircleFeature(10, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(40, 40)),)
    path = tmp_path / "source.dxf"
    doc = ezdxf.new("R2010", units=ezdxf.units.MM)
    doc.modelspace().add_circle((40, 40), 5)
    doc.saveas(path)
    api.verify_cadcraft_manual_ticket_seed(path, originals, surface, 300, 300)
    doc = ezdxf.readfile(path)
    circle = list(doc.modelspace())[0]
    circle.dxf.center = (50, 45, 0)
    doc.modelspace().add_circle((180, 180), 8)
    doc.saveas(path)
    direct = api.project_cadcraft_manual_return_changes(path, originals, surface, 300, 300)
    assert direct == _dxf_moves(path, originals, surface, 300, 300)
    assert direct[1] == ((0, 10, 5),)
    assert len(direct[2]) == 1
    assert direct[2][0].diameter == 16
    assert direct[2][0] == new_hole_from_cadcraft_entity(list(ezdxf.readfile(path).modelspace())[1])


def test_engine_rejects_untrusted_return_without_gui_session_changes(tmp_path):
    surface = feature_surface_from_rect("engine-cadcraft-reject", Vec2(0, 0), Vec2(300, 300))
    originals = (CircleFeature(10, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(40, 40)),)
    path = tmp_path / "reject.dxf"
    doc = ezdxf.new("R2010", units=ezdxf.units.MM)
    doc.modelspace().add_circle((40, 40), 5)
    doc.saveas(path)
    doc = ezdxf.readfile(path)
    doc.header["$INSUNITS"] = 1
    doc.saveas(path)
    with pytest.raises(CadcraftCommandProofError, match="MILLIMETRE_HEADER_MISMATCH"):
        api.project_cadcraft_manual_return_changes(path, originals, surface, 300, 300)


def test_public_engine_owns_manual_geometry_and_legacy_paths_are_presentation_only():
    root = Path(__file__).resolve().parents[1]
    for name in (
        "gui_modules/editors/cadcraft_new_hole_import.py",
        "gui_modules/editors/cadcraft_manual_hole_return_bridge.py",
        "gui_modules/editors/cadcraft_command_session_bridge.py",
    ):
        source = (root / name).read_text(encoding="utf-8")
        assert "from shapely.geometry import Point, Polygon" not in source
        assert "import ezdxf" not in source
    engine = (root / "ae_engine/cadcraft_manual_return.py").read_text(encoding="utf-8")
    assert "gui_modules" not in engine
    assert "phase6_" not in engine
    assert "from tools." not in engine
    assert api.CadcraftCommandProofError is CadcraftCommandProofError
