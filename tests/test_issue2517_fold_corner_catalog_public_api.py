"""#2517: Fold Designer CornerType catalog must come from the public Engine."""
from copy import deepcopy
from inspect import getsource

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.cabinet_model_choices import (
    project_operator_corner_selection_catalog as original_owner,
)
from ae_engine.sheetmetal_geometry import (
    EDITABLE_CORNER_TYPE_IDS, CORNER_TYPE_LABELS,
)
import fold_designer_bridge as bridge


def test_facade_root_and_canonical_owner_are_one_catalog_callable():
    assert ae_engine.project_operator_corner_selection_catalog is (
        api.project_operator_corner_selection_catalog
    )
    assert api.project_operator_corner_selection_catalog is original_owner
    assert "project_operator_corner_selection_catalog" in ae_engine.__all__


def test_existing_engine_catalog_contains_exact_corner_types_and_labels():
    expected = tuple((i.value, CORNER_TYPE_LABELS[i]) for i in EDITABLE_CORNER_TYPE_IDS)
    original_models = ["金庫型", "未知類型", "自訂"]
    before = deepcopy(original_models)
    for model, editable in (
        ("自訂", True), ("未知類型", True),
        ("金庫型", False), ("受電箱", False),
    ):
        catalog = api.project_operator_corner_selection_catalog(
            model, original_models,
        )
        assert catalog.labels == expected
        assert catalog.editable is editable
        assert original_models == before


def test_fold_designer_consumes_public_catalog_without_private_enum_decisions():
    catalog = api.project_operator_corner_selection_catalog(
        api.operator_default_custom_model_name, (),
    )
    expected = catalog.labels
    assert bridge._CORNER_TYPE_LABEL_ITEMS == expected
    assert bridge._CORNER_TYPE_IDS == tuple(type_id for type_id, _ in expected)
    assert bridge._CORNER_TYPE_LABEL_BY_ID == dict(expected)
    assert bridge._CORNER_TYPE_BY_LABEL == {
        label: type_id for type_id, label in expected
    }
    source = getsource(bridge)
    assert "manufacturing_api.project_operator_corner_selection_catalog(" in source
    assert "EDITABLE_CORNER_TYPE_IDS" not in source
    assert "CORNER_TYPE_LABELS" not in source
    assert "from ae_engine.cabinet_model_choices import" not in source
