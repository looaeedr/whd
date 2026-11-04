"""#2517: Quantity common physical box policy is a public Engine API."""
from copy import deepcopy
from inspect import getsource

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.receiving_quantity_box import (
    BOX_KEY, normalize_common_box, project_common_box, update_common_box,
)
from gui_modules.application import fold_designer_composition_receiving as gui


def _quantity_source():
    return {
        "model": "受電箱", "active_mode": "quantity", "t": 2,
        BOX_KEY: {"w": 800, "h": 1600, "d": 350},
    }


def test_common_box_public_ports_preserve_original_engine_owner_and_projection():
    assert api.RECEIVING_QUANTITY_BOX_KEY == BOX_KEY
    assert api.normalize_common_box is normalize_common_box
    assert api.update_common_box is update_common_box
    assert api.project_common_box is project_common_box

    original = _quantity_source()
    before = deepcopy(original)
    result = api.update_common_box(original, {"w": 820, "h": 1600, "d": 350})
    assert original == before
    assert result[BOX_KEY]["w"] == 820
    assert result["receiving_layout"]["sets"][0]["bays"][0]["width"] == 820
    assert api.project_common_box(original) == project_common_box(original)


@pytest.mark.parametrize("invalid", [True, 0, -1, "nan", float("inf"), None])
def test_public_quantity_common_box_rejects_invalid_source_without_edit(invalid):
    snapshot = _quantity_source()
    before = deepcopy(snapshot)
    with pytest.raises(ValueError):
        api.update_common_box(snapshot, {"w": invalid})
    assert snapshot == before


def test_receiving_gui_never_imports_private_quantity_common_box_policy():
    source = getsource(gui)
    assert "from ae_engine.receiving_quantity_box import" not in source
    assert "manufacturing_api.update_common_box(" in source
    assert "manufacturing_api.normalize_common_box(" in source
    assert "manufacturing_api.project_common_box(" in source
    assert "manufacturing_api.RECEIVING_QUANTITY_BOX_KEY" in source
