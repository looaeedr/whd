# -*- coding: utf-8 -*-
"""V5 confirmed CSV edits persist source-owned NFB rows without fake X approval."""
from hashlib import sha256

import pytest

from ae_engine.receiving_nfb_csv_committed_config import committed_csv_nfb_config
from ae_engine.receiving_nfb_model_identity import numeric_model_ref
from ae_engine.receiving_nfb_numeric_catalog import brand_csv_path, model_spec
from ae_engine.sheetmetal_feature_core import FeatureAnchor, ProfileFeature
from ae_engine.sheetmetal_geometry import Vec2


PART = "inner_door:upper:panel"


def _feature(layer, slot=0):
    brand, model = "士林", "2P400"
    spec = model_spec(brand, model)
    assert spec and spec.dimensionally_complete
    return ProfileFeature(
        points=tuple(Vec2(float(x), float(y))
                     for x, y in spec.opening_corners_xy_mm),
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(0., 0.), layer="CUTTING",
        source_type="NFB_CSV_SOURCE",
        source_params=(
            ("part_id", PART), ("brand", brand), ("model", model),
            ("layer_index", layer), ("slot_index", slot),
            ("csv_sha256", sha256(brand_csv_path(brand).read_bytes()).hexdigest()),
        ),
    )


def _config():
    model = numeric_model_ref("士林", "2P400")
    return {"layers": 2, "models": [model, model],
            "layer_heights_mm": [300., 800.]}


def test_editor_confirm_builds_current_csv_config_with_no_fabricated_x_datum():
    rows = committed_csv_nfb_config(PART, [_feature(0), _feature(1)], _config())
    assert rows["layer_count"] == 2
    assert len(rows["holes"]) == 2
    assert [p["layer_index"] for p in rows["holes"]] == [0, 1]
    assert len({p["physical_hole_id"] for p in rows["holes"]}) == 2
    assert {p["model_filename"] for p in rows["holes"]} == {
        numeric_model_ref("士林", "2P400")
    }
    assert all(p["manual_x_state"] == "UNVERIFIED_BASIS"
               and p["manual_x_mm"] is None for p in rows["holes"])


@pytest.mark.parametrize("features,config", (
    ([_feature(0)], _config()),
    ([_feature(0), _feature(0)], _config()),
    ([_feature(0), _feature(1)], {"layers":2, "models":[
        numeric_model_ref("士林", "2P400"), "nfbv5:士林:3P400"],
        "layer_heights_mm":[300.,800.]}),
))
def test_missing_duplicate_or_changed_rows_cannot_submit(features, config):
    with pytest.raises(ValueError):
        committed_csv_nfb_config(PART, features, config)
