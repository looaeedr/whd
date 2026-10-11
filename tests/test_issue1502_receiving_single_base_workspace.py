# -*- coding: utf-8 -*-
"""#1502: Receiving keeps ONE original base, never derived lower-cell bases."""
from pathlib import Path

from phase6_derived_part_projection import (
    DerivedPartRequestAssemblyInput,
    build_derived_part_projection_request,
    build_derived_part_sync_plan,
)


def _input(*, receiving):
    profiles={
        "base_plate_c1_r1":{"X":[{"len":700}],"Y":[{"len":1060}]},
        "base_plate_c1_r2":{"X":[{"len":700}],"Y":[{"len":460}]},
    }
    return DerivedPartRequestAssemblyInput(
        door_part_keys=("door_c1_r1","door_c1_r2"),
        door_profiles={
            "door_c1_r1":{"X":[],"Y":[]},
            "door_c1_r2":{"X":[],"Y":[]},
        },
        base_plate_profiles=profiles,
        divider_profiles={},
        inner_profiles={},
        box_piece_profiles={},
        current_piece_keys=(),
        source_parts=("door","base_plate"),
        available_parts=(
            "door_c1_r1","door_c1_r2",
            "base_plate","base_plate_c1_r1","base_plate_c1_r2",
        ),
        source_part_features={},
        known_feature_keys=(),
        single_door_profiles=None,
        single_base_plate_profiles=None,
        active_part="base_plate_c1_r2",
        selected_part="base_plate_c1_r1",
        preserve_single_base_plate=receiving,
    )


def test_receiving_keeps_existing_base_not_top_or_lower_door_clones():
    request=build_derived_part_projection_request(_input(receiving=True))
    plan=build_derived_part_sync_plan(request)
    plate_namespace=next(n for n in plan.namespaces if n.namespace=="base_plate_c")
    assert plate_namespace.parts == ()
    assert "base_plate" not in plan.remove_part_keys
    assert plan.active_part_repair=="base_plate"
    assert plan.selected_part_repair=="base_plate"
    assert all(not x.part_key.startswith("base_plate_c")
               for x in plan.add_parts)
    # Door topology remains real and unchanged.
    doors=next(n for n in plan.namespaces if n.namespace=="door_c")
    assert [p.part_key for p in doors.parts]==["door_c1_r1","door_c1_r2"]


def test_other_families_keep_prior_per_door_base_projection():
    request=build_derived_part_projection_request(_input(receiving=False))
    plan=build_derived_part_sync_plan(request)
    plate_namespace=next(n for n in plan.namespaces if n.namespace=="base_plate_c")
    assert [p.part_key for p in plate_namespace.parts]==[
        "base_plate_c1_r1","base_plate_c1_r2",
    ]
    assert "base_plate" in plan.remove_part_keys
    assert plan.active_part_repair is None
    assert plan.selected_part_repair is None


def test_hidden_receiving_original_base_is_reactivated_without_door_base_clones():
    request_data=_input(receiving=True)
    from dataclasses import replace
    request_data=replace(
        request_data,
        available_parts=("door_c1_r1","door_c1_r2","base_plate_c1_r1"),
        single_base_plate_profiles={"X":[{"len":710}],"Y":[{"len":300}]},
    )
    plan=build_derived_part_sync_plan(
        build_derived_part_projection_request(request_data),
    )
    assert [p.part_key for p in plan.add_parts]==["base_plate"]
    assert [p.part_key for p in plan.stash_profiles]==["base_plate"]
    assert plan.active_part_repair=="base_plate"


def test_real_receiving_composition_passes_preservation_intent_from_model():
    source=Path('gui_modules/application/fold_designer_composition_shell_settings.py').read_text(encoding='utf-8')
    assert "receiving_single_base" in source
    assert 'str(snapshot.get("model") or "").strip()' in source
    assert "preserve_single_base_plate=receiving_single_base" in source
    assert "if door_rows and not receiving_single_base" in source
