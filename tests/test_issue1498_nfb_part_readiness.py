# -*- coding: utf-8 -*-
"""#1498 NFB per-physical-part readiness / partial export regression."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from ae_engine.receiving_nfb_part_readiness import (
    BLOCKED, LEGACY, READY, UNAFFECTED,
    NfbPhysicalScope, derive_nfb_part_readiness,
)
from ae_engine.receiving_nfb_dxf_source import NfbSourceInventory
from ae_engine.receiving_nfb_manufacturing_release import (
    NfbValidatedInnerDoorRender, VALIDATED,
)

SHA = "1" * 64


def _scope(*, submitted=True, set_id="setA", bay_id="bayA", version_id="v1"):
    return NfbPhysicalScope(
        set_id=set_id, bay_id=bay_id, version_id=version_id,
        submitted=submitted, inner_door_part_id="inner_door:upper:panel",
        base_plate_part_ids=("base_plate:upper",),
        middle_plate_part_ids=("middle_plate:upper",),
    )


def _inventory(*, color30=0, color150=1, color212=0, unknown=0, diagnostics=()):
    return NfbSourceInventory(
        source_path="400_140X257_107.dxf", source_sha256=SHA,
        source_id="NFB-DXF:" + SHA, status="SOURCE_OBSERVED_UNCERTIFIED",
        entities=(), diagnostics=tuple(diagnostics),
        process_aci_entity_counts=((30,color30),(150,color150),(212,color212)),
        unresolved_color_entities=unknown,
        grouped_entity_counts=(("modelspace",1),),
    )


def _inner(*, sha=SHA, part="inner_door:upper:panel", status=VALIDATED):
    return NfbValidatedInnerDoorRender(
        render_data=SimpleNamespace(metadata={
            "nfb_trial_status":status,
            "nfb_trial_export_approved":True,
        }),
        part_id=part, indexed_model_key=("士林","400_140X257_107.dxf"),
        source_sha256=sha,
        physical_hole_ids=("nfb:upper:1",),
    )


def test_unconfigured_preserves_legacy_even_when_nfb_source_absent():
    result=derive_nfb_part_readiness(_scope(submitted=False))
    # Legacy output remains usable, but UNCONFIGURED is not a verified NFB
    # submission and cannot authorize an NFB manufacturing transaction.
    assert not result.can_submit
    assert all(item.status==LEGACY for item in result.decisions)
    assert result.filter_export_part_ids((
        "inner_door:upper:panel","base_plate:upper",
        "middle_plate:upper","side_panel:left",
    ))[0][-1]=="side_panel:left"


def test_shihlin_upper_source_allows_inner_door_but_blocks_middle_only():
    result=derive_nfb_part_readiness(
        _scope(),source_inventory=_inventory(),verified_inner_door=_inner(),
    )
    assert result.for_part("inner_door:upper:panel").status==READY
    assert result.for_part("base_plate:upper").status==UNAFFECTED
    assert result.for_part("middle_plate:upper").status==BLOCKED
    assert result.for_part("side_panel:right").can_export
    assert result.can_submit  # inner-door MFG-1 READY; middle-plate still held
    with pytest.raises(ValueError,match="middle_plate"):
        result.filter_export_part_ids(("inner_door:upper:panel","middle_plate:upper"))
    allowed,blocked=result.filter_export_part_ids(
        ("inner_door:upper:panel","middle_plate:upper","side_panel:right"),
        partial=True,
    )
    assert allowed==("inner_door:upper:panel","side_panel:right")
    assert tuple(x.part_id for x in blocked)==("middle_plate:upper",)


def test_real_base_color30_and_marking212_have_specific_base_dependency():
    for colors in (dict(color30=1),dict(color212=1)):
        result=derive_nfb_part_readiness(
            _scope(),source_inventory=_inventory(**colors),
            verified_inner_door=_inner(),
        )
        assert result.for_part("base_plate:upper").status==BLOCKED
        assert result.for_part("middle_plate:upper").status==BLOCKED
        assert result.for_part("side_panel:left").status==UNAFFECTED


def test_unknown_missing_and_ambiguous_sources_are_unknown_not_zero():
    for src in (None, _inventory(unknown=2),
                _inventory(diagnostics=("LOWER_GROUP_AMBIGUOUS",))):
        result=derive_nfb_part_readiness(
            _scope(),source_inventory=src,verified_inner_door=_inner(),
        )
        assert result.for_part("inner_door:upper:panel").status==BLOCKED
        assert result.for_part("base_plate:upper").status==BLOCKED
        assert result.for_part("middle_plate:upper").status==BLOCKED
        assert "NFB_SOURCE_COLOR_SCOPE_UNKNOWN" in result.scope_reasons
        assert result.for_part("side_panel:left").status==UNAFFECTED


def test_wrong_approved_inner_source_or_wrong_part_is_not_a_manufacturing_capability():
    for render in (None,_inner(sha="2"*64),_inner(part="inner_door:lower:panel"),
                   _inner(status="PREVIEW_ONLY")):
        result=derive_nfb_part_readiness(
            _scope(),source_inventory=_inventory(),
            verified_inner_door=render,
        )
        assert result.for_part("inner_door:upper:panel").status==BLOCKED


def test_missing_real_plate_id_is_scope_blocker_not_an_invented_part():
    scope=NfbPhysicalScope(
        set_id="A",bay_id="B",version_id="V",submitted=True,
        inner_door_part_id="inner_door:upper:panel",
        base_plate_part_ids=(),middle_plate_part_ids=(),
    )
    result=derive_nfb_part_readiness(
        scope,source_inventory=_inventory(color30=1),
        verified_inner_door=_inner(),
    )
    assert result.for_part("inner_door:upper:panel").status==READY
    assert "BASE_PLATE_PHYSICAL_ID_UNRESOLVED" in result.scope_reasons
    assert "MIDDLE_PLATE_PHYSICAL_ID_UNRESOLVED" not in result.scope_reasons
    assert result.can_submit  # only the genuinely verified MFG-1 door
    with pytest.raises(ValueError,match="dependencies unresolved"):
        result.filter_export_part_ids(("side_panel:left",))
    assert result.filter_export_part_ids(("side_panel:left",),partial=True)[0]==(
        "side_panel:left",)


def test_issue1502_one_authority_inner_door_NFB_no_base_from_illustration():
    # User-shown base DXFs are illustrative. They cannot create a real
    # physical Base Plate, a lower-layer plate or new switch coordinates.
    # The verified inner-door NFB configuration is the only hole-position
    # authority. Downstream parts remain blocked until independently
    # verified against actual manufacturing geometry.
    scope=NfbPhysicalScope(
        set_id="setA", bay_id="bayA", version_id="v1", submitted=True,
        inner_door_part_id="inner_door:upper:panel",
        base_plate_part_ids=(), middle_plate_part_ids=(),
    )
    result=derive_nfb_part_readiness(
        scope, source_inventory=_inventory(color30=16, color150=1, color212=26),
        verified_inner_door=_inner(),
    )
    assert result.can_submit
    assert result.for_part("inner_door:upper:panel").status==READY
    assert tuple(row.part_id for row in result.decisions)==(
        "inner_door:upper:panel",
    )
    assert set(result.scope_reasons)=={
        "BASE_PLATE_PHYSICAL_ID_UNRESOLVED",
    }
    assert result.filter_export_part_ids(
        ("inner_door:upper:panel",), partial=True,
    )[0]==("inner_door:upper:panel",)
    with pytest.raises(ValueError, match="physical dependencies unresolved"):
        result.filter_export_part_ids(("inner_door:upper:panel",))
    # Missing source-verified inner door must block even this partial scope.
    not_verified=derive_nfb_part_readiness(
        scope, source_inventory=_inventory(color30=16, color150=1, color212=26),
        verified_inner_door=None,
    )
    assert not not_verified.can_submit
    assert not_verified.for_part("inner_door:upper:panel").status==READY


def test_each_set_bay_version_independent_and_no_cross_scope_ready_cache():
    approved=derive_nfb_part_readiness(
        _scope(),source_inventory=_inventory(),verified_inner_door=_inner(),
    )
    missing=derive_nfb_part_readiness(
        _scope(bay_id="bayB",version_id="v2"),source_inventory=None,
    )
    assert approved.for_part("inner_door:upper:panel").status==READY
    assert missing.for_part("inner_door:upper:panel").status==BLOCKED
    assert approved.scope.identity != missing.scope.identity


def test_duplicate_or_ambiguous_physical_ids_fail_closed():
    with pytest.raises(ValueError,match="collision"):
        NfbPhysicalScope(
            set_id="A",bay_id="B",version_id="v1",submitted=True,
            inner_door_part_id="inner_door:upper:panel",
            middle_plate_part_ids=("inner_door:upper:panel",),
        )
    with pytest.raises(ValueError,match="boolean"):
        NfbPhysicalScope(
            set_id="A",bay_id="B",version_id="v1",submitted="false",
            inner_door_part_id="inner_door:upper:panel",
        )
    result=derive_nfb_part_readiness(
        _scope(submitted=False),
    )
    with pytest.raises(ValueError,match="duplicate"):
        result.filter_export_part_ids(("side_panel:left","side_panel:left"))


def test_duplicate_process_color_rows_cannot_hide_real_base_holes():
    original=_inventory(color30=1)
    poisoned=replace(original,process_aci_entity_counts=(
        (30,1),(150,1),(212,0),(30,0),
    ))
    status=derive_nfb_part_readiness(
        _scope(),source_inventory=poisoned,verified_inner_door=_inner(),
    )
    assert not status.can_submit
    assert status.for_part("inner_door:upper:panel").status==BLOCKED
    assert status.for_part("base_plate:upper").status==BLOCKED
    assert status.for_part("middle_plate:upper").status==BLOCKED
    assert "NFB_SOURCE_COLOR_SCOPE_UNKNOWN" in status.scope_reasons


@pytest.mark.parametrize("bad_counts",(
    ((30,False),(150,1),(212,0)),
    ((30,0),(150,1)),
    ((30,0),(150,1),(212,-1)),
    ((30,0),(150,0),(150,1),(212,0)),
))
def test_missing_or_malformed_color_evidence_is_unknown_not_zero(bad_counts):
    inventory=replace(_inventory(),process_aci_entity_counts=bad_counts)
    state=derive_nfb_part_readiness(
        _scope(),source_inventory=inventory,verified_inner_door=_inner(),
    )
    assert state.for_part("base_plate:upper").status==BLOCKED
    assert "NFB_SOURCE_COLOR_SCOPE_UNKNOWN" in state.scope_reasons


def test_unique_out_of_order_color_counts_do_not_change_valid_readiness():
    reordered=replace(_inventory(),process_aci_entity_counts=(
        (212,0),(150,1),(30,0),
    ))
    state=derive_nfb_part_readiness(
        _scope(),source_inventory=reordered,verified_inner_door=_inner(),
    )
    assert state.can_submit
    assert state.for_part("base_plate:upper").status==UNAFFECTED
    assert state.for_part("middle_plate:upper").status==BLOCKED
