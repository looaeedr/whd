"""#2517: native, Receiving Bay and candidate EndCap editors share Engine geometry."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_features import (
    RectGuide, Vec2, resolve_endcap_finished_face_guide, feature_surface_from_rect,
)
from tests.test_issue2517_receiving_endcap_hole_context_api import _source


@pytest.mark.parametrize("role", ("head", "tail"))
@pytest.mark.parametrize("values", (
    (800.0, 350.0, 2.0), (920.25, 440.5, 1.6),
))
def test_real_endcap_face_and_guide_identical_to_engine_source(role, values):
    width, depth, thickness = values
    actual = api.project_operator_hole_editor_endcap(
        role, width=width, depth=depth, thickness=thickness,
    )
    guide = resolve_endcap_finished_face_guide(width, depth, thickness)
    assert actual.surface == feature_surface_from_rect(
        f"{role}_finished_face", guide.min_point, guide.max_point,
    )
    assert actual.reference_guide == RectGuide(
        Vec2(0, 0), Vec2(width, depth), "finished_boundary",
    )
    assert (actual.width, actual.height) == (width, depth)


@pytest.mark.parametrize("name", ("width", "depth", "thickness"))
@pytest.mark.parametrize("bad", (
    True, False, 0, -4, float("nan"), float("inf"), "invalid", None,
))
def test_raw_invalid_physical_source_must_not_become_valid_mm(name, bad):
    values = {"width": 800., "depth": 350., "thickness": 2.}
    values[name] = bad
    with pytest.raises(ValueError, match="包外尺寸"):
        api.project_operator_hole_editor_endcap("head", **values)


@pytest.mark.parametrize("role", ("door", "base_plate", "", None))
def test_unsupported_role_never_gets_editable_physical_geometry(role):
    with pytest.raises(ValueError, match="ENDCAP_HOLE_EDITOR_ROLE_INVALID"):
        api.project_operator_hole_editor_endcap(
            role, width=800, depth=350, thickness=2,
        )


@pytest.mark.parametrize("name", ("width", "depth"))
@pytest.mark.parametrize("bad", (True, float("nan"), float("inf"), -20, None))
def test_receiving_selected_bay_reuses_strict_engine_validation(name, bad):
    snapshot, layout, *_ = _source()
    source = deepcopy(layout)
    source["sets"][0]["bays"][1][name] = bad
    with pytest.raises(ValueError, match="包外尺寸"):
        api.project_receiving_endcap_hole_editor_context(
            snapshot, source, set_index=0, bay_index=1, role="head",
        )


@pytest.mark.parametrize("invalid", (True, float("nan"), 0, None))
def test_receiving_snapshot_thickness_cannot_be_cast_to_one_mm(invalid):
    snapshot, layout, *_ = _source()
    snapshot["t"] = invalid
    with pytest.raises(ValueError, match="T 包外尺寸"):
        api.project_receiving_endcap_hole_editor_context(
            snapshot, layout, set_index=0, bay_index=1, role="tail",
        )


def test_receiving_uses_same_public_surface_and_old_missing_t_default():
    snapshot, layout, *_ = _source()
    snapshot.pop("t")
    result = api.project_receiving_endcap_hole_editor_context(
        snapshot, layout, set_index=0, bay_index=1, role="head",
    )
    expected = api.project_operator_hole_editor_endcap(
        "head", width=920, depth=440, thickness=2,
    )
    assert result.surface == expected.surface
    assert result.reference_guide == expected.reference_guide
    assert (result.width, result.depth) == (expected.width, expected.height)


def test_gui_main_and_candidate_delegate_without_second_geometry_implementation():
    root = Path(__file__).resolve().parents[1]
    main = (root / "gui_modules/editors/hole_editor.py").read_text(encoding="utf-8")
    assert "manufacturing_api.project_operator_hole_editor_endcap(" in main
    assert "manufacturing_api.feature_to_legacy_hole(" in main
    assert "manufacturing_api.legacy_hole_to_feature(" in main
    assert "resolve_endcap_finished_face_guide(" not in main
    candidate = (root / "gui_modules/application/fold_designer_composition_receiving.py"
                 ).read_text(encoding="utf-8").split("def edit_candidate(")[1].split(
                     "def copy_candidate("
                 )[0]
    assert "manufacturing_api.project_operator_hole_editor_endcap(" in candidate
    assert "float(bay[" not in candidate
    assert "feature_surface_from_rect(" not in candidate
    assert "RectGuide(" not in candidate
    engine = (root / "ae_engine/operator_receiving_endcap_hole_context.py"
              ).read_text(encoding="utf-8")
    assert "project_operator_hole_editor_endcap(" in engine
    assert 'float(bay["width"])' not in engine
