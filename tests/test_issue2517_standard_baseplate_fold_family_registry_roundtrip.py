"""#2517: physical Receiving BasePlate Fold builds and saves by Engine Family identity."""
from __future__ import annotations

from copy import deepcopy
import inspect

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.cabinet_types.policy import canonical_family_name
from ae_engine.sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_LEFT
from ae_engine.standard_part_fold_profiles import build_standard_part_fold_profiles
from ae_engine.standard_part_fold_readback import read_standard_part_fold_profiles
import phase6_fold_profiles as gui
import phase6_project_file as project


def _configured(model="受電箱", *, cabinet_type=False):
    result = {
        "w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0,
        "base_plate_bend": 29.0,
        "receiving_base_plate": {
            "pattern": RECEIVING_BASE_PATTERN_LEFT,
            "height": 340.0, "shrink_top": 20.0, "shrink_bottom": 20.0,
            "shrink_left": 45.0, "shrink_right": 45.0, "bend": 20.0,
        },
    }
    result["cabinet_type" if cabinet_type else "model"] = model
    return result


@pytest.mark.parametrize("alias", [
    "受電箱", "RECEIVING", "receiving", "ReCeIvInG", "  receiving  ",
])
def test_configured_receiving_alias_build_and_saved_fold_readback_share_true_bend(alias):
    snapshot = _configured(alias)
    before = deepcopy(snapshot)
    assert canonical_family_name(snapshot) == "受電箱"
    physical = api.build_standard_part_fold_profiles(snapshot, "base_plate")
    assert physical == build_standard_part_fold_profiles(snapshot, "base_plate")
    # The certified LEFT source has one flat X face, not invented 29 mm
    # generic flanges. Y comes from the actual physical BEND20 stations.
    assert [row["phase6_key"] for row in physical["X"]] == [
        "receiving_flat_side_face",
    ]
    assert [row["phase6_key"] for row in physical["Y"]] == [
        "receiving_bottom_fold_20",
        "receiving_base_face_height",
        "receiving_top_fold_20",
    ]
    assert physical["Y"][0]["len"] == pytest.approx(20.0)
    assert physical["Y"][-1]["len"] == pytest.approx(20.0)
    assert api.read_standard_part_fold_profiles(
        "base_plate", physical, snapshot,
    ) == {}
    assert read_standard_part_fold_profiles("base_plate", physical, snapshot) == {}
    assert snapshot == before


@pytest.mark.parametrize("alias", ["receiving", "ReCeIvInG"])
def test_saved_project_reload_keeps_same_physical_base_fold_and_not_generic_settings(tmp_path, alias):
    snapshot = _configured(alias)
    original = api.build_standard_part_fold_profiles(snapshot, "base_plate")
    target = project.write_project(
        tmp_path / "fold-physical-base.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": snapshot},
    )
    restored = project.read_project(target)["snapshot"]
    assert canonical_family_name(restored) == "受電箱"
    assert api.build_standard_part_fold_profiles(restored, "base_plate") == original
    assert api.read_standard_part_fold_profiles(
        "base_plate", original, restored,
    ) == {}
    assert restored["base_plate_bend"] == 29.0


def test_receiving_alias_from_saved_cabinet_type_uses_same_physical_profiles():
    saved = _configured("receiving", cabinet_type=True)
    physical = api.build_standard_part_fold_profiles(saved, "base_plate")
    assert len(physical["X"]) == 1
    assert api.read_standard_part_fold_profiles("base_plate", physical, saved) == {}


def test_vault_and_unconfigured_receiving_keep_existing_generic_editor_behavior():
    for snapshot in (
        {"model": "金庫型", **{k: v for k, v in _configured().items() if k != "model"}},
        {"model": "receiving", "w": 800, "h": 1600, "t": 2, "base_plate_bend": 29},
    ):
        before = deepcopy(snapshot)
        rows = api.build_standard_part_fold_profiles(snapshot, "base_plate")
        assert [row.get("phase6_key") for row in rows["X"]] == [
            "base_bend_l", "base_face_w", "base_bend_r",
        ]
        assert api.read_standard_part_fold_profiles(
            "base_plate", rows, snapshot,
        ) == {"base_plate_bend": 29.0}
        assert snapshot == before


def test_invalid_configured_receiving_base_does_not_fall_back_to_generic_fold():
    source = _configured("receiving")
    source["receiving_base_plate"]["bend"] = -1.0
    before = deepcopy(source)
    with pytest.raises(ValueError):
        api.build_standard_part_fold_profiles(source, "base_plate")
    assert source == before


def test_gui_and_engine_use_one_family_registry_for_physical_base_fold():
    source = inspect.getsource(build_standard_part_fold_profiles)
    readback = inspect.getsource(read_standard_part_fold_profiles)
    for code in (source, readback):
        assert "canonical_family_name(" in code
        assert 'in {"受電箱", "RECEIVING"}' not in code
    facade = inspect.getsource(gui.build_endcap_xy_profiles)
    assert "manufacturing_api.build_endcap_xy_fold_profiles" in facade
