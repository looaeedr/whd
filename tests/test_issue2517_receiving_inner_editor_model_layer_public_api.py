# -*- coding: utf-8 -*-
"""#2517: Receiving NFB model occurrences and brand choices are public Engine inputs."""
from inspect import getsource

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.receiving_shared_settings import (
    switch_filenames_in_layer as original_unpack,
    pack_switch_layer as original_pack,
)
from ae_engine.receiving_nfb_model_identity import numeric_model_ref
from gui_modules.application import fold_designer_composition_receiving as gui


LEGACY = "400_140X257_107.dxf"


def test_public_facades_are_same_canonical_layer_model_source_functions():
    assert api.receiving_nfb_switch_filenames_in_layer is original_unpack
    assert ae_engine.receiving_nfb_switch_filenames_in_layer is original_unpack
    assert api.pack_receiving_nfb_switch_layer is original_pack
    assert ae_engine.pack_receiving_nfb_switch_layer is original_pack
    assert "receiving_nfb_switch_filenames_in_layer" in ae_engine.__all__
    assert "pack_receiving_nfb_switch_layer" in ae_engine.__all__


def test_legacy_and_native_nfb_model_slots_preserve_duplicate_physical_occurrences():
    model = numeric_model_ref("士林", "2P400")
    for original, expected in (
        ("", ()),
        (LEGACY, (LEGACY,)),
        (model, (model,)),
        ([model, model], (model, model)),
        ([LEGACY, model, model], (LEGACY, model, model)),
    ):
        unpacked = api.receiving_nfb_switch_filenames_in_layer(original)
        assert unpacked == expected
        assert api.pack_receiving_nfb_switch_layer(unpacked) == original
        assert original_unpack(original) == unpacked
        assert original_pack(unpacked) == original


def test_invalid_slot_type_and_source_item_rejected_by_original_engine_owner():
    for invalid in (None, 17, {"models": []}):
        with pytest.raises((TypeError, ValueError)):
            api.receiving_nfb_switch_filenames_in_layer(invalid)
    for invalid in (None, 17):
        with pytest.raises((TypeError, ValueError)):
            api.pack_receiving_nfb_switch_layer(invalid)


def test_fold_designer_uses_public_source_apis_and_original_brand_choices():
    source = getsource(gui)
    assert "from ae_engine.receiving_shared_settings import switch_filenames_in_layer" not in source
    assert "from ae_engine.receiving_shared_settings import pack_switch_layer" not in source
    assert "from ae_engine.receiving_switch_layout import RECEIVING_SWITCH_BRANDS" not in source
    assert source.count("manufacturing_api.receiving_nfb_switch_filenames_in_layer(") >= 3
    assert source.count("manufacturing_api.pack_receiving_nfb_switch_layer(") >= 4
    assert "manufacturing_api.receiving_operator_switch_brand_choices()" in source
    brand_choices = api.receiving_operator_switch_brand_choices()
    assert isinstance(brand_choices, tuple)
    assert "士林" in brand_choices
    assert "東元" in brand_choices


def test_legacy_quantity_editor_height_fallback_is_engine_owned_and_detached():
    from ae_engine.receiving_shared_settings import SETTING_DEFAULTS

    first = api.receiving_inner_door_legacy_layer_height_defaults()
    expected = SETTING_DEFAULTS["inner_door_layer_heights_mm"]
    assert first == expected
    assert first is not expected
    first[0] = -10
    assert api.receiving_inner_door_legacy_layer_height_defaults() == expected
    assert ae_engine.receiving_inner_door_legacy_layer_height_defaults() == expected
    assert "receiving_inner_door_legacy_layer_height_defaults" in ae_engine.__all__
    source = getsource(gui)
    assert "SETTING_DEFAULTS" not in source
    assert source.count("manufacturing_api.receiving_inner_door_legacy_layer_height_defaults()") == 2
