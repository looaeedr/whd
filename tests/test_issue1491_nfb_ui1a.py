# -*- coding: utf-8 -*-
"""#1491: physical NFB layer/slot draft, 3-tier brand inheritance, nominal X/Y."""
from copy import deepcopy

import pytest

from ae_engine.receiving_nfb_ui1a import (
    INHERIT, OVERRIDE, NEEDS_RESELECTION, PREVIEW_ONLY,
    new_nfb_ui1a_draft, reconcile_set_brand, set_nfb_draft_layer_count,
    set_nfb_layer_brand, set_nfb_slot_brand, add_nfb_draft_slot,
    select_nfb_slot_model, remove_nfb_draft_slot, effective_nfb_slot_brand,
    nfb_ui1a_preview,
)


def _draft():
    return new_nfb_ui1a_draft(set_brand="士林", layer_count=1,
                            model_layers=(["400_140X257_107.dxf"]*2,""))


def test_single_set_brand_owner_and_explicit_same_value_overrides():
    source=_draft()
    same_layer=set_nfb_layer_brand(source,0,mode=OVERRIDE,value="士林")
    same_unit=set_nfb_slot_brand(same_layer,0,0,mode=OVERRIDE,value="士林")
    assert same_layer["layers"][0]["brand"]=={"mode":OVERRIDE,"value":"士林"}
    assert same_unit["layers"][0]["slots"][0]["brand"]=={"mode":OVERRIDE,"value":"士林"}
    assert source["layers"][0]["brand"]=={"mode":INHERIT,"value":None}
    updated=reconcile_set_brand(same_unit,"東元")
    assert updated["set_brand"]=="東元"
    assert effective_nfb_slot_brand(updated,0,0)=="士林"  # explicit override
    assert effective_nfb_slot_brand(updated,0,1)=="士林"  # layer override
    inherit=set_nfb_layer_brand(updated,0,mode=INHERIT)
    assert effective_nfb_slot_brand(inherit,0,0)=="士林"
    assert effective_nfb_slot_brand(inherit,0,1)=="東元"
    reset=set_nfb_slot_brand(inherit,0,0,mode=INHERIT)
    assert effective_nfb_slot_brand(reset,0,0)=="東元"


def test_brand_change_does_not_silently_swap_csv_filename_even_if_other_brand_same_name():
    old=_draft()
    updated=reconcile_set_brand(old,"東元")
    selected=nfb_ui1a_preview(updated,bay_width_mm=800,upper_cell_height_mm=1100,
        catalog={"東元":("400_140X257_107.dxf",)})
    assert all(x["status"]==NEEDS_RESELECTION for x in selected["layers"][0]["slots"])
    assert all(x["filename"]=="400_140X257_107.dxf"
               for x in selected["layers"][0]["slots"])
    assert all(x["absolute_x_mm"] is None for x in selected["layers"][0]["slots"])
    updated=select_nfb_slot_model(
        updated,0,0,"400_140X257_107.dxf",
        catalog={"東元":("400_140X257_107.dxf",)})
    rows=nfb_ui1a_preview(updated,bay_width_mm=800,upper_cell_height_mm=1100)["layers"][0]["slots"]
    assert [x["status"] for x in rows]==["MODEL_SELECTED",NEEDS_RESELECTION]
    assert old["set_brand"]=="士林"


@pytest.mark.parametrize("width,quantity,pitch", [
    (600,2,(180.0,)), (750,2,(310.0,)), (800,2,(360.0,)),
    (800,3,(180.0,180.0)),
])
def test_nominal_pitch_exact_but_never_absolute_x(width,quantity,pitch):
    draft=new_nfb_ui1a_draft(set_brand="士林")
    for i in range(quantity):
        draft=add_nfb_draft_slot(draft,0,filename="400_140X257_107.dxf")
    r=nfb_ui1a_preview(draft,bay_width_mm=width,upper_cell_height_mm=1100)
    assert r["layers"][0]["adjacent_x_mm"]==pitch
    assert r["layers"][0]["nominal_y_from_top_mm"]==550.0
    assert all(p["absolute_x_mm"] is None for p in r["layers"])
    assert not r["can_manufacture"] and not r["has_absolute_x"]
    assert r["status"]==PREVIEW_ONLY


def test_empty_slot_keeps_physical_order_and_requires_no_fake_hole():
    source=_draft()
    with_empty=add_nfb_draft_slot(source,0)
    r=nfb_ui1a_preview(with_empty,bay_width_mm=800,upper_cell_height_mm=1100)
    assert len(r["layers"][0]["slots"])==3
    assert r["layers"][0]["slots"][2]["status"]=="EMPTY"
    assert r["layers"][0]["adjacent_x_mm"]==(180.0,180.0)
    assert source["layers"][0]["slots"][-1]["filename"]=="400_140X257_107.dxf"
    restored=remove_nfb_draft_slot(with_empty,0,2)
    assert restored==source
    with pytest.raises(IndexError):
        remove_nfb_draft_slot(source,0,8)


def test_two_layers_y_290_790_only_for_actual_1100_basis():
    d=new_nfb_ui1a_draft(set_brand="士林",layer_count=2)
    d=add_nfb_draft_slot(d,0,filename="400_140X257_107.dxf")
    d=add_nfb_draft_slot(d,1,filename="400_140X257_107.dxf")
    result=nfb_ui1a_preview(d,bay_width_mm=800,upper_cell_height_mm=1100)
    assert tuple(x["nominal_y_from_top_mm"] for x in result["layers"])==(290.0,790.0)
    unknown=nfb_ui1a_preview(d,bay_width_mm=800,upper_cell_height_mm=900)
    assert not unknown["is_1100_y_known"]
    assert all(x["nominal_y_from_top_mm"] is None for x in unknown["layers"])
    assert nfb_ui1a_preview(d,bay_width_mm=825,upper_cell_height_mm=1100)["layers"][0]["adjacent_x_mm"] is None
    assert d["status"]==PREVIEW_ONLY


def test_slots_do_not_erase_second_layer_and_no_stale_model_is_saved():
    d=new_nfb_ui1a_draft(set_brand="士林",layer_count=2,
                         model_layers=(["400_140X257_107.dxf"],["400_140X257_107.dxf"]))
    before=deepcopy(d)
    with pytest.raises(ValueError,match="remove"):
        set_nfb_draft_layer_count(d,1)
    assert d==before
    assert set_nfb_draft_layer_count(d,2)==d
    with pytest.raises(ValueError,match="physical layer must be visible and valid"):
        add_nfb_draft_slot(new_nfb_ui1a_draft(set_brand="士林"),1)
    with pytest.raises(ValueError,match="cannot hide"):
        new_nfb_ui1a_draft(set_brand="士林",layer_count=1,
                           model_layers=("", "400_140X257_107.dxf"))
    with pytest.raises(ValueError,match="registered"):
        reconcile_set_brand(d,"虛構廠牌")


def test_slot_reselection_requires_real_csv_entry_for_effective_brand():
    d=_draft()
    d=set_nfb_slot_brand(d,0,0,mode=OVERRIDE,value="東元")
    with pytest.raises(ValueError,match="current brand CSV"):
        select_nfb_slot_model(d,0,0,"400_140X257_107.dxf",catalog={"東元":()})
    d=select_nfb_slot_model(d,0,0,"400_140X257_107.dxf",
        catalog={"東元":("400_140X257_107.dxf",)})
    r=nfb_ui1a_preview(d,bay_width_mm=800,upper_cell_height_mm=1100,
        catalog={"東元":("400_140X257_107.dxf",),"士林":("400_140X257_107.dxf",)})
    assert r["layers"][0]["slots"][0]["effective_brand"]=="東元"
    assert r["layers"][0]["slots"][0]["brand_mode"]==OVERRIDE
    assert r["layers"][0]["slots"][0]["status"]=="MODEL_SELECTED"
    assert r["layers"][0]["slots"][1]["status"]=="MODEL_SELECTED"


def test_no_unapproved_geometry_or_persistence_fields():
    d=_draft()
    for name in ("readiness","manufacturing_ready","approved","nfb_config_submitted",
                 "hole_center_x_mm","cutting"):
        assert name not in d
    result=nfb_ui1a_preview(d,bay_width_mm=600,upper_cell_height_mm=1100)
    assert not result["can_manufacture"]
    assert all(x["absolute_x_mm"] is None for x in result["layers"])


def test_ac23_brand_reselection_revokes_only_changed_effective_x_datum():
    from copy import deepcopy
    from ae_engine.receiving_nfb_ui1a_edits import (
        NfbUi1aEditSession, editable_nfb_draft, set_nfb_manual_x,
    )

    initial = editable_nfb_draft(_draft())
    for index, offset in ((0, 0), (1, 14.5)):
        initial = set_nfb_manual_x(
            initial, 0, index, offset, datum={"width": 800, "brand": "士林"},
        )
        part = initial["layers"][0]["slots"][index]
        part["manual_x_state"] = "CONFIRMED"
        part["datum_revision"] = "old-brand-source"
    initial = set_nfb_slot_brand(initial, 0, 0, mode=OVERRIDE, value="士林")
    frozen = deepcopy(initial)
    session = NfbUi1aEditSession(initial)

    # Set brand changes but explicitly same-brand unit keeps source authority.
    assert session.apply("SET_BRAND", reconcile_set_brand, "東元")
    first, second = session.current["layers"][0]["slots"]
    assert first == frozen["layers"][0]["slots"][0]
    assert second["manual_x_mm"] == 14.5
    assert second["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert second["datum_snapshot"] is None
    assert "datum_revision" not in second
    assert session.undo().action == "SET_BRAND"
    assert session.current == frozen and initial == frozen

    # Same effective brand does not gratuitously invalidate prior X proof.
    no_op = set_nfb_layer_brand(initial, 0, mode=OVERRIDE, value="士林")
    assert no_op["layers"][0]["slots"][0]["datum_revision"] == "old-brand-source"
    assert no_op["layers"][0]["slots"][1]["datum_revision"] == "old-brand-source"
    overridden = set_nfb_slot_brand(initial, 0, 0, mode=OVERRIDE, value="東元")
    changed = overridden["layers"][0]["slots"][0]
    assert changed["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert changed["manual_x_mm"] == 0
    assert changed["datum_snapshot"] is None
    assert "datum_revision" not in changed
    assert overridden["layers"][0]["slots"][1] == initial["layers"][0]["slots"][1]


def test_ac23_repeated_effective_brand_changes_preserve_reconfirm_required():
    from ae_engine.receiving_nfb_ui1a_edits import (
        editable_nfb_draft, set_nfb_manual_x,
    )

    original = editable_nfb_draft(_draft())
    original = set_nfb_manual_x(original, 0, 0, 0)
    original["layers"][0]["slots"][0]["manual_x_state"] = "RECONFIRM_REQUIRED"
    original["layers"][0]["slots"][0]["datum_revision"] = "old-world-x"
    first = reconcile_set_brand(original, "東元")
    assert first["layers"][0]["slots"][0]["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert "datum_revision" not in first["layers"][0]["slots"][0]
    second = reconcile_set_brand(first, "士林")
    assert second["layers"][0]["slots"][0]["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert second["layers"][0]["slots"][0]["manual_x_mm"] == 0
    assert original["layers"][0]["slots"][0]["datum_revision"] == "old-world-x"


def test_ac23_direct_model_selection_cannot_reuse_approved_old_x_datum():
    """All editor model-selection callers share the same source invalidation."""
    from copy import deepcopy
    from ae_engine.receiving_nfb_model_identity import numeric_model_ref
    from ae_engine.receiving_nfb_ui1a_edits import (
        editable_nfb_draft, replace_nfb_slot_model, set_nfb_manual_x,
    )

    first = numeric_model_ref("士林", "2P400")
    second = numeric_model_ref("士林", "3P125SN")
    options = {"士林": (first, second)}
    original = editable_nfb_draft(new_nfb_ui1a_draft(
        set_brand="士林", layer_count=1, model_layers=([first], ""),
    ))
    original = set_nfb_manual_x(original, 0, 0, 0, datum={"width": 800})
    source = original["layers"][0]["slots"][0]
    source["manual_x_state"] = "CONFIRMED"
    source["datum_revision"] = "old-model-datum"
    frozen = deepcopy(original)

    direct = select_nfb_slot_model(original, 0, 0, second, catalog=options)
    row = direct["layers"][0]["slots"][0]
    assert row["manual_x_mm"] == 0
    assert row["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert row["datum_snapshot"] is None
    assert "datum_revision" not in row
    assert direct["layers"][0]["slots"][0]["filename"] == second

    wrapped = replace_nfb_slot_model(original, 0, 0, second, catalog=options)
    assert wrapped["layers"][0]["slots"][0]["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert select_nfb_slot_model(
        original, 0, 0, first, catalog=options,
    )["layers"][0]["slots"][0] == source
    assert original == frozen


@pytest.mark.parametrize("dimension,bad", (
    ("bay_width_mm", 0), ("bay_width_mm", -800),
    ("bay_width_mm", 10 ** 400), ("bay_width_mm", -(10 ** 400)),
    ("bay_width_mm", float("nan")), ("bay_width_mm", float("inf")),
    ("bay_width_mm", True), ("bay_width_mm", "800"),
    ("upper_cell_height_mm", 0), ("upper_cell_height_mm", -1100),
    ("upper_cell_height_mm", 10 ** 400),
    ("upper_cell_height_mm", -(10 ** 400)),
    ("upper_cell_height_mm", float("nan")),
    ("upper_cell_height_mm", float("-inf")),
    ("upper_cell_height_mm", False), ("upper_cell_height_mm", "1100"),
))
def test_ac23_nominal_nfb_preview_rejects_bad_physical_box_dimensions(dimension, bad):
    """Invalid W/H cannot crash a preview or project an apparent NFB datum."""
    original = _draft()
    frozen = deepcopy(original)
    kwargs = {"bay_width_mm": 800, "upper_cell_height_mm": 1100}
    kwargs[dimension] = bad
    expected = "NFB Bay width is invalid" if dimension == "bay_width_mm" else "NFB upper cell height is invalid"
    with pytest.raises(ValueError, match=expected):
        nfb_ui1a_preview(original, **kwargs)
    assert original == frozen


def test_ac23_nominal_nfb_preview_preserves_approved_geometry_in_valid_scope():
    """Guard must preserve ordinary source-approved nominal pitch and Y preview."""
    original = _draft()
    result = nfb_ui1a_preview(original, bay_width_mm=800, upper_cell_height_mm=1100)
    assert result["status"] == PREVIEW_ONLY
    assert result["layers"][0]["adjacent_x_mm"] == (360.0,)
    assert result["layers"][0]["nominal_y_from_top_mm"] == 550.0
    assert result["has_absolute_x"] is False
    assert original == _draft()


def test_ac51_model_catalog_identity_alone_can_only_display_preview():
    """CSV/DXF model existence is not a physical manufacturing certificate."""
    import pytest
    from ae_engine.receiving_nfb_model_identity import (
        display_model_ref, display_unverified_model_choice,
    )

    for ref in ("nfbv5:士林:2P400", "nfbv5:東元:TEST", "400_140X257_107.dxf"):
        label = display_unverified_model_choice(ref)
        assert label == display_model_ref(ref) + "｜僅預覽"
        assert "可製造（內門）" not in label
        assert "nfbv5:" not in label
        # Rendering must never overwrite the saved brand/model owner.
        assert ref != label
    for invalid in ("nfbv5:士林:", "nfbv5:跨品牌:TEST"):
        with pytest.raises(ValueError):
            display_unverified_model_choice(invalid)
