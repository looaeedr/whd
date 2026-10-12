# -*- coding: utf-8 -*-
"""#1501 source-bound physical piece manifest, partial-only DXF authorization."""
from hashlib import sha256
from types import SimpleNamespace

import pytest

from ae_engine.receiving_nfb_export_manifest import (
    INNER_DOOR,BASE_PLATE,MIDDLE_PLATE,OTHER,NfbActualPart,
    derive_nfb_partial_export_manifest,
)
from ae_engine.receiving_nfb_part_readiness import (
    NfbPhysicalScope,READY,BLOCKED,UNAFFECTED,LEGACY,
)
from ae_engine.receiving_nfb_dxf_source import NfbSourceInventory
from ae_engine.receiving_nfb_manufacturing_release import (
    NfbValidatedInnerDoorRender,VALIDATED,
)

MODEL="400_140X257_107.dxf"


def _prepared(tmp_path,*,submitted=True,color30=0,color150=1):
    file=tmp_path/MODEL
    file.write_bytes(b"real-byte-source-test-evidence-1")
    digest=sha256(file.read_bytes()).hexdigest()
    inventory=NfbSourceInventory(
        source_path=str(file),source_sha256=digest,
        source_id="NFB-DXF:"+digest,status="SOURCE_OBSERVED_UNCERTIFIED",
        entities=(),diagnostics=(),
        process_aci_entity_counts=((30,color30),(150,color150),(212,0)),
        unresolved_color_entities=0,grouped_entity_counts=(("modelspace",1),),
    )
    door=NfbValidatedInnerDoorRender(
        render_data=SimpleNamespace(metadata={
            "nfb_trial_status":VALIDATED,"nfb_trial_export_approved":True,
        }),
        part_id="inner1",indexed_model_key=("士林",MODEL),
        source_sha256=digest,physical_hole_ids=("nfb:bay1:slot1",),
        verified_hole_locations=(("nfb:bay1:slot1",0.0,1,0,90),),
    )
    scope=NfbPhysicalScope(
        "setA","bayA","version-1",submitted,"inner1",
        ("base1",),("middle1",),
    )
    bay={"stable_id":"bayA"}
    if submitted:
        bay["nfb_config_submitted"]=True
        bay["nfb_config"]={"holes":[{
            "physical_hole_id":"nfb:bay1:slot1",
            "model_filename":MODEL,
            "manual_x_state":"CONFIRMED","manual_x_mm":0,
            "datum_revision":"MEASURED_V1","datum_snapshot":{"w":800},
            "rotation_deg":90,"layer_count":1,"slot_index":0,
        }]}
    parts=[
        NfbActualPart("inner1",INNER_DOOR,2),
        NfbActualPart("base1",BASE_PLATE,1),
        NfbActualPart("middle1",MIDDLE_PLATE,4),
        NfbActualPart("side1",OTHER,3),
    ]
    opts=dict(scope=scope,saved_bay=bay,set_brand="士林",actual_parts=parts,
              source_inventory=inventory,verified_inner_door=door,
              source_path=file,proven_unaffected_part_ids=("side1",))
    return opts


def test_shihlin_color150_partial_only_counts_real_pieces(tmp_path):
    m=derive_nfb_partial_export_manifest(**_prepared(tmp_path))
    status={r.part_id:r.status for r in m.rows}
    assert status=={"inner1":READY,"base1":UNAFFECTED,
                    "middle1":BLOCKED,"side1":UNAFFECTED}
    assert m.authorized_part_ids==("inner1","base1","side1")
    assert m.actual_export_count==6
    assert m.held_actual_count==4
    assert m.partial_only and not m.whole_ready
    assert m.require_export(("inner1","side1"),partial=True)==("inner1","side1")
    with pytest.raises(ValueError,match="partial only"):
        m.require_export(("inner1","side1"))
    with pytest.raises(ValueError,match="BLOCKED"):
        m.require_export(("middle1",),partial=True)
    with pytest.raises(ValueError,match="not in current physical scene"):
        m.require_export(("hidden_unverified_part",),partial=True)
    report=m.report()
    assert report["set_id"]=="setA" and report["bay_id"]=="bayA"
    assert report["version_id"]=="version-1"
    assert report["actual_export_count"]==6
    assert any("MIDDLE_PLATE_NFB_COLOR150_UNVERIFIED" in row["reasons"]
               for row in report["rows"] if row["part_id"]=="middle1")
    assert "whole_ready" in report and report["whole_ready"] is False


def test_color30_adds_base_hold_without_poisoning_other_part(tmp_path):
    m=derive_nfb_partial_export_manifest(**_prepared(tmp_path,color30=1))
    assert [r.part_id for r in m.held_rows]==["base1","middle1"]
    assert m.authorized_part_ids==("inner1","side1")
    assert m.actual_export_count==5


def test_source_sha_change_invalidates_nfb_but_not_proven_other(tmp_path):
    opts=_prepared(tmp_path)
    orig=derive_nfb_partial_export_manifest(**opts)
    assert orig.rows[0].status==READY
    opts["source_path"].write_bytes(b"changed")
    now=derive_nfb_partial_export_manifest(**opts)
    assert now.rows[0].status==BLOCKED
    assert "ORIGINAL_NFB_DXF_MISSING_OR_SHA_CHANGED" in now.unresolved_dependencies
    assert now.authorized_part_ids==("side1",)
    assert now.actual_export_count==3
    assert now.require_export(("side1",),partial=True)==("side1",)
    opts["source_path"].unlink()
    absent=derive_nfb_partial_export_manifest(**opts)
    assert absent.authorized_part_ids==("side1",)
    assert not absent.whole_ready


def test_missing_explicit_middle_id_is_not_inferred_from_inner_door_color150(tmp_path):
    opts=_prepared(tmp_path)
    opts["scope"]=NfbPhysicalScope(
        "setA","bayA","version-1",True,"inner1",
        ("base1",),(),
    )
    m=derive_nfb_partial_export_manifest(**opts)
    assert "MIDDLE_PLATE_PHYSICAL_ID_UNRESOLVED" not in m.unresolved_dependencies
    assert next(x for x in m.rows if x.part_id=="middle1").status==BLOCKED
    assert m.authorized_part_ids==("inner1","base1","side1")
    assert not m.whole_ready
    assert "middle1" not in m.authorized_part_ids


def test_unconfigured_keeps_legacy_batching_and_draft_is_not_submitted(tmp_path):
    opts=_prepared(tmp_path,submitted=False)
    m=derive_nfb_partial_export_manifest(**opts)
    assert not m.nfb_config_submitted and m.whole_ready
    assert all(p.status==LEGACY for p in m.rows)
    assert m.actual_export_count==10
    assert m.require_export(tuple(p.part_id for p in opts["actual_parts"]))==(
        "inner1","base1","middle1","side1",
    )
    # Draft-only UI has no saved NFB manufacturing authority.
    opts["saved_bay"]["nfb_config_submitted"]=False
    assert derive_nfb_partial_export_manifest(**opts).whole_ready


def test_identity_role_count_and_target_list_fail_closed(tmp_path):
    opts=_prepared(tmp_path)
    for rows in (
        [NfbActualPart("inner1",INNER_DOOR),NfbActualPart("inner1",INNER_DOOR)],
        [NfbActualPart("inner1",OTHER),NfbActualPart("base1",BASE_PLATE)],
    ):
        with pytest.raises(ValueError):
            derive_nfb_partial_export_manifest(**{
                **opts,"actual_parts":rows,
                "proven_unaffected_part_ids":("missing-other",),
            })
    with pytest.raises(ValueError,match="Bay stable ID"):
        derive_nfb_partial_export_manifest(**{**opts,
            "saved_bay":{**opts["saved_bay"],"stable_id":"wrong"}})
    with pytest.raises(ValueError,match="duplicate"):
        derive_nfb_partial_export_manifest(**{**opts,
            "actual_parts":opts["actual_parts"]+opts["actual_parts"][:1]})
    with pytest.raises(ValueError,match="count"):
        NfbActualPart("a",INNER_DOOR,0)
    m=derive_nfb_partial_export_manifest(**opts)
    with pytest.raises(ValueError,match="repeats physical part"):
        m.require_export(("inner1","inner1"),partial=True)


def test_one_bay_evidence_does_not_authorize_another_bay(tmp_path):
    opts=_prepared(tmp_path)
    m=derive_nfb_partial_export_manifest(**opts)
    assert m.rows[0].status==READY
    other_scope=NfbPhysicalScope(
        "setA","bayB","version-2",True,"inner2",(),(),
    )
    with pytest.raises(ValueError,match="Bay stable ID"):
        derive_nfb_partial_export_manifest(**{**opts,"scope":other_scope})
    assert m.scope.identity==("setA","bayA","version-1")


def test_other_part_without_independent_unaffected_proof_stays_held(tmp_path):
    opts=_prepared(tmp_path)
    opts["proven_unaffected_part_ids"]=()
    m=derive_nfb_partial_export_manifest(**opts)
    assert "side1" not in m.authorized_part_ids
    assert next(x for x in m.rows if x.part_id=="side1").reasons==(
        "OTHER_PART_UNAFFECTED_OWNER_NOT_VERIFIED",
    )



def test_saved_hole_moved_or_rotated_requires_new_cutting_proof(tmp_path):
    opts=_prepared(tmp_path)
    assert "inner1" in derive_nfb_partial_export_manifest(**opts).authorized_part_ids
    for field,value in (("manual_x_mm",22),("rotation_deg",180),
                        ("slot_index",1),("model_filename","wrong.dxf")):
        updated={**opts["saved_bay"],
                 "nfb_config":{"holes":[{
                     **opts["saved_bay"]["nfb_config"]["holes"][0],
                     field:value,
                 }]}}
        m=derive_nfb_partial_export_manifest(**{**opts,"saved_bay":updated})
        assert "inner1" not in m.authorized_part_ids
        assert "SAVED_NFBCONFIG_DIFFERS_FROM_VERIFIED_CUTTING" in m.unresolved_dependencies
        assert m.partial_only and not m.whole_ready
        assert "side1" in m.authorized_part_ids


def test_cross_brand_same_filename_must_not_reuse_source_proof(tmp_path):
    opts=_prepared(tmp_path)
    mismatch=derive_nfb_partial_export_manifest(**{**opts,"set_brand":"東元"})
    assert "inner1" not in mismatch.authorized_part_ids
    assert "SAVED_NFBCONFIG_DIFFERS_FROM_VERIFIED_CUTTING" in mismatch.unresolved_dependencies
    with pytest.raises(ValueError,match="Set brand"):
        derive_nfb_partial_export_manifest(**{**opts,"set_brand":""})
