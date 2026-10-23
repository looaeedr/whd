# -*- coding: utf-8 -*-
"""#1504 unified brand inheritance: active-mode source, one unchanged rule.

No new NFB brand rule, no second Set owner, no per-version hard-coded brand.
Only the existing UI's input owner changes when switching to quantity.
"""
from pathlib import Path

from ae_engine.receiving_nfb_model_identity import (
    numeric_model_refs, parse_numeric_model_ref,
)
from ae_engine.receiving_nfb_ui1a import (
    INHERIT, OVERRIDE, new_nfb_ui1a_draft, set_nfb_layer_brand,
    set_nfb_slot_brand, effective_nfb_layer_brand,
    effective_nfb_slot_brand, nfb_ui1a_preview,
)
from ae_engine.receiving_quantity_box import project_common_box
from ae_engine.receiving_layout import new_receiving_layout
from phase6_quantity_model import QuantityModel


def _brand_for_quantity(brand):
    q = QuantityModel()
    projected = project_common_box({
        "model": "受電箱",
        "active_mode": "quantity",
        "quantity": q.snapshot(),
        "receiving_quantity_box": {
            "w": 800, "h": 1600, "d": 350, "switch_brand": brand,
        },
    })
    row = projected["receiving_layout"]["sets"][0]
    assert row["switch_brand"] == brand
    assert projected["receiving_quantity_box"]["switch_brand"] == brand
    return row["switch_brand"]


def test_quantity_brand_projects_original_owner_to_same_nfb_layer_unit_rule():
    shihlin = numeric_model_refs("士林")[0]
    teco = numeric_model_refs("東元")[0]
    assert parse_numeric_model_ref(shihlin)[0] == "士林"
    assert parse_numeric_model_ref(teco)[0] == "東元"

    # Same NFB UI-1A inheritance engine in both modes; no mode-specific
    # brand inheritance function or new QuantityModel brand schema.
    for brand, expected_ref in (("士林", shihlin), ("東元", teco)):
        current = _brand_for_quantity(brand)
        draft = new_nfb_ui1a_draft(
            set_brand=current, layer_count=1, model_layers=([expected_ref], ""),
        )
        assert effective_nfb_layer_brand(draft, 0) == brand
        assert effective_nfb_slot_brand(draft, 0, 0) == brand
        preview = nfb_ui1a_preview(
            draft, bay_width_mm=800, upper_cell_height_mm=1100,
        )
        assert preview["layers"][0]["slots"][0]["status"] == "MODEL_SELECTED"
        assert preview["layers"][0]["slots"][0]["effective_brand"] == brand
        assert preview["has_absolute_x"] is False
        assert preview["can_manufacture"] is False


def test_quantity_brand_override_reuses_existing_three_tier_rule_exactly():
    teco = numeric_model_refs("東元")[0]
    shihlin = numeric_model_refs("士林")[0]
    selected_parent = _brand_for_quantity("東元")
    source = new_nfb_ui1a_draft(
        set_brand=selected_parent, layer_count=1,
        model_layers=([teco, shihlin], ""),
    )
    layer = set_nfb_layer_brand(source, 0, mode=OVERRIDE, value="士林")
    with_slot = set_nfb_slot_brand(layer, 0, 0, mode=OVERRIDE, value="東元")
    assert effective_nfb_slot_brand(with_slot, 0, 0) == "東元"
    assert effective_nfb_slot_brand(with_slot, 0, 1) == "士林"
    inherited = set_nfb_slot_brand(with_slot, 0, 0, mode=INHERIT)
    assert effective_nfb_slot_brand(inherited, 0, 0) == "士林"
    assert source["layers"][0]["brand"]["mode"] == INHERIT
    assert source["set_brand"] == selected_parent
    assert source["layers"][0]["slots"][0]["filename"] == teco


def test_set_bay_brand_owner_unchanged_by_quantity_entry_routing():
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    assert "switch_brand" not in layout["sets"][0]
    layout["sets"][0]["switch_brand"] = "士林"
    draft = new_nfb_ui1a_draft(
        set_brand=layout["sets"][0]["switch_brand"],
        model_layers=([numeric_model_refs("士林")[0]], ""),
    )
    assert effective_nfb_slot_brand(draft, 0, 0) == "士林"
    assert "brand" not in layout["sets"][0]
    assert "nfb_brand" not in layout["sets"][0]


def test_all_three_real_gui_nfb_source_call_sites_use_same_active_mode_owner():
    gui = (Path(__file__).resolve().parents[1] /
           "gui_modules/application/fold_designer_composition_receiving.py"
           ).read_text(encoding="utf-8")
    # Existing Single and Multi selectors keep their canonical write ports.
    assert 'candidate = update_common_box(source, {"switch_brand": value})' in gui
    assert 'adapter.set_global_brand(value)' in gui
    assert 'def current_nfb_parent_brand():' in gui
    assert 'if _current_mode_snapshot(self, namespace).get("active_mode") == "quantity":' in gui
    assert 'return single_brand()' in gui
    assert 'return self.receiving_switch_adapter(namespace).brand' in gui
    begin = gui.index("    def inner_edit(role, version_id, after_saved,")
    end = gui.index("    def current_inner_editor_config():", begin)
    inner = gui[begin:end]
    assert 'selected_brand=current_nfb_parent_brand(),' in inner
    assert 'set_brand=current_nfb_parent_brand(),' in inner
    assert 'current_owner = current_nfb_parent_brand()' in inner
    assert 'self.receiving_switch_adapter(namespace).brand' not in inner
    # A branch-specific brand inference would produce two inconsistent lists
    # or overwrite a selected model's own V5 source identity. There is one
    # engine: effective_nfb_slot_brand() for both contexts.
    assert "effective_nfb_slot_brand(" in inner
    assert "reconcile_set_brand(" in inner
