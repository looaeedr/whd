"""#2517 Receiving GUI Set/Bay mutations require the public Engine seam."""
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import new_receiving_layout
from gui_modules.application.receiving_set_bay_adapter import (
    ReceivingSetBayAdapter, receiving_layout_stable_ids,
)


def test_engine_owns_stable_id_sequence_and_set_append():
    raw = new_receiving_layout(width=800, height=1600, depth=350)
    assert api.receiving_layout_stable_ids(raw) == receiving_layout_stable_ids(raw)
    adapter = ReceivingSetBayAdapter(raw)
    assert adapter.select_set(2)
    assert adapter.layout == api.append_receiving_set(raw)
    assert len(api.receiving_layout_stable_ids(adapter.layout)) == 4


def test_shared_setting_adapter_matches_same_public_api_and_rejects_bad_brand():
    raw = new_receiving_layout(width=800, height=1600, depth=350)
    expected = api.edit_receiving_shared_setting(
        raw, set_index=0, bay_index=0, kind="inner_door_layers", value=2,
    )
    adapter = ReceivingSetBayAdapter(raw)
    adapter.update_setting("inner_door_layers", 2)
    assert adapter.layout == expected
    assert raw != expected
    with pytest.raises(ValueError, match="不支援的開關品牌"):
        api.require_receiving_operator_brand("unknown")


def test_gui_only_calls_public_api_and_nfb_transactions_remain_engine_owned():
    source = (
        Path(__file__).resolve().parents[1] /
        "gui_modules/application/receiving_set_bay_adapter.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "from ae_engine.receiving_layout import",
        "from ae_engine.receiving_shared_settings import",
        "from ae_engine.receiving_nfb_transactions import",
        "from ae_engine.receiving_switch_layout import",
        "from ae_engine.receiving_manufacturing_readiness import",
    ):
        assert forbidden not in source
    for name in (
        "submit_receiving_nfb_bays",
        "copy_receiving_submitted_nfb_bay",
        "restore_receiving_nfb_bays_unconfigured",
        "undo_receiving_nfb_transaction",
        "share_receiving_shared_setting",
        "unlink_receiving_shared_setting",
    ):
        assert "manufacturing_api." + name in source
        assert callable(getattr(api, name))
