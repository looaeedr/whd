"""#2517 Quantity canonical grouping + NFB CHECK/Q belong to Engine.

No factory rule duplicated in Phase6 or source CSV exporter. Existing end-to-end
#1501 NFB manifest/Q and #1502 CSV quantity tests remain canonical oracles.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from ae_engine import manufacturing_api
from ae_engine.manufacturing_value_thaw import thaw_manufacturing_value
from ae_engine.quantity_manufacturing_groups import (
    QuantityManufacturingBatch,
    quantity_manufacturing_groups,
    quantity_nfb_checked_manufacturing_groups,
)
from ae_engine.receiving_quantity_versions import QuantityModel
import ae_engine.receiving_csv_quantity_manufacturing as csv
import phase6_quantity_manufacturing as compat
import phase6_quantity_model as quantity_compat
from phase6_manufacturing_contracts import freeze_manufacturing_value


def test_old_quantity_exports_are_exact_engine_implementations():
    assert compat.QuantityManufacturingBatch is QuantityManufacturingBatch
    assert compat.quantity_manufacturing_groups is quantity_manufacturing_groups
    assert compat.quantity_nfb_checked_manufacturing_groups is quantity_nfb_checked_manufacturing_groups
    assert manufacturing_api.QuantityManufacturingBatch is QuantityManufacturingBatch
    assert manufacturing_api.quantity_manufacturing_groups is quantity_manufacturing_groups
    assert manufacturing_api.quantity_nfb_checked_manufacturing_groups is quantity_nfb_checked_manufacturing_groups
    assert quantity_compat.QuantityModel is QuantityModel


def test_engine_thaw_preserves_integer_bay_ids_and_detaches_frozen_payload():
    frozen = freeze_manufacturing_value({
        "set_index": 0, "bay_index": 2,
        "groups": [{"source_part_id": "inner_door:bay-2:panel", "quantity": 3}],
        "t": 2.0,
    })
    thawed = thaw_manufacturing_value(frozen)
    assert (type(thawed["set_index"]), thawed["set_index"]) == (int, 0)
    assert (type(thawed["bay_index"]), thawed["bay_index"]) == (int, 2)
    assert thawed["groups"][0]["quantity"] == 3
    thawed["groups"][0]["quantity"] = 300
    assert thaw_manufacturing_value(frozen)["groups"][0]["quantity"] == 3


def test_fail_closed_nfb_check_uses_engine_batch_identity():
    batch = QuantityManufacturingBatch((), (), ())
    with pytest.raises(TypeError, match="boolean"):
        manufacturing_api.quantity_nfb_checked_manufacturing_groups(
            batch, live_manifest_provider=lambda *_: (), partial="yes",
        )
    with pytest.raises(ValueError, match="complete resolved quantity versions"):
        manufacturing_api.quantity_nfb_checked_manufacturing_groups(
            batch, live_manifest_provider=lambda *_: (), partial=True,
        )


def test_engine_csv_has_no_gui_or_phase6_runtime_imports():
    source = inspect.getsource(csv.export_current_csv_quantity_manufacturing)
    for forbidden in ("from phase6_", "import phase6_", "gui_modules", "tkinter", "fold_designer_bridge"):
        assert forbidden not in source
    assert "from .quantity_manufacturing_groups import (" in source
    assert "from .receiving_quantity_versions import QuantityModel" in source
    assert "from .manufacturing_value_thaw import thaw_manufacturing_value" in source


def test_gui_groups_via_public_engine_without_duplicate_rules():
    legacy = Path(compat.__file__).read_text(encoding="utf-8")
    gui = Path("gui_modules/project/export_actions.py").read_text(encoding="utf-8")
    assert "def quantity_manufacturing_groups(" not in legacy
    assert "def quantity_nfb_checked_manufacturing_groups(" not in legacy
    assert "manufacturing_api.quantity_manufacturing_groups(" in gui
    assert "manufacturing_api.quantity_nfb_checked_manufacturing_groups(" in gui
    assert "from phase6_quantity_manufacturing import resolve_quantity_manufacturing" in gui
