"""#2517: FinalScene 3D/unfold info must read the same physical Fold as editor."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
import inspect

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import project_operator_fold_editor_display_rows as engine_project
from phase6_final_scene_contracts import FinalSceneViewRequest
from phase6_final_scene_projection import (
    _phase6_profile_operator_fold_values as ui_projection,
    format_operator_info_text,
)
import phase6_final_scene_projection as ui_module
import phase6_final_scene_view as public_view
import phase6_project_file as project


def _profiles():
    # Legacy metadata intentionally disagrees with actual adjacent BENDs.
    x = [
        {"len": 22.0, "angle": 90.0, "ui_len_add": 999.0},
        {"len": 500.0, "core": "W", "angle": -90.0, "ui_len_add": -300.0},
        {"len": 22.0, "phase6_ui_sign": -1.0, "ui_len_add": 999.0},
    ]
    y = [
        {"len": 20.0, "angle": 0.0, "ui_len_add": 900.0},
        {"len": 800.0, "core": "H"},
        {"len": 21.0, "ui_len_add": "stale"},
    ]
    return x, y


def _request(x, y, *, thickness=2.0):
    return FinalSceneViewRequest(
        render_data=SimpleNamespace(pieces=()),
        x_profile=tuple(x), y_profile=tuple(y),
        part_key="door", thickness=thickness,
        finished_dimensions=(800.0, 1600.0),
    )


def test_real_finalscene_typed_request_uses_live_bends_and_T_not_serialized_ui_len_add():
    x, y = _profiles()
    original = deepcopy((x, y))
    request = _request(x, y, thickness=3.0)

    expected = tuple(
        abs(float(row["len"]))
        for row in api.project_operator_fold_editor_display_rows(x, 3.0)
        if not row.get("core")
    )
    assert expected == (25.0, 25.0)
    assert ui_projection(x, thickness=3.0) == list(expected)
    assert ui_projection(y, thickness=3.0) == [20.0, 21.0]
    info = format_operator_info_text(request)
    assert "折後包外：W 800 × H 1600 mm" in info
    assert "X折：25 / 25   Y折：20 / 21" in info
    assert "999" not in info and "900" not in info
    assert (x, y) == original
    assert engine_project is api.project_operator_fold_editor_display_rows
    assert public_view.format_operator_info_text is format_operator_info_text


def test_real_project_save_reload_keeps_material_but_finalscene_info_recomputes(tmp_path):
    x, y = _profiles()
    saved = {"model": "金庫型", "box_body_fold_profile": x,
             "view_y_profile": y}
    before = deepcopy(saved)
    target = project.write_project(tmp_path / "info-physical-source.p6fold", {
        "schema": project.PROJECT_SCHEMA, "snapshot": saved,
    })
    restored = project.read_project(target)["snapshot"]
    assert restored["box_body_fold_profile"] == x
    assert restored["view_y_profile"] == y
    text = format_operator_info_text(_request(
        restored["box_body_fold_profile"], restored["view_y_profile"],
    ))
    assert "X折：24 / 24   Y折：20 / 21" in text
    assert saved == before


def test_removed_bend_clears_stale_outside_compensation_in_both_operator_views():
    rows = [
        {"len": 24, "angle": 0, "ui_len_add": 400},
        {"len": 150, "core": "W", "ui_len_add": 400},
        {"len": 26, "ui_len_add": 400},
    ]
    old = deepcopy(rows)
    assert [abs(float(row["len"])) for row in engine_project(rows, 2)
            if not row.get("core")] == [24.0, 26.0]
    assert ui_projection(rows, thickness=2.0) == [24.0, 26.0]
    assert rows == old


@pytest.mark.parametrize("bad", (
    True, False, None, "", "bad", "nan", "inf",
    float("nan"), float("inf"), float("-inf"),
))
def test_invalid_material_fold_not_turned_into_fake_zero_in_operator_info(bad):
    rows = [{"len": bad, "angle": 90}, {"len": 200, "core": "W"}]
    original = deepcopy(rows)
    with pytest.raises(ValueError, match="FOLD_EDITOR_SOURCE_INVALID:len"):
        engine_project(rows, 2.0)
    with pytest.raises(ValueError, match="FOLD_EDITOR_SOURCE_INVALID:len"):
        ui_projection(rows, thickness=2.0)
    with pytest.raises(ValueError, match="FOLD_EDITOR_SOURCE_INVALID:len"):
        format_operator_info_text(_request(rows, ()))
    # NaN is not equal to itself, so identity/source layout is checked.
    assert rows[0]["len"] is bad or (isinstance(bad, float) and
                                        str(rows[0]["len"]) == str(bad))
    assert rows[1] == original[1]


@pytest.mark.parametrize("bad", (True, False, "bad", "nan", float("inf")))
def test_invalid_authored_bend_angle_fails_closed_before_ui_or_engine_projection(bad):
    rows = [{"len": 20, "angle": bad}, {"len": 50}]
    with pytest.raises(ValueError, match="FOLD_EDITOR_SOURCE_INVALID:angle"):
        ui_projection(rows, thickness=2)
    with pytest.raises(ValueError, match="FOLD_EDITOR_SOURCE_INVALID:angle"):
        engine_project(rows, 2)


@pytest.mark.parametrize("bad", (None, 0, -1, True, False, "nan", float("inf")))
def test_nonphysical_T_not_used_to_fabricate_finalscene_fold_information(bad):
    rows = [{"len": 20, "angle": 90}, {"len": 200}]
    with pytest.raises(ValueError, match="FOLD_EDITOR_SOURCE_INVALID:thickness"):
        ui_projection(rows, thickness=bad)
    with pytest.raises(ValueError, match="FOLD_EDITOR_SOURCE_INVALID:thickness"):
        format_operator_info_text(_request(rows, (), thickness=bad))


def test_legacy_none_angle_retains_flat_bend_compatibility():
    rows = [{"len": 20.0, "angle": None, "ui_len_add": 40},
            {"len": 50.0}]
    assert ui_projection(rows, thickness=2.0) == [20.0, 50.0]


def test_gui_info_text_owns_only_formatting_not_bend_compensation():
    source = inspect.getsource(ui_module._phase6_profile_operator_fold_values)
    formatted = inspect.getsource(ui_module.format_operator_info_text)
    assert "manufacturing_api.project_operator_fold_editor_display_rows(" in source
    assert "engine_segment_length_to_ui(" not in source
    assert "except Exception" not in source
    assert "request.y_profile, thickness=thickness" in formatted
    assert "request.x_profile, thickness=thickness" in formatted
    assert "apply_outside_dimension_compensation(" not in formatted
