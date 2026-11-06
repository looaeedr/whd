"""#2517 candidate stage checks are Engine-owned, Session stays GUI-owned."""
from hashlib import sha256
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_features import (
    CircleFeature, FeatureAnchor, Vec2, feature_surface_from_rect,
)
from gui_modules.editors.cadcraft_command_session_bridge import stage_verified_cadcraft_drawing
from phase6_hole_editor_session import Phase6HoleEditorSession


def _fixture(tmp_path):
    surface = feature_surface_from_rect("cadcraft-stage-engine", Vec2(0, 0), Vec2(300, 300))
    current = CircleFeature(6, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(25, 25))
    candidate = CircleFeature(10, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(140, 140))
    path = tmp_path / "isolated.dxf"
    doc = ezdxf.new("R2010", units=ezdxf.units.MM)
    doc.modelspace().add_circle((140, 140), 5)
    doc.saveas(path)
    return surface, current, candidate, path


def test_engine_verifies_file_and_gui_only_stages_original_session(tmp_path):
    surface, current, candidate, path = _fixture(tmp_path)
    digest = api.verify_cadcraft_verified_candidate_stage(
        path, (candidate,), (current,), surface, 300, 300,
    )
    assert digest == sha256(path.read_bytes()).hexdigest()
    features = [current]
    session = Phase6HoleEditorSession("cadcraft-stage-engine", features)
    preview = stage_verified_cadcraft_drawing(
        output=path, whd_candidates=(candidate,), session=session,
        surface=surface, width=300, height=300,
    )
    assert preview.output_sha256 == digest
    assert session.has_active_edit
    preview.cancel()
    assert features == [current] and not session.has_active_edit


def test_direct_engine_rejects_bad_units_collision_and_missing_file(tmp_path):
    surface, current, candidate, path = _fixture(tmp_path)
    with pytest.raises(api.CadcraftCommandProofError, match="WHD_FEATURE_COLLISION"):
        api.verify_cadcraft_verified_candidate_stage(
            path, (current,), (current,), surface, 300, 300,
        )
    doc = ezdxf.readfile(path)
    doc.header["$INSUNITS"] = 1
    doc.saveas(path)
    with pytest.raises(api.CadcraftCommandProofError, match="MILLIMETRE_HEADER_MISMATCH"):
        api.verify_cadcraft_verified_candidate_stage(
            path, (candidate,), (current,), surface, 300, 300,
        )
    with pytest.raises(api.CadcraftCommandProofError, match="CADCRAFT_STAGE_VALIDATION_FAILED"):
        api.verify_cadcraft_verified_candidate_stage(
            tmp_path / "missing.dxf", (candidate,), (current,), surface, 300, 300,
        )


def test_phase6_session_adapter_has_no_geometry_or_raw_dxf_owner():
    root = Path(__file__).resolve().parents[1]
    code = (root / "gui_modules/editors/cadcraft_command_session_bridge.py").read_text(
        encoding="utf-8"
    )
    assert "verify_cadcraft_verified_candidate_stage(" in code
    assert "from ae_engine.sheetmetal_features import" not in code
    assert "feature_is_strictly_within_surface" not in code
    assert "resolve_surface_features" not in code
    assert "verify_dxf(" not in code
    assert api.CADCRAFT_MAX_EXCHANGE_BYTES == 3_000_000
