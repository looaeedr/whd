# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import importlib.util
import inspect
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest


MODULE = "phase6_assembly_presentation"


def _module():
    spec = importlib.util.find_spec(MODULE)
    assert spec is not None, (
        "T1 requirement RED: phase6_assembly_presentation.py does not exist yet"
    )
    return importlib.import_module(MODULE)


def _entry_signature(model):
    rows = []
    for entry in model.entries:
        if hasattr(entry, "children"):
            rows.append(
                (
                    "group",
                    entry.presentation_key,
                    tuple(child.part_key for child in entry.children),
                )
            )
        else:
            rows.append(("row", entry.part_key))
    return tuple(rows)


def test_t1_contract_types_are_frozen_and_group_has_no_live_authority():
    m = _module()
    row = m.AssemblyPresentationRow(
        part_key="box_body",
        label="箱身",
        visible_seed=True,
        has_piece_host=True,
    )
    group = m.AssemblySyntheticGroup(
        presentation_key="door",
        label="門",
        children=(
            m.AssemblyPresentationRow(
                part_key="door_c1_r1",
                label="上門",
                visible_seed=False,
            ),
        ),
    )
    model = m.AssemblyPresentationModel(entries=(row, group))
    piece = m.AssemblyBoxBodyPieceRow(
        part_key="box_body:left_side",
        label="左側板",
        formed_width=100.0,
        formed_height=200.0,
        blank_width=110.0,
        blank_height=210.0,
    )

    assert model.entries == (row, group)
    assert piece.part_key == "box_body:left_side"
    assert row.formed_text_seed is None
    assert row.blank_text_seed is None
    assert row.corner_text_seed is None

    for forbidden in (
        "visible_seed",
        "formed_text_seed",
        "blank_text_seed",
        "corner_text_seed",
        "has_piece_host",
    ):
        assert not hasattr(group, forbidden)

    with pytest.raises(FrozenInstanceError):
        row.label = "changed"
    with pytest.raises(FrozenInstanceError):
        group.label = "changed"
    with pytest.raises(FrozenInstanceError):
        piece.blank_width = 999.0


def test_t1_model_consumes_dm7_top_level_projection_and_preserves_order(monkeypatch):
    m = _module()
    seen = {}

    def fake_selector(values):
        seen["values"] = tuple(values)
        return (
            "box_body",
            "door_c1_r1",
            "door_c1_r2",
            "head",
            "base_plate_c1_r1",
            "base_plate_c1_r2",
            "tail",
        )

    monkeypatch.setattr(m, "operator_part_selector_keys", fake_selector)
    available = (
        "box_body",
        "box_body:left_side",
        "box_body:back",
        "door_c1_r1",
        "door_c1_r2",
        "head",
        "base_plate_c1_r1",
        "base_plate_c1_r2",
        "tail",
    )
    model = m.build_assembly_presentation_model(
        available,
        label_for=lambda key: f"L:{key}",
        visible_seed_by_key={"door_c1_r2": False, "tail": False},
    )

    assert seen["values"] == available
    assert _entry_signature(model) == (
        ("row", "box_body"),
        ("group", "door", ("door_c1_r1", "door_c1_r2")),
        ("row", "head"),
        ("group", "base_plate", ("base_plate_c1_r1", "base_plate_c1_r2")),
        ("row", "tail"),
    )
    box_row = model.entries[0]
    door_group = model.entries[1]
    tail_row = model.entries[-1]
    assert box_row.has_piece_host is True
    assert door_group.label == "L:door"
    assert tuple(child.visible_seed for child in door_group.children) == (True, False)
    assert tail_row.visible_seed is False


def test_t1_real_dm7_parent_projection_does_not_invent_or_duplicate_box_children():
    m = _module()
    model = m.build_assembly_presentation_model(
        (
            "box_body",
            "box_body:left_side",
            "box_body:back",
            "box_body:right_side",
            "head",
            "tail",
        ),
        label_for=str,
    )
    assert _entry_signature(model) == (
        ("row", "box_body"),
        ("row", "head"),
        ("row", "tail"),
    )

    parent_absent = m.build_assembly_presentation_model(
        ("box_body:left_side", "box_body:back", "head"),
        label_for=str,
    )
    assert _entry_signature(parent_absent) == (
        ("row", "box_body:left_side"),
        ("row", "box_body:back"),
        ("row", "head"),
    )


def test_t1_synthetic_groups_are_presentation_only_and_keep_child_identity():
    m = _module()
    model = m.build_assembly_presentation_model(
        (
            "door_c2_r1",
            "door_c1_r2",
            "head",
            "base_plate_c2_r1",
            "base_plate_c1_r2",
        ),
        label_for=lambda key: key,
    )
    assert _entry_signature(model) == (
        ("group", "door", ("door_c2_r1", "door_c1_r2")),
        ("row", "head"),
        ("group", "base_plate", ("base_plate_c2_r1", "base_plate_c1_r2")),
    )


def test_t1_box_body_piece_projection_uses_render_time_piece_order_and_dimensions_only():
    m = _module()
    pieces = (
        SimpleNamespace(
            role="left_side",
            key="ignored-left-key",
            formed_outer_dimensions=(101, 201),
            material_dimensions=(111, 211),
        ),
        SimpleNamespace(
            role="back",
            key="ignored-back-key",
            formed_outer_dimensions=(301.5, 401.25),
            material_dimensions=(311.5, 411.25),
        ),
        SimpleNamespace(
            role="right_side",
            key="ignored-right-key",
            formed_outer_dimensions=(501, 601),
            material_dimensions=(511, 611),
        ),
    )
    rows = m.project_box_body_piece_rows(
        SimpleNamespace(pieces=pieces),
        label_for=lambda key: f"label:{key}",
    )

    assert tuple(row.part_key for row in rows) == (
        "box_body:left_side",
        "box_body:back",
        "box_body:right_side",
    )
    assert (
        rows[0].formed_width,
        rows[0].formed_height,
        rows[0].blank_width,
        rows[0].blank_height,
    ) == (101.0, 201.0, 111.0, 211.0)
    assert (
        rows[1].formed_width,
        rows[1].formed_height,
        rows[1].blank_width,
        rows[1].blank_height,
    ) == (301.5, 401.25, 311.5, 411.25)


def test_t1_box_body_piece_projection_preserves_current_key_fallback():
    m = _module()
    rows = m.project_box_body_piece_rows(
        SimpleNamespace(
            pieces=(
                SimpleNamespace(
                    role="",
                    key="box_body:legacy_piece",
                    formed_outer_dimensions=(10, 20),
                    material_dimensions=(30, 40),
                ),
            )
        ),
        label_for=str,
    )
    assert len(rows) == 1
    assert rows[0].part_key == "box_body:legacy_piece"


def test_t1_module_purity_and_authority_source_scan():
    m = _module()
    source = inspect.getsource(m)
    lowered = source.lower()

    assert "tkinter" not in lowered
    assert "fold_designer_bridge" not in source
    assert "phase6_settings_panel" not in source
    assert "manufacturing_api" not in source
    assert "resolve_geometry(" not in source
    assert "designer_workspace" not in source
    assert "project_controller" not in source
    assert "workspace." not in source

    assert "operator_part_selector_keys" in source
    assert "pieces" in source
