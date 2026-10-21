# -*- coding: utf-8 -*-
"""#1504 direct source assertions for NFB-AC-17 and SWT-AC-04.

Selected V5 model identities always belong to the current brand CSV.
Draft/UI previews never manufacture a world-X or mutate the parent Set.
"""
from copy import deepcopy
import json

import pytest

from ae_engine.receiving_nfb_model_identity import numeric_model_refs
from ae_engine.receiving_nfb_ui1a import (
    INHERIT, OVERRIDE, NEEDS_RESELECTION, PREVIEW_ONLY,
    new_nfb_ui1a_draft, reconcile_set_brand, set_nfb_layer_brand,
    set_nfb_slot_brand, select_nfb_slot_model, nfb_ui1a_preview,
    effective_nfb_slot_brand,
)
from ae_engine.receiving_nfb_persistence import (
    normalize_nfb_config, normalize_nfb_saved_fields,
)


def _models():
    shihlin = numeric_model_refs("士林")
    teco = numeric_model_refs("東元")
    assert shihlin and teco
    return shihlin[0], teco[0]


def _preview(draft, catalog=None):
    return nfb_ui1a_preview(
        draft, bay_width_mm=800, upper_cell_height_mm=1100, catalog=catalog,
    )


def test_nfb_ac17_three_tier_followers_overrides_provenance_and_preview():
    """Follow only inheritors; same-value explicit overrides remain overrides."""
    original_model, east_model = _models()
    original = new_nfb_ui1a_draft(
        set_brand="士林", layer_count=2,
        model_layers=([original_model, original_model],
                      [original_model, original_model]),
    )
    source = deepcopy(original)
    source = set_nfb_slot_brand(source, 0, 0, mode=OVERRIDE, value="東元")
    source = select_nfb_slot_model(
        source, 0, 0, east_model, catalog={"東元": (east_model,)},
    )
    source = set_nfb_layer_brand(source, 1, mode=OVERRIDE, value="士林")
    source = set_nfb_slot_brand(source, 1, 1, mode=OVERRIDE, value="東元")
    source = select_nfb_slot_model(
        source, 1, 1, east_model, catalog={"東元": (east_model,)},
    )
    before_change = deepcopy(source)
    changed = reconcile_set_brand(source, "東元")
    assert source == before_change and original["set_brand"] == "士林"
    assert changed["set_brand"] == "東元"
    assert [effective_nfb_slot_brand(changed, i, j)
            for i in range(2) for j in range(2)] == [
                "東元", "東元", "士林", "東元",
            ]
    preview = _preview(changed)
    assert [u["status"] for row in preview["layers"]
            for u in row["slots"]] == [
                "MODEL_SELECTED", NEEDS_RESELECTION,
                "MODEL_SELECTED", "MODEL_SELECTED",
            ]
    assert changed["layers"][0]["slots"][1]["filename"] == original_model
    assert changed["layers"][0]["slots"][1]["source_brand"] == "士林"
    assert changed["layers"][1]["brand"] == {"mode": OVERRIDE, "value": "士林"}
    assert changed["layers"][1]["slots"][1]["brand"] == {
        "mode": OVERRIDE, "value": "東元",
    }
    assert not preview["can_manufacture"] and not preview["has_absolute_x"]
    assert preview["status"] == PREVIEW_ONLY
    assert all(u["absolute_x_mm"] is None for row in preview["layers"]
               for u in row["slots"])

    # Explicitly writing the same inherited value must keep override
    # identity; only an explicit INHERIT returns to following the parent.
    same = set_nfb_slot_brand(changed, 0, 1, mode=OVERRIDE, value="東元")
    assert same["layers"][0]["slots"][1]["brand"]["mode"] == OVERRIDE
    assert _preview(same)["layers"][0]["slots"][1]["status"] == NEEDS_RESELECTION
    switched_back = reconcile_set_brand(same, "士林")
    assert effective_nfb_slot_brand(switched_back, 0, 1) == "東元"
    inherited = set_nfb_slot_brand(switched_back, 0, 1, mode=INHERIT)
    assert effective_nfb_slot_brand(inherited, 0, 1) == "士林"


def test_swt_ac04_spoofed_catalog_and_stale_csv_never_relabel_v5_source(monkeypatch):
    """Typed IDs cannot inherit a different brand just because lists lie."""
    shihlin, teco = _models()
    draft = new_nfb_ui1a_draft(
        set_brand="東元", model_layers=([shihlin], ""),
    )
    snapshot = deepcopy(draft)
    spoofed_catalog = {"東元": (shihlin, teco, "nfbv5:東元:REMOVED")}
    with pytest.raises(ValueError, match="identity/source"):
        select_nfb_slot_model(
            draft, 0, 0, shihlin, catalog=spoofed_catalog,
        )
    with pytest.raises(ValueError, match="identity/source"):
        select_nfb_slot_model(
            draft, 0, 0, "nfbv5:東元:REMOVED",
            catalog=spoofed_catalog,
        )
    assert draft == snapshot

    # Legacy data can contain a syntactically valid, wrong-brand identity
    # with a misleading source_brand field. The UI must still show reselection.
    stored = deepcopy(draft)
    stored["layers"][0]["slots"][0]["source_brand"] = "東元"
    stale = _preview(stored, catalog=spoofed_catalog)
    assert stale["layers"][0]["slots"][0]["status"] == NEEDS_RESELECTION
    assert stale["layers"][0]["slots"][0]["filename"] == shihlin
    assert stale["layers"][0]["slots"][0]["absolute_x_mm"] is None

    removed = new_nfb_ui1a_draft(
        set_brand="東元", model_layers=(["nfbv5:東元:REMOVED"], ""),
    )
    absent = _preview(removed, catalog=spoofed_catalog)
    assert absent["layers"][0]["slots"][0]["status"] == NEEDS_RESELECTION

    # Fresh CSV loss after a valid selection must not keep MODEL_SELECTED.
    valid = select_nfb_slot_model(
        draft, 0, 0, teco, catalog={"東元": (teco,)},
    )
    assert _preview(valid)["layers"][0]["slots"][0]["status"] == "MODEL_SELECTED"
    monkeypatch.setattr(
        "ae_engine.receiving_nfb_model_identity.numeric_model_refs",
        lambda brand: () if brand == "東元" else numeric_model_refs(brand),
    )
    vanished = _preview(valid)
    assert vanished["layers"][0]["slots"][0]["status"] == NEEDS_RESELECTION
    assert vanished["can_manufacture"] is False
    assert valid["layers"][0]["slots"][0]["source_brand"] == "東元"


def test_swt_ac04_selected_brand_and_override_are_persisted_without_second_set_owner():
    """A saved per-hole value must preserve the chosen typed model and mode."""
    shihlin, teco = _models()
    config = {"layer_count": 1, "holes": [
        {
            "physical_hole_id": "nfb:bay:one",
            "model_filename": shihlin,
            "source_brand": "士林",
            "brand_mode": INHERIT,
            "manual_x_state": "NONE",
            "manual_x_mm": None,
        }, {
            "physical_hole_id": "nfb:bay:two",
            "model_filename": teco,
            "source_brand": "東元",
            "brand_mode": OVERRIDE,
            "manual_x_state": "NONE",
            "manual_x_mm": None,
        },
    ]}
    source = deepcopy(config)
    saved = normalize_nfb_saved_fields({
        "nfb_config_submitted": True, "nfb_config": config,
    })
    loaded = json.loads(json.dumps(saved, ensure_ascii=False))
    assert loaded["nfb_config_submitted"] is True
    assert [(u["model_filename"], u["source_brand"], u["brand_mode"])
            for u in loaded["nfb_config"]["holes"]] == [
                (shihlin, "士林", INHERIT), (teco, "東元", OVERRIDE),
            ]
    assert config == source
    assert "brand" not in loaded["nfb_config"]
    assert "switch_brand" not in loaded["nfb_config"]

    bad = deepcopy(config)
    bad["holes"][1]["source_brand"] = "士林"
    with pytest.raises(ValueError, match="mismatch"):
        normalize_nfb_config(bad)
    assert bad["holes"][1]["model_filename"] == teco
