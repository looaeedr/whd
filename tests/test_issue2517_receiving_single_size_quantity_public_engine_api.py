# -*- coding: utf-8 -*-
"""#2517: Quantity Single W/H/D + selected version count is one Engine API.

The GUI owns presentation only, never a second QuantityModel write or
manufacturing hole-placement source. Every failure keeps the entire source.
"""
from copy import deepcopy
from pathlib import Path

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.receiving_quantity_versions import QuantityModel
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from phase6_receiving_modes import fresh_receiving_mode


def _source():
    return fresh_receiving_mode(
        "quantity", {"w": 800, "h": 1600, "d": 350}, thickness=2,
    )


def _apply(source, *, width=800, height=1600, depth=350, count=2):
    return api.apply_operator_receiving_quantity_size_count(
        source, width=width, height=height, depth=depth, count=count,
    )


def test_root_and_facade_share_exact_two_public_engine_quantity_entrypoints():
    assert ae_engine.project_operator_receiving_quantity_size_count is (
        api.project_operator_receiving_quantity_size_count)
    assert ae_engine.apply_operator_receiving_quantity_size_count is (
        api.apply_operator_receiving_quantity_size_count)
    assert {"project_operator_receiving_quantity_size_count",
            "apply_operator_receiving_quantity_size_count"} <= set(ae_engine.__all__)


def test_selected_version_count_and_common_physical_dimensions_round_trip():
    source = _source()
    model = QuantityModel.from_payload(source["quantity"])
    first = model.selected_version_id
    selected = model.add_version()
    model.set_piece_count(3)
    source["quantity"] = model.snapshot()
    before = deepcopy(source)
    summary = api.project_operator_receiving_quantity_size_count(source)
    assert summary == {
        "width": 800.0, "height": 1600.0, "depth": 350.0,
        "count": 3, "total_count": 4, "version_count": 2,
    }
    projected = _apply(source, width=780, height=1700, depth=380, count=4)
    assert source == before
    assert projected is not source
    assert projected["active_mode"] == "quantity"
    assert (projected["w"], projected["h"], projected["d"]) == (780.0, 1700.0, 380.0)
    assert (projected["receiving_quantity_box"]["w"],
            projected["receiving_quantity_box"]["h"],
            projected["receiving_quantity_box"]["d"]) == (780.0, 1700.0, 380.0)
    versions = {r["version_id"]: r for r in projected["quantity"]["versions"]}
    assert versions[first]["piece_count"] == 1
    assert versions[selected]["piece_count"] == 4
    assert projected["quantity"]["selected_version_id"] == selected
    assert api.project_operator_receiving_quantity_size_count(projected) == {
        "width": 780.0, "height": 1700.0, "depth": 380.0,
        "count": 4, "total_count": 5, "version_count": 2,
    }


def test_engine_complete_projection_matches_original_canonical_owner_operations():
    source = _source()
    original = deepcopy(source)
    model = QuantityModel.from_payload(source["quantity"])
    model.set_piece_count(4)
    expected = api.update_common_box(
        source, {"w": 775, "h": 1640, "d": 365},
    )
    expected["quantity"] = model.snapshot()
    api.require_valid_operator_quantity_features(expected)
    actual = _apply(source, width=775, height=1640, depth=365, count=4)
    assert actual == expected
    assert source == original


def test_stale_root_alias_does_not_override_real_common_box_or_version():
    source = _source()
    source["w"] = 1234  # stale runtime projection, physical box is W800
    source["_receiving_runtime_selection"] = {
        "set_index": 99, "bay_index": 99, "set_id": "stale", "bay_id": "stale",
    }
    before = deepcopy(source)
    assert api.project_operator_receiving_quantity_size_count(source)["width"] == 800.0
    result = _apply(source, width=790, count=2)
    assert result["w"] == result["receiving_quantity_box"]["w"] == 790.0
    assert "_receiving_runtime_selection" not in result
    assert source == before


@pytest.mark.parametrize("fault,pattern", (
    ("wrong-model", "MODE_REQUIRED"),
    ("wrong-mode", "MODE_REQUIRED"),
    ("non-mapping", "MODE_REQUIRED"),
    ("missing-box", "SOURCE_REQUIRED"),
    ("missing-version", "SOURCE_REQUIRED"),
    ("corrupt-version", "不合法"),
    ("missing-t", "有限正數"),
    ("zero-t", "有限正數"),
    ("invalid-count", "正整數"),
    ("boolean-count", "正整數"),
    ("float-count", "正整數"),
    ("zero-w", "有限正數"),
    ("nan-w", "有限正數"),
    ("bad-d", "有限正數"),
))
def test_bad_input_cannot_write_count_or_synthetic_bay(fault, pattern):
    source = _source()
    values = {"width": 800, "height": 1600, "depth": 350, "count": 2}
    if fault == "wrong-model":
        source["model"] = "金庫型"
    elif fault == "wrong-mode":
        source["active_mode"] = "set_bay"
    elif fault == "non-mapping":
        source = None
    elif fault == "missing-box":
        del source["receiving_quantity_box"]
    elif fault == "missing-version":
        del source["quantity"]
    elif fault == "corrupt-version":
        source["quantity"] = {"schema": "bad"}
    elif fault == "missing-t":
        del source["t"]
    elif fault == "zero-t":
        source["t"] = 0
    elif fault == "invalid-count":
        values["count"] = -2
    elif fault == "boolean-count":
        values["count"] = True
    elif fault == "float-count":
        values["count"] = 2.5
    elif fault == "zero-w":
        values["width"] = 0
    elif fault == "nan-w":
        values["width"] = float("nan")
    elif fault == "bad-d":
        values["depth"] = float("inf")
    previous = deepcopy((source, values))
    with pytest.raises((ValueError, TypeError), match=pattern):
        api.apply_operator_receiving_quantity_size_count(source, **values)
    if fault not in ("nan-w", "bad-d"):
        assert (source, values) == previous
    else:
        assert source == previous[0]


def test_true_head_tail_finished_face_holes_remain_engine_validated_before_commit():
    original = _source()
    model = QuantityModel.from_payload(original["quantity"])
    # Initially inside the W800 endcap finished face, but not inside W700.
    hole = CircleFeature(
        diameter=8,
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(755, 80),
    )
    model.set_features("head", [hole])
    original["quantity"] = model.snapshot()
    before = deepcopy(original)
    with pytest.raises(ValueError, match="不能輸出 DXF|越界|失效"):
        _apply(original, width=700, count=3)
    assert original == before


def test_saved_quantity_dimensions_and_piece_count_survive_project_reload(tmp_path):
    import phase6_project_file as project
    source = _apply(_source(), width=775, height=1640, depth=365, count=3)
    target = project.write_project(
        tmp_path / "2517-quantity-size-count.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": source},
    )
    saved = project.read_project(target)["snapshot"]
    assert api.project_operator_receiving_quantity_size_count(saved) == {
        "width": 775.0, "height": 1640.0, "depth": 365.0,
        "count": 3, "total_count": 3, "version_count": 1,
    }
    assert api.project_common_box(saved)["receiving_quantity_box"]["w"] == 775.0


def test_real_single_settings_ports_only_submit_operator_values_to_public_engine():
    source = (Path(__file__).resolve().parents[1]
              / "gui_modules/application/fold_designer_composition_receiving.py")
    text = source.read_text(encoding="utf-8")
    block = text.split("    def single_size_quantity():", 1)[1].split(
        "    def edit_single_holes(", 1,
    )[0]
    assert "manufacturing_api.project_operator_receiving_quantity_size_count(" in block
    assert "manufacturing_api.apply_operator_receiving_quantity_size_count(" in block
    assert "from phase6_quantity_model import" not in block
    assert "QuantityModel.from_payload(" not in block
    assert "model.set_piece_count(" not in block
    assert "manufacturing_api.update_common_box(" not in block
    assert 'candidate["quantity"] =' not in block
    assert "manufacturing_api.require_valid_operator_quantity_features(" not in block
    assert "_apply_mode_snapshot(self, namespace, candidate)" in block
