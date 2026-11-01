"""#2517 Fold Designer Receiving BasePlate real source priority is Engine-owned."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api, resolve_fold_designer_base_plate_source
from ae_engine import operator_auxiliary_part_specs as owner
from gui_modules.application import fold_designer_manufacturing_projection as gui
from ae_engine.sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_CENTER


def payload(model="受電箱"):
    return {
        "model": model, "w": 800.0, "h": 1600.0, "t": 2.0, "fw": 25.0,
        "base_plate_shrink_top": 3.0,
        "base_plate_shrink_bottom": 4.0,
        "base_plate_shrink_left": 5.0,
        "base_plate_shrink_right": 6.0,
        "base_plate_bend": 12.0,
        "receiving_base_plate": {
            "pattern": RECEIVING_BASE_PATTERN_CENTER,
            "height": 280.0, "shrink_top": 20.0,
            "shrink_bottom": 20.0, "shrink_left": 85.0,
            "shrink_right": 85.0, "bend": 20.0,
        },
    }


def request(data, key="base_plate", policy=None):
    return resolve_fold_designer_base_plate_source(
        key, data, width=800, height=1600, thickness=2,
        frame_width=25, model_name=data["model"], corner_policy=policy,
    )


def test_real_receiving_manual_preview_uses_existing_physical_source_without_mutation():
    data = payload()
    saved = json.loads(json.dumps(data, ensure_ascii=False))
    values, policy = request(saved, policy=object())
    assert manufacturing_api.resolve_fold_designer_base_plate_source is resolve_fold_designer_base_plate_source
    assert policy is None
    assert values["h"] == 280.0
    assert values["base_plate_shrink_top"] == 20.0
    assert values["base_plate_shrink_left"] == 85.0
    assert values["base_plate_bend"] == 20.0
    assert values["receiving_bend_pattern"] == RECEIVING_BASE_PATTERN_CENTER
    assert values["physical_id"] == "base_plate"
    assert saved == data


@pytest.mark.parametrize("model", ("金庫型", "自訂", "未知類型"))
def test_other_families_never_borrow_receiving_source_or_drop_corner_policy(model):
    data = payload(model)
    policy = object()
    values, selected = request(data, policy=policy)
    assert selected is policy
    assert values["h"] == 1600.0
    assert values["base_plate_bend"] == 12.0
    assert values["base_plate_shrink_left"] == 5.0
    assert values["receiving_bend_pattern"] is None
    assert values["model"] == model


def test_missing_receiving_config_is_preview_only_without_fabricated_pattern():
    data = payload()
    data.pop("receiving_base_plate")
    sentinel = object()
    values, policy = request(data, policy=sentinel)
    assert values["h"] == 1600.0
    assert values["base_plate_shrink_left"] == 5.0
    assert values["receiving_bend_pattern"] is None
    assert policy is sentinel


@pytest.mark.parametrize("key", ("base_plate_c1_r1", "base_plate_c2_r4"))
def test_receiving_cell_never_aliases_an_independently_sourced_plate(key):
    with pytest.raises(ValueError, match="RECEIVING_BASE_PLATE_LEGACY_CELL_UNSUPPORTED"):
        request(payload(), key=key)


def test_invalid_physical_config_not_silently_forged_into_generic(monkeypatch):
    def no_source(_):
        raise ValueError("RECEIVING_BASE_PLATE_CONFIG_INCOMPLETE")
    monkeypatch.setattr(
        "ae_engine.receiving_base_plate_config.receiving_base_plate_values", no_source,
    )
    with pytest.raises(ValueError, match="CONFIG_INCOMPLETE"):
        request(payload())


def test_gui_no_longer_owns_receiving_artefact_source_or_corner_policy(monkeypatch):
    called = []
    expected_values = {"source": "Engine"}
    sentinel_policy = object()
    rendered = object()
    def engine(part, snapshot, **kwargs):
        called.append(("source", part, snapshot, kwargs))
        return expected_values, sentinel_policy
    monkeypatch.setattr(manufacturing_api, "resolve_fold_designer_base_plate_source", engine)
    class Host:
        def _fold_designer_corner_policy_from_payload(self, state, part, fw):
            return object()
        def _apply_cabinet_family_endcap_policy(self, policy, part, **kwargs):
            return policy
        def _base_plate_part_spec_from_values(self, values, *, features, corner_policy):
            called.append(("spec", values, features, corner_policy))
            return rendered
    original = payload()
    result, context = gui._fold_designer_part_spec_from_payload(Host(), "base_plate", original)
    assert result is rendered
    assert called[0][0] == "source" and called[0][1] == "base_plate"
    assert called[0][2]["model"] == "受電箱"
    assert called[0][3]["width"] == 800.0 and called[0][3]["height"] == 1600.0
    assert called[1] == ("spec", expected_values, (), sentinel_policy)
    code = inspect.getsource(gui._fold_designer_part_spec_from_payload)
    block = code.split('elif key == "base_plate" or key.startswith("base_plate_c"):')[1].split('elif key == "indicator_box":')[0]
    assert "manufacturing_api.resolve_fold_designer_base_plate_source(" in block
    assert "receiving_base_plate_values(" not in block
    assert "values.update(physical)" not in block
    assert "policy = None" not in block
    assert "base_plate_bend" not in block
