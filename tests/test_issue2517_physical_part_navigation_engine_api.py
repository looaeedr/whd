# -*- coding: utf-8 -*-
"""#2517 physical part hierarchy derives only from Engine identity owners."""
from ae_engine import manufacturing_api as api
from phase6_part_navigation import NavigationRow, project_hierarchy


def test_vault_and_three_piece_box_body_preserve_original_real_order():
    keys = ("box_body", "box_body:left_side", "box_body:back",
            "box_body:right_side", "head", "tail")
    expected = (
        ("box_body", None, 0),
        ("box_body:left_side", "box_body", 1),
        ("box_body:back", "box_body", 1),
        ("box_body:right_side", "box_body", 1),
        ("head", None, 0),
        ("tail", None, 0),
    )
    assert api.project_physical_part_navigation_rows(keys) == expected
    assert project_hierarchy(keys) == tuple(NavigationRow(*row) for row in expected)


def test_missing_physical_parent_must_not_be_invented():
    keys = ("box_body:left_side", "head", "base_plate:fixing_plate:left")
    expected = tuple((key, None, 0) for key in keys)
    assert api.project_physical_part_navigation_rows(keys) == expected
    assert project_hierarchy(keys) == tuple(NavigationRow(*row) for row in expected)


def test_one_tier_ears_owned_by_true_base_and_no_pseudo_tier():
    keys = ("base_plate", "base_plate:fixing_plate:left",
            "base_plate:fixing_plate:right", "head")
    assert api.project_physical_part_navigation_rows(keys) == (
        ("base_plate", None, 0),
        ("base_plate:fixing_plate:left", "base_plate", 1),
        ("base_plate:fixing_plate:right", "base_plate", 1),
        ("head", None, 0),
    )


def test_real_two_tier_ear_parent_is_exact_matching_layer():
    keys = (
        "base_plate", "base_plate:nfb_layer:0", "base_plate:nfb_layer:1",
        "base_plate:fixing_plate:nfb_layer:0:left",
        "base_plate:fixing_plate:nfb_layer:0:right",
        "base_plate:fixing_plate:nfb_layer:1:left",
        "base_plate:fixing_plate:nfb_layer:1:right",
    )
    assert api.project_physical_part_navigation_rows(keys) == (
        ("base_plate", None, 0),
        ("base_plate:nfb_layer:0", None, 0),
        ("base_plate:fixing_plate:nfb_layer:0:left", "base_plate:nfb_layer:0", 1),
        ("base_plate:fixing_plate:nfb_layer:0:right", "base_plate:nfb_layer:0", 1),
        ("base_plate:nfb_layer:1", None, 0),
        ("base_plate:fixing_plate:nfb_layer:1:left", "base_plate:nfb_layer:1", 1),
        ("base_plate:fixing_plate:nfb_layer:1:right", "base_plate:nfb_layer:1", 1),
    )
    # If tier 1's true physical base is missing, its EARs cannot borrow tier 0.
    without_owner = tuple(k for k in keys if k != "base_plate:nfb_layer:1")
    rows = api.project_physical_part_navigation_rows(without_owner)
    assert ("base_plate:fixing_plate:nfb_layer:1:left", "base_plate", 1) in rows
    assert ("base_plate:fixing_plate:nfb_layer:1:right", "base_plate", 1) in rows


def test_gui_navigation_only_adapts_public_engine_rows(monkeypatch):
    keys = ("base_plate", "head")
    seen = []
    def engine(available):
        seen.append(available)
        return (("real-id", "real-parent", 1),)
    monkeypatch.setattr(api, "project_physical_part_navigation_rows", engine)
    assert project_hierarchy(keys) == (NavigationRow("real-id", "real-parent", 1),)
    assert seen == [keys]


def test_gui_has_no_physical_tier_regex_or_owner_selection():
    from pathlib import Path
    source = Path("phase6_part_navigation.py").read_text(encoding="utf-8")
    assert "tier_ear = re.compile" not in source
    assert "tier_owners =" not in source
    assert "ear_parent(key)" not in source
    assert "manufacturing_api.project_physical_part_navigation_rows(" in source
