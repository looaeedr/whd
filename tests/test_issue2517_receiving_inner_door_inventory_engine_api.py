"""#2517 Receiving inner-door preview inventory uses one public Engine owner."""
from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError

import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_nfb_model_identity import display_model_ref
from gui_modules.application import receiving_inner_door_thumbnail as ui


def test_legacy_real_occurrences_and_exact_display_ref_parity():
    source = {"layers": 2, "models": [["A.dxf", "A.dxf", "B.dxf"], "C.dxf"]}
    rows = manufacturing_api.resolve_receiving_inner_door_preview_inventory(source)
    assert all(isinstance(row, manufacturing_api.ReceivingInnerDoorInventoryLayer) for row in rows)
    assert rows[0].model_refs == ("A.dxf", "A.dxf", "B.dxf")
    assert rows[0].display_counts == (("A", 2), ("B", 1))
    assert rows[1].model_refs == ("C.dxf",)
    assert rows[1].display_counts == (("C", 1),)
    assert ui.inner_door_preview_rows(source) == tuple(row.model_refs for row in rows)
    with pytest.raises(FrozenInstanceError):
        rows[0].model_refs = ()


def test_v5_brand_model_reference_keeps_true_physical_identity_and_no_dxf_assumption():
    a = "nfbv5:士林:NFB-100"
    b = "nfbv5:東元:NFB-100"
    data = {"layers": 2, "models": [[a, a, b], ["LEGACY.dxf"]]}
    actual = manufacturing_api.resolve_receiving_inner_door_preview_inventory(data)
    assert actual[0].model_refs == (a, a, b)
    assert actual[0].display_counts == (
        (display_model_ref(a), 2), (display_model_ref(b), 1),
    )
    # Brand/model identities remain separate despite identical visible names.
    assert len(actual[0].display_counts) == 2
    assert actual[1].display_counts == (("LEGACY", 1),)
    assert ui.inner_door_preview_rows(data)[0] == (a, a, b)


def test_empty_inactive_slot_keeps_legacy_single_layer_preview_contract():
    assert manufacturing_api.resolve_receiving_inner_door_preview_inventory(None) == ()
    assert ui.inner_door_preview_rows({"layers": 1, "models": ["", ""]}) == ((),)
    rows = manufacturing_api.resolve_receiving_inner_door_preview_inventory({
        "layers": 1, "models": [["A.dxf"], ["not-selected"]],
    })
    assert len(rows) == 1 and rows[0].display_counts == (("A", 1),)


@pytest.mark.parametrize("source", [
    {"layers": 3, "models": ["A.dxf", ""]},
    {"layers": 1, "models": ["A.dxf"]},
    {"layers": 2, "models": [["invalid.txt"], ""]},
    {"layers": 2, "models": [["nfbv5:壞廠牌:型號"], ""]},
])
def test_invalid_inventory_fails_closed_without_fabricating_display(source):
    with pytest.raises(ValueError):
        manufacturing_api.resolve_receiving_inner_door_preview_inventory(source)


def test_canvas_v5_renders_verified_counts_not_fabricated_hole_positions():
    class Canvas:
        def __init__(self):
            self.texts = []
        def delete(self, *_):
            self.texts.clear()
        def winfo_width(self):
            return 256
        def winfo_height(self):
            return 158
        def cget(self, key):
            assert key in {"width", "height"}
            return "256" if key == "width" else "158"
        def create_rectangle(self, *_args, **_kwargs):
            return None
        def create_text(self, *_args, **kwargs):
            self.texts.append(kwargs["text"])

    canvas = Canvas()
    raw = "nfbv5:士林:NFB-100"
    data = {"layers": 2, "models": [[raw, raw], "A.dxf"]}
    result = ui.paint_inner_door_thumbnail(canvas, data)
    assert result == ((raw, raw), ("A.dxf",))
    assert "第 1 層  ·  2 顆" in canvas.texts
    assert "NFB-100×2" in canvas.texts
    assert "配置示意，非實際開孔位置" in canvas.texts
    assert not any(".dxf" in label.lower() for label in canvas.texts)
    assert canvas._receiving_inner_preview_rows == result


def test_gui_has_no_private_engine_import_or_model_identity_policy():
    source = inspect.getsource(ui)
    assert "manufacturing_api.resolve_receiving_inner_door_preview_inventory(" in source
    assert "receiving_shared_settings" not in source
    assert "receiving_switch_model_catalog" not in source
    assert "display_model(" not in source
    assert "Counter(" not in source
