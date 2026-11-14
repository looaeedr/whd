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


@pytest.mark.parametrize("field", ("width", "depth", "thickness"))
@pytest.mark.parametrize("invalid", (10 ** 400, "1e10000"))
def test_endcap_editor_refuses_physical_overflow_before_geometry(field, invalid):
    """A huge persisted coordinate must not overflow into valid material mm."""
    values = {"width": 800, "depth": 350, "thickness": 2}
    values[field] = invalid
    with pytest.raises(ValueError, match="包外尺寸"):
        api.project_operator_hole_editor_endcap("head", **values)


def test_numeric_string_endcap_source_preserves_fractional_mm():
    """Legacy saved numeric strings retain canonical physical dimensions."""
    from_strings = api.project_operator_hole_editor_endcap(
        "tail", width="920.25", depth="440.5", thickness="1.6",
    )
    from_floats = api.project_operator_hole_editor_endcap(
        "tail", width=920.25, depth=440.5, thickness=1.6,
    )
    assert (from_strings.width, from_strings.height) == (920.25, 440.5)
    assert from_strings.surface == from_floats.surface
    assert from_strings.reference_guide == from_floats.reference_guide


def test_receiving_valid_fractional_string_source_equal_direct_engine_surface():
    """Saved Bay numeric strings and direct headless inputs share real geometry."""
    snapshot, layout, *_ = _source()
    snapshot["t"] = "1.6"
    bay = layout["sets"][0]["bays"][1]
    bay["width"], bay["depth"] = "920.25", "440.5"
    receiving = api.project_receiving_endcap_hole_editor_context(
        snapshot, layout, set_index=0, bay_index=1, role="head",
    )
    direct = api.project_operator_hole_editor_endcap(
        "head", width=920.25, depth=440.5, thickness=1.6,
    )
    assert (receiving.width, receiving.depth) == (920.25, 440.5)
    assert receiving.surface == direct.surface
    assert receiving.reference_guide == direct.reference_guide


@pytest.mark.parametrize("model", ("受電箱", "RECEIVING", "receiving"))
def test_quantity_endcap_uses_receiving_common_box_not_stale_global_dimensions(model):
    snapshot = {
        "model": model, "active_mode": "quantity",
        "w": 990, "d": 550, "t": 1.6,
        "receiving_quantity_box": {"w": 920, "h": 1800, "d": 430},
    }
    actual = api.project_operator_quantity_endcap_hole_editor_geometry(
        snapshot, role="head",
    )
    expected = api.project_operator_hole_editor_endcap(
        "head", width=920, depth=430, thickness=1.6,
    )
    assert actual == expected
    assert snapshot["w"] == 990
    fresh = api.project_operator_quantity_endcap_hole_editor_geometry(
        {**snapshot, "receiving_quantity_box": None}, role="tail",
    )
    assert fresh == api.project_operator_hole_editor_endcap(
        "tail", width=800, depth=350, thickness=1.6,
    )


@pytest.mark.parametrize("model", ("金庫型", "RO", "未知"))
def test_quantity_endcap_other_families_keep_their_own_source(model):
    actual = api.project_operator_quantity_endcap_hole_editor_geometry(
        {"model": model, "w": 650, "d": 280, "t": 2},
        role="tail",
    )
    assert actual == api.project_operator_hole_editor_endcap(
        "tail", width=650, depth=280, thickness=2,
    )


@pytest.mark.parametrize("changed", (
    {"t": True}, {"t": float("nan")}, {"t": 0}, {"t": float("inf")},
    {"receiving_quantity_box": {"w": True, "h": 1600, "d": 350}},
    {"receiving_quantity_box": {"w": 800, "h": 1600, "d": -40}},
    {"receiving_quantity_box": "invalid-source"},
))
def test_quantity_endcap_rejects_invalid_physical_source_without_ui_fallback(changed):
    source = {
        "model": "受電箱", "active_mode": "quantity",
        "w": 800, "d": 350, "t": 2,
        "receiving_quantity_box": {"w": 800, "h": 1600, "d": 350},
    }
    source.update(changed)
    with pytest.raises(ValueError):
        api.project_operator_quantity_endcap_hole_editor_geometry(
            source, role="head",
        )


def test_quantity_editor_port_is_public_engine_only_and_uses_actual_geometry():
    from types import SimpleNamespace
    from phase6_quantity_model import QuantityModel
    from gui_modules.application.quantity_version_ports import quantity_ports

    source = Path("gui_modules/application/quantity_version_ports.py").read_text(encoding="utf-8")
    assert "resolve_endcap_finished_face_guide(" not in source
    assert "feature_surface_from_rect(" not in source
    assert "require_valid_quantity_features(" not in source
    assert "manufacturing_api.project_operator_quantity_endcap_hole_editor_geometry(" in source
    assert "manufacturing_api.commit_operator_quantity_version_holes(" in source
    assert "manufacturing_api.require_valid_operator_quantity_features(" not in source
    from inspect import getsource
    # Validation moved into the canonical Engine transaction, not removed.
    assert "require_valid_quantity_features(candidate)" in getsource(
        api.commit_operator_quantity_version_holes
    )

    class Host:
        def __init__(self):
            self.args = None
            self.kwargs = None

        def scene(self):
            pass

        def _open_unified_hole_editor(self, *args, **kwargs):
            self.args, self.kwargs = args, kwargs
            return "real-editor-return"

    host = Host()
    model = QuantityModel()
    workspace = SimpleNamespace(
        quantity_model=model,
        snapshot=lambda: {"active_mode": "quantity", "quantity": model.snapshot()},
    )
    app = SimpleNamespace(
        designer_workspace=workspace,
        _phase6_input_snapshot={
            "active_mode": "quantity",
            "receiving_quantity_box": {"w": 920, "h": 1800, "d": 430},
        },
        _settings_values={"t": 1.6},
        _phase6_box_whd={"w": 990, "h": 1800, "d": 550},
        baseline_model_var=SimpleNamespace(get=lambda: "RECEIVING"),
        _scene_query_callback=host.scene,
    )
    ui = quantity_ports(SimpleNamespace(app=app), None)
    assert ui["holes"]("head") == "real-editor-return"
    geometry = api.project_operator_quantity_endcap_hole_editor_geometry(
        {"model": "RECEIVING", "t": 1.6,
         "receiving_quantity_box": {"w": 920, "h": 1800, "d": 430}},
        role="head",
    )
    assert host.args[2:] == (geometry.surface, geometry.width, geometry.height)
    assert host.kwargs["reference_guide"] == geometry.reference_guide
    app._settings_values["t"] = True
    with pytest.raises(ValueError):
        ui["holes"]("head")
    assert host.args[2:] == (geometry.surface, geometry.width, geometry.height)
