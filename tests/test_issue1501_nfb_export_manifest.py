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
        # The once-matching source cannot prove that a newly edited model/
        # position has zero Color30/212 dependencies on the physical base.
        assert "NFB_SOURCE_COLOR_SCOPE_UNKNOWN" in m.unresolved_dependencies
        assert next(r for r in m.rows if r.part_id == "base1").status == BLOCKED
        assert next(r for r in m.rows if r.part_id == "middle1").status == BLOCKED
        assert m.partial_only and not m.whole_ready
        assert m.authorized_part_ids == ("side1",)
        assert m.actual_export_count == 3
        assert m.held_actual_count == 7
        with pytest.raises(ValueError, match="BLOCKED"):
            m.require_export(("base1",), partial=True)


def test_cross_brand_same_filename_must_not_reuse_source_proof(tmp_path):
    opts=_prepared(tmp_path)
    mismatch=derive_nfb_partial_export_manifest(**{**opts,"set_brand":"東元"})
    assert "inner1" not in mismatch.authorized_part_ids
    assert "SAVED_NFBCONFIG_DIFFERS_FROM_VERIFIED_CUTTING" in mismatch.unresolved_dependencies
    with pytest.raises(ValueError,match="Set brand"):
        derive_nfb_partial_export_manifest(**{**opts,"set_brand":""})


@pytest.mark.parametrize(("aci30", "aci212", "unresolved", "base_status", "actual_count"), (
    (False, False, False, UNAFFECTED, 6),
    (True, False, False, BLOCKED, 5),
    (False, True, False, BLOCKED, 5),
    (True, False, True, BLOCKED, 3),
))
def test_ac38_real_dxf_color_inventory_drives_physical_partial_manifest(
    tmp_path, aci30, aci212, unresolved, base_status, actual_count,
):
    """#1504 AC38: actual DXF reader -> saved physical Bay -> piece manifest.

    This exercises generated *real DXF bytes* and the original source parser;
    they are not supplier-certified originals nor authority for whole MFG-2.
    """
    from dataclasses import replace
    import ezdxf
    from ae_engine.receiving_nfb_dxf_source import inspect_nfb_dxf_source

    options = _prepared(tmp_path)
    source = tmp_path / "observed-source.dxf"
    document = ezdxf.new("R2010")
    scene = document.modelspace()
    scene.add_lwpolyline(
        ((0, 0), (57, 0), (57, 96), (0, 96)),
        close=True, dxfattribs={"color": 150},
    )
    if aci30:
        scene.add_circle((7, 7), 2, dxfattribs={"color": 30})
    if aci212:
        scene.add_line((3, 3), (8, 8), dxfattribs={"color": 212})
    if unresolved:
        # Explicit BYBLOCK with no owner is not a certified zero.
        scene.add_line((1, 1), (2, 2), dxfattribs={"color": 0})
    document.saveas(source)
    inventory = inspect_nfb_dxf_source(source)
    assert inventory.source_sha256 == sha256(source.read_bytes()).hexdigest()
    assert dict(inventory.process_aci_entity_counts)[150] == 1
    assert dict(inventory.process_aci_entity_counts)[30] == int(aci30)
    assert dict(inventory.process_aci_entity_counts)[212] == int(aci212)
    options.update(
        source_path=source,
        source_inventory=inventory,
        verified_inner_door=replace(
            options["verified_inner_door"],
            source_sha256=inventory.source_sha256,
        ),
    )
    manifestation = derive_nfb_partial_export_manifest(**options)
    rows = {row.part_id: row for row in manifestation.rows}
    assert rows["base1"].status == base_status
    assert rows["middle1"].status == BLOCKED
    assert rows["side1"].status == UNAFFECTED
    assert rows["side1"].may_export is True
    assert rows["base1"].may_export is (base_status == UNAFFECTED)
    assert manifestation.actual_export_count == actual_count
    assert manifestation.held_actual_count == 10 - actual_count
    assert manifestation.partial_only and not manifestation.whole_ready
    assert manifestation.report()["actual_export_count"] == actual_count
    assert manifestation.require_export(("side1",), partial=True) == ("side1",)
    with pytest.raises(ValueError, match="partial only"):
        manifestation.require_export(("side1",))
    for held in manifestation.held_rows:
        with pytest.raises(ValueError, match="BLOCKED"):
            manifestation.require_export((held.part_id,), partial=True)
    if unresolved:
        assert inventory.unresolved_color_entities > 0
        assert "NFB_SOURCE_COLOR_SCOPE_UNKNOWN" in manifestation.unresolved_dependencies
        assert rows["inner1"].status == BLOCKED
    else:
        assert inventory.unresolved_color_entities == 0
        assert rows["inner1"].status == READY
    # A changed source has no reusable prior manifest authorization.
    source.write_bytes(source.read_bytes() + b"\nREMOVED-TRUST")
    revoked = derive_nfb_partial_export_manifest(**options)
    assert revoked.authorized_part_ids == ("side1",)
    assert revoked.actual_export_count == 3
    assert not revoked.whole_ready



@pytest.mark.parametrize(
    ("aci30", "aci212", "unresolved", "expected_base", "expected_count"),
    (
        (False, False, False, UNAFFECTED, 6),
        (True, False, False, BLOCKED, 5),
        (False, True, False, BLOCKED, 5),
        (False, False, True, BLOCKED, 3),
    ),
)
def test_ac38_current_receiving_source_guards_only_actual_parts_and_side(
    tmp_path, aci30, aci212, unresolved, expected_base, expected_count,
):
    """One submitted Bay, one source, real DXF parsing and only actual parts.

    Historic middle-plate role is NOT silently added to today's Receiving.
    Real unapproved color evidence holds the Base only; unrelated physically
    present SIDE is independently verifiable, never collateral damage.
    This does not certify factory welding or arbitrary V5 models.
    """
    from dataclasses import replace
    import ezdxf
    from ae_engine.receiving_nfb_dxf_source import inspect_nfb_dxf_source

    options = _prepared(tmp_path)
    options["scope"] = NfbPhysicalScope(
        "setA", "bayA", "version-1", True, "inner1",
        ("base1",), (),
    )
    options["actual_parts"] = tuple(
        item for item in options["actual_parts"] if item.part_id != "middle1"
    )
    source = tmp_path / "ac38_physical_dxf.dxf"
    document = ezdxf.new("R2010")
    sheet = document.modelspace()
    sheet.add_lwpolyline(
        ((0, 0), (57, 0), (57, 96), (0, 96)),
        close=True, dxfattribs={"color": 150},
    )
    if aci30:
        sheet.add_circle((3, 4), 2, dxfattribs={"color": 30})
    if aci212:
        sheet.add_line((1, 2), (8, 2), dxfattribs={"color": 212})
    if unresolved:
        sheet.add_line((5, 5), (6, 6), dxfattribs={"color": 0})
    document.saveas(source)
    source_inv = inspect_nfb_dxf_source(source)
    options.update(
        source_path=source,
        source_inventory=source_inv,
        verified_inner_door=replace(
            options["verified_inner_door"],
            source_sha256=source_inv.source_sha256,
        ),
    )
    manifest = derive_nfb_partial_export_manifest(**options)
    decisions = {row.part_id: row for row in manifest.rows}
    assert set(decisions) == {"inner1", "base1", "side1"}
    assert decisions["base1"].status == expected_base
    assert decisions["side1"].status == UNAFFECTED
    assert decisions["side1"].actual_count == 3
    assert manifest.actual_export_count == expected_count
    assert manifest.held_actual_count == 6 - expected_count
    assert manifest.report()["assembly_status"] != "COMPLETE"
    assert not any("MIDDLE_PLATE" in token for token in manifest.unresolved_dependencies)
    assert manifest.require_export(("side1",), partial=True) == ("side1",)
    if unresolved:
        assert decisions["inner1"].status == BLOCKED
        assert "NFB_SOURCE_COLOR_SCOPE_UNKNOWN" in manifest.unresolved_dependencies
    else:
        assert decisions["inner1"].status == READY
        assert manifest.require_export(("inner1", "side1"), partial=True) == (
            "inner1", "side1",
        )
    if expected_base == BLOCKED:
        with pytest.raises(ValueError, match="BLOCKED"):
            manifest.require_export(("base1",), partial=True)

    # A changed original source revokes any previously READY inner/Base
    # while retaining only the real independent SIDE; never treat an old
    # source inventory's zero Color30 as a valid present-source zero.
    source.write_bytes(source.read_bytes() + b"\nSOURCE_REPLACED")
    stale = derive_nfb_partial_export_manifest(**options)
    assert stale.authorized_part_ids == ("side1",)
    assert stale.actual_export_count == 3
    assert stale.held_actual_count == 3
    assert stale.partial_only
    assert "ORIGINAL_NFB_DXF_MISSING_OR_SHA_CHANGED" in stale.unresolved_dependencies
    with pytest.raises(ValueError, match="BLOCKED"):
        stale.require_export(("inner1",), partial=True)



@pytest.mark.parametrize(
    ("case", "expected_status", "allowed", "count"),
    (
        ("upper_only", (READY, UNAFFECTED, UNAFFECTED), ("inner1", "base1", "side1"), 6),
        ("upper_and_base", (READY, BLOCKED, UNAFFECTED), ("inner1", "side1"), 5),
        ("no_upper", (BLOCKED, UNAFFECTED, UNAFFECTED), ("base1", "side1"), 4),
        ("unknown_aci", (BLOCKED, BLOCKED, UNAFFECTED), ("side1",), 3),
        ("source_missing", (BLOCKED, BLOCKED, UNAFFECTED), ("side1",), 3),
    ),
)
def test_ac44_live_source_partial_must_not_masquerade_as_whole_export(
    tmp_path, case, expected_status, allowed, count,
):
    """Original DXF reader → saved Bay → real-part manifest → export gate.

    A historical Color150 source alone never creates Receiving middle plate.
    Current numeric CSV V5 and the real output writer have their independent
    approval requirements. This proves manifest scope only, not factory NC.
    """
    from dataclasses import replace
    import ezdxf
    from ae_engine.receiving_nfb_dxf_source import inspect_nfb_dxf_source

    opts = _prepared(tmp_path)
    opts["scope"] = NfbPhysicalScope(
        "setA", "bayA", "version-1", True, "inner1",
        ("base1",), (),
    )
    opts["actual_parts"] = tuple(
        part for part in opts["actual_parts"] if part.part_id != "middle1"
    )
    source = tmp_path / "ac44_actual_source.dxf"
    dxf = ezdxf.new("R2010")
    msp = dxf.modelspace()
    if case not in ("no_upper",):
        msp.add_lwpolyline(
            ((0, 0), (57, 0), (57, 96), (0, 96)),
            close=True, dxfattribs={"color": 150},
        )
    if case == "upper_and_base":
        msp.add_circle((12, 18), 2, dxfattribs={"color": 30})
    if case == "unknown_aci":
        msp.add_line((1, 1), (3, 3), dxfattribs={"color": 0})
    if case == "no_upper":
        msp.add_line((0, 0), (1, 0), dxfattribs={"color": 3})
    dxf.saveas(source)
    observed = inspect_nfb_dxf_source(source)
    opts.update(
        source_path=source,
        source_inventory=observed,
        verified_inner_door=replace(
            opts["verified_inner_door"],
            source_sha256=observed.source_sha256,
        ),
    )
    if case == "source_missing":
        source.unlink()
    manifest = derive_nfb_partial_export_manifest(**opts)
    assert set(row.part_id for row in manifest.rows) == {
        "inner1", "base1", "side1"
    }
    assert tuple(
        next(row for row in manifest.rows if row.part_id == part_id).status
        for part_id in ("inner1", "base1", "side1")
    ) == expected_status
    assert manifest.authorized_part_ids == allowed
    assert manifest.actual_export_count == count
    assert manifest.held_actual_count == 6 - count
    assert manifest.require_export(("side1",), partial=True) == ("side1",)
    assert manifest.report()["assembly_status"] == (
        "NOT_VALIDATED_AS_COMPLETE_NFB_ASSEMBLY"
    )
    if case != "upper_only":
        assert manifest.partial_only and not manifest.whole_ready
        with pytest.raises(ValueError, match="whole manufacturing not ready|partial only"):
            manifest.require_export(allowed, partial=False)
        for part in manifest.held_rows:
            with pytest.raises(ValueError, match="BLOCKED"):
                manifest.require_export((part.part_id,), partial=True)
    else:
        assert manifest.whole_ready
        assert manifest.require_export(
            ("inner1", "base1", "side1"), partial=False
        ) == ("inner1", "base1", "side1")


@pytest.mark.parametrize("invalid_flag", (0, 1, None, "", "true", [], {}))
def test_ac39_partial_export_requires_explicit_boolean(invalid_flag, tmp_path):
    manifest = derive_nfb_partial_export_manifest(**_prepared(tmp_path))
    assert manifest.partial_only and not manifest.whole_ready
    with pytest.raises(TypeError, match="explicit boolean"):
        manifest.require_export(("inner1",), partial=invalid_flag)
    assert manifest.require_export(("inner1",), partial=True) == ("inner1",)
    with pytest.raises(ValueError, match="partial only"):
        manifest.require_export(("inner1",), partial=False)


@pytest.mark.parametrize(("status", "may_export", "count"), (
    (BLOCKED, True, 2),
    (READY, 1, 2),
    (READY, "true", 2),
    (READY, True, 0),
    (READY, True, True),
    (LEGACY, True, 2),
))
def test_ac44_partial_manifest_must_not_authorize_forged_blocked_or_nonboolean_row(
    tmp_path, status, may_export, count,
):
    """Typed holder reports alone must never override true per-part readiness."""
    from dataclasses import replace

    current = derive_nfb_partial_export_manifest(**_prepared(tmp_path))
    door = next(row for row in current.rows if row.part_id == "inner1")
    forged = replace(
        current, rows=tuple(
            replace(row, status=status, may_export=may_export, actual_count=count)
            if row.part_id == "inner1" else row
            for row in current.rows
        ),
    )
    assert door.status == READY and door.may_export is True
    with pytest.raises(ValueError, match="BLOCKED"):
        forged.require_export(("inner1",), partial=True)
    # A real independently unaffected SIDE must remain available in the
    # very same manifest; this is per-part, not all-or-nothing blocking.
    assert forged.require_export(("side1",), partial=True) == ("side1",)


def test_ac44_duplicate_physical_part_cannot_hide_a_blocked_legacy_source(tmp_path):
    """A forged second row with the same part ID must not replace its owner."""
    from dataclasses import replace

    current = derive_nfb_partial_export_manifest(**_prepared(tmp_path))
    original = next(row for row in current.rows if row.part_id == "inner1")
    duplicate = replace(original, role=OTHER, status=UNAFFECTED, may_export=True)
    forged = replace(current, rows=(*current.rows, duplicate))
    with pytest.raises(ValueError, match="duplicate physical part BLOCKED"):
        forged.require_export(("inner1",), partial=True)


@pytest.mark.parametrize("forgery", ("whole_ready", "clear_unresolved", "integer_ready"))
def test_ac44_forged_whole_ready_never_bypasses_blocked_physical_parts(
    tmp_path, forgery,
):
    """A forged full-export flag cannot approve only the independent side."""
    from dataclasses import replace

    manifest = derive_nfb_partial_export_manifest(**_prepared(tmp_path, color30=1))
    assert manifest.partial_only and not manifest.whole_ready
    assert manifest.authorized_part_ids == ("inner1", "side1")
    if forgery == "whole_ready":
        forged = replace(manifest, whole_ready=True)
    elif forgery == "clear_unresolved":
        forged = replace(manifest, whole_ready=True, unresolved_dependencies=())
    else:
        forged = replace(manifest, whole_ready=1)
    with pytest.raises(ValueError, match="whole manufacturing not ready"):
        forged.require_export(("side1",), partial=False)
    # The independently verified OTHER part is still valid for partial-only.
    assert forged.require_export(("side1",), partial=True) == ("side1",)


def test_ac44_unsubmitted_legacy_manifest_still_exports_original_physical_parts(
    tmp_path,
):
    opts = _prepared(tmp_path, submitted=False)
    manifest = derive_nfb_partial_export_manifest(**opts)
    requested = tuple(part.part_id for part in opts["actual_parts"])
    assert manifest.require_export(requested, partial=False) == requested


@pytest.mark.parametrize("corruption", (
    "scope_unsubmitted", "row_other_bay", "row_other_version",
    "door_disguised_other",
))
def test_ac44_manifest_rejects_cross_bay_version_or_submitted_identity_for_export(
    tmp_path, corruption,
):
    from dataclasses import replace

    original = derive_nfb_partial_export_manifest(**_prepared(tmp_path))
    door = next(row for row in original.rows if row.part_id == "inner1")
    assert original.require_export(("inner1",), partial=True) == ("inner1",)
    if corruption == "scope_unsubmitted":
        invalid = replace(
            original, scope=replace(original.scope, submitted=False),
        )
    else:
        if corruption == "row_other_bay":
            altered = replace(door, bay_id="another-bay")
        elif corruption == "row_other_version":
            altered = replace(door, version_id="another-version")
        else:
            altered = replace(door, role=OTHER, status=UNAFFECTED)
        invalid = replace(
            original,
            rows=tuple(altered if row.part_id == "inner1" else row
                       for row in original.rows),
        )
    with pytest.raises(ValueError, match="BLOCKED"):
        invalid.require_export(("inner1",), partial=True)
    # Nothing in a corrupted owner's typed record can approve another DXF.

@pytest.mark.parametrize("pending_x_state", (
    "NONE", "UNVERIFIED_BASIS", "RECONFIRM_REQUIRED",
))
def test_swt21_unconfirmed_saved_world_x_never_reuses_old_manufacturing_proof(
    tmp_path, pending_x_state,
):
    """A matching historic XY numeral does not confirm its operator datum.

    Same real physical Bay, present source bytes, unchanged physical hole and
    old validated CUTTING remain; operator revoked CONFIRMED X in saved data.
    Only unrelated real SIDE remains eligible for partial DXF.
    """
    opts = _prepared(tmp_path, color30=1)
    opts["scope"] = NfbPhysicalScope(
        "setA", "bayA", "version-1", True, "inner1",
        ("base1",), (),
    )
    opts["actual_parts"] = tuple(
        part for part in opts["actual_parts"] if part.part_id != "middle1"
    )
    hole = opts["saved_bay"]["nfb_config"]["holes"][0]
    assert hole["manual_x_state"] == "CONFIRMED"
    assert hole["manual_x_mm"] == 0
    hole["manual_x_state"] = pending_x_state
    manifest = derive_nfb_partial_export_manifest(**opts)
    by_id = {part.part_id: part for part in manifest.rows}
    assert set(by_id) == {"inner1", "base1", "side1"}
    assert by_id["inner1"].status == BLOCKED
    assert by_id["base1"].status == BLOCKED
    assert by_id["side1"].status == UNAFFECTED
    assert manifest.authorized_part_ids == ("side1",)
    assert manifest.actual_export_count == 3
    assert manifest.held_actual_count == 3
    assert manifest.partial_only
    assert "SAVED_NFBCONFIG_DIFFERS_FROM_VERIFIED_CUTTING" in (
        manifest.unresolved_dependencies
    )
    with pytest.raises(ValueError, match="BLOCKED"):
        manifest.require_export(("inner1",), partial=True)
    with pytest.raises(ValueError, match="BLOCKED"):
        manifest.require_export(("base1",), partial=True)
    assert manifest.require_export(("side1",), partial=True) == ("side1",)


@pytest.mark.parametrize("outdated_owner", ("width", "model", "bay", "rotation"))
def test_swt21_saved_x_datum_drift_is_normalized_before_manufacturing(
    tmp_path, outdated_owner,
):
    """Canonical saved Bay X datum cannot be bypassed by reading raw values."""
    opts = _prepared(tmp_path, color30=1)
    opts["scope"] = NfbPhysicalScope(
        "setA", "bayA", "version-1", True, "inner1",
        ("base1",), (),
    )
    opts["actual_parts"] = tuple(
        part for part in opts["actual_parts"] if part.part_id != "middle1"
    )
    hole = opts["saved_bay"]["nfb_config"]["holes"][0]
    assert hole["manual_x_state"] == "CONFIRMED"
    if outdated_owner == "width":
        opts["saved_bay"]["width"] = 750
    elif outdated_owner == "model":
        hole["datum_snapshot"]["model_filename"] = "changed-source.dxf"
    elif outdated_owner == "bay":
        hole["datum_snapshot"]["bay_id"] = "other-physical-bay"
    elif outdated_owner == "rotation":
        hole["datum_snapshot"]["rotation_deg"] = 180
    manifest = derive_nfb_partial_export_manifest(**opts)
    assert manifest.authorized_part_ids == ("side1",)
    assert manifest.actual_export_count == 3
    assert manifest.held_actual_count == 3
    assert "SAVED_NFBCONFIG_DIFFERS_FROM_VERIFIED_CUTTING" in (
        manifest.unresolved_dependencies
    )
    for part_id in ("inner1", "base1"):
        with pytest.raises(ValueError, match="BLOCKED"):
            manifest.require_export((part_id,), partial=True)
    assert manifest.require_export(("side1",), partial=True) == ("side1",)


@pytest.mark.parametrize("source_loss", ("empty_slots", "pending_model", "missing_dxf", "missing_inventory"))
def test_swt21_missing_committed_source_or_slot_never_authorizes_dependent_parts(
    tmp_path, source_loss,
):
    """A real submitted owner cannot turn UNKNOWN into Color30/150 zero."""
    opts = _prepared(tmp_path, color30=1)
    opts["scope"] = NfbPhysicalScope(
        "setA", "bayA", "version-1", True, "inner1",
        ("base1",), (),
    )
    opts["actual_parts"] = tuple(
        part for part in opts["actual_parts"] if part.part_id != "middle1"
    )
    if source_loss == "empty_slots":
        opts["saved_bay"]["nfb_config"]["holes"] = []
        with pytest.raises(ValueError, match="explicit hole list"):
            derive_nfb_partial_export_manifest(**opts)
        return
    if source_loss == "pending_model":
        opts["saved_bay"]["nfb_config"]["holes"][0]["model_filename"] = "reselect.dxf"
    elif source_loss == "missing_dxf":
        opts["source_path"] = tmp_path / "unavailable_original.dxf"
    else:
        opts["source_inventory"] = None
    manifest = derive_nfb_partial_export_manifest(**opts)
    status = {part.part_id: part.status for part in manifest.rows}
    assert status == {"inner1": BLOCKED, "base1": BLOCKED, "side1": UNAFFECTED}
    assert manifest.authorized_part_ids == ("side1",)
    assert manifest.actual_export_count == 3
    assert manifest.held_actual_count == 3
    assert not manifest.whole_ready
    with pytest.raises(ValueError, match="BLOCKED"):
        manifest.require_export(("inner1",), partial=True)
    assert manifest.require_export(("side1",), partial=True) == ("side1",)



def test_ac23_one_real_bay_changed_x_datum_survives_project_reopen_and_blocks_dxf(
    tmp_path,
):
    """A former CONFIRMED X must never resurrect from physical Bay W changes.

    Uses the actual saved ReceivingLayout Bay, project writer/reader, source-
    inspected DXF, and the SAME physical-part manufacturing manifest.
    Operator reapproval is NOT simulated or fabricated by an approval flag.
    """
    from copy import deepcopy
    from dataclasses import replace
    import ezdxf

    from ae_engine.receiving_layout import update_receiving_bay
    from ae_engine.receiving_nfb_dxf_source import inspect_nfb_dxf_source
    from phase6_project_file import read_project, write_project
    from tests.test_issue1499_nfb_persistence import _layout, _payload

    opts = _prepared(tmp_path, color30=1)
    opts["actual_parts"] = tuple(
        part for part in opts["actual_parts"] if part.part_id != "middle1"
    )
    layout = _layout()
    set_id = layout["sets"][0]["stable_id"]
    bay_id = layout["sets"][0]["bays"][0]["stable_id"]
    opts["scope"] = NfbPhysicalScope(
        set_id, bay_id, "version-1", True,
        "inner1", ("base1",), (),
    )
    committed_nfb = deepcopy(opts["saved_bay"]["nfb_config"])
    layout = update_receiving_bay(
        layout, set_index=0, bay_index=0,
        nfb_config_submitted=True, nfb_config=committed_nfb,
    )
    original_sibling = deepcopy(layout["sets"][0]["bays"][1])
    opts["saved_bay"] = layout["sets"][0]["bays"][0]
    hole = opts["saved_bay"]["nfb_config"]["holes"][0]
    assert hole["manual_x_state"] == "CONFIRMED"
    assert hole["manual_x_mm"] == 0
    assert hole["datum_snapshot"]["w"] == 800

    # Real parsed DXF geometry, not solely invented inventory metadata.
    source = opts["source_path"]
    drawing = ezdxf.new("R2010")
    ms = drawing.modelspace()
    ms.add_lwpolyline(
        ((0, 0), (57, 0), (57, 96), (0, 96)),
        close=True, dxfattribs={"color": 150},
    )
    ms.add_circle((8, 6), 2, dxfattribs={"color": 30})
    drawing.saveas(source)
    inventory = inspect_nfb_dxf_source(source)
    opts["source_inventory"] = inventory
    opts["verified_inner_door"] = replace(
        opts["verified_inner_door"],
        source_sha256=inventory.source_sha256,
    )
    baseline = derive_nfb_partial_export_manifest(**opts)
    assert baseline.authorized_part_ids == ("inner1", "side1")
    assert baseline.actual_export_count == 5
    assert baseline.require_export(("inner1", "side1"), partial=True) == (
        "inner1", "side1",
    )

    changed = update_receiving_bay(
        layout, set_index=0, bay_index=0, width=750,
    )
    changed_bays = changed["sets"][0]["bays"]
    assert changed_bays[1] == original_sibling
    stale = changed_bays[0]["nfb_config"]["holes"][0]
    assert stale["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert stale["manual_x_mm"] == 0
    assert stale["datum_snapshot"]["w"] == 800
    opts["saved_bay"] = changed_bays[0]
    held = derive_nfb_partial_export_manifest(**opts)
    assert held.authorized_part_ids == ("side1",)
    assert held.actual_export_count == 3
    assert held.held_actual_count == 3
    assert "SAVED_NFBCONFIG_DIFFERS_FROM_VERIFIED_CUTTING" in (
        held.unresolved_dependencies
    )
    with pytest.raises(ValueError, match="BLOCKED"):
        held.require_export(("inner1",), partial=True)
    assert held.require_export(("side1",), partial=True) == ("side1",)

    path = write_project(tmp_path / "ac23_old_x_reopen.p6fold", _payload(changed))
    reopened = read_project(path)["snapshot"]["receiving_layout"]["sets"][0]["bays"]
    assert reopened[1] == original_sibling
    reopened_hole = reopened[0]["nfb_config"]["holes"][0]
    assert reopened_hole["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert reopened_hole["manual_x_mm"] == 0
    opts["saved_bay"] = reopened[0]
    assert derive_nfb_partial_export_manifest(**opts).authorized_part_ids == ("side1",)

    # Restoring W800 alone is NOT an operator's new confirmation.
    recovered_width = update_receiving_bay(
        changed, set_index=0, bay_index=0, width=800,
    )
    revived = recovered_width["sets"][0]["bays"][0]
    assert revived["nfb_config"]["holes"][0]["manual_x_state"] == "RECONFIRM_REQUIRED"
    opts["saved_bay"] = revived
    assert derive_nfb_partial_export_manifest(**opts).authorized_part_ids == ("side1",)

def test_swt32_same_original_dxf_brand_pins_colors_real_part_counts_and_sha_hold(
    tmp_path,
):
    """Index observation + raw DXF parser + actual Bay/part manifest agree.

    Unknown/foreign brands are never fake color-zero records. The historical
    source diagnostic cannot certify MFG-2 or create a Receiving middle plate.
    The typed, pre-verified inner CUTTING fixture is independently required.
    """
    from dataclasses import replace

    from ae_engine.receiving_nfb_dxf_source import inspect_nfb_dxf_source
    from tests.test_issue1496_nfb_source_inventory_report import _case
    from tools.nfb_source_audit import build_source_coverage_report

    index, source_root, pins, source = _case(tmp_path)
    original = source.read_bytes()
    observed = build_source_coverage_report(
        index, source_root=source_root, pin_path=pins,
    )
    by_brand = {
        (row["brand"], row["indexed_filename"]): row
        for row in observed["records"]
    }
    trusted = by_brand[("士林", "A.dxf")]
    unknown = by_brand[("東元", "A.dxf")]
    assert trusted["source_sha256"] == sha256(original).hexdigest()
    assert trusted["provenance_pin_matches"] is True
    assert trusted["status"] == "SOURCE_OBSERVED_UNCERTIFIED"
    assert tuple(trusted[f"color_{v}_entities"] for v in (30, 150, 212)) == (
        1, 1, 1,
    )
    assert unknown["status"] == "SOURCE_IDENTITY_MISMATCH_UNKNOWN"
    assert unknown["provenance_pin_matches"] is False
    assert tuple(unknown[f"color_{v}_entities"] for v in (30, 150, 212)) == (
        None, None, None,
    )
    assert all(row["manufacturing_ready"] is False for row in observed["records"])

    parsed = inspect_nfb_dxf_source(source)
    assert parsed.source_sha256 == trusted["source_sha256"]
    counts = dict(parsed.process_aci_entity_counts)
    assert tuple(counts[v] for v in (30, 150, 212)) == (1, 1, 1)

    actual = _prepared(tmp_path)
    actual["scope"] = NfbPhysicalScope(
        "setA", "bayA", "version-1", True, "inner1", ("base1",), (),
    )
    actual["actual_parts"] = tuple(
        part for part in actual["actual_parts"] if part.part_id != "middle1"
    )
    actual["saved_bay"]["nfb_config"]["holes"][0]["model_filename"] = "A.dxf"
    actual["source_path"] = source
    actual["source_inventory"] = parsed
    actual["verified_inner_door"] = replace(
        actual["verified_inner_door"],
        indexed_model_key=("士林", "A.dxf"),
        source_sha256=parsed.source_sha256,
    )
    manifest = derive_nfb_partial_export_manifest(**actual)
    statuses = {row.part_id: row.status for row in manifest.rows}
    assert statuses == {
        "inner1": READY, "base1": BLOCKED, "side1": UNAFFECTED,
    }
    assert manifest.authorized_part_ids == ("inner1", "side1")
    assert manifest.actual_export_count == 5
    assert manifest.held_actual_count == 1
    assert not manifest.whole_ready and manifest.partial_only
    check = manifest.report()
    assert len(check["rows"]) == 3
    assert check["actual_export_count"] == 5
    assert check["held_actual_count"] == 1
    assert check["assembly_status"] == "NOT_VALIDATED_AS_COMPLETE_NFB_ASSEMBLY"
    assert manifest.require_export(("side1",), partial=True) == ("side1",)
    with pytest.raises(ValueError, match="BLOCKED"):
        manifest.require_export(("base1",), partial=True)
    with pytest.raises(ValueError, match="partial only"):
        manifest.require_export(("inner1", "side1"), partial=False)

    # Valid-but-foreign DXF bytes under the formerly indexed source name:
    # index audit must revoke the process counts, and the current manifest
    # must revoke all NFB-dependent output while preserving proven SIDE.
    source.write_bytes((source_root / "東元" / "A.dxf").read_bytes())
    mismatched = build_source_coverage_report(
        index, source_root=source_root, pin_path=pins,
    )
    foreign = next(
        row for row in mismatched["records"]
        if (row["brand"], row["indexed_filename"]) == ("士林", "A.dxf")
    )
    assert foreign["status"] == "SOURCE_IDENTITY_MISMATCH_UNKNOWN"
    assert tuple(foreign[f"color_{v}_entities"] for v in (30, 150, 212)) == (
        None, None, None,
    )
    stale = derive_nfb_partial_export_manifest(**actual)
    assert stale.authorized_part_ids == ("side1",)
    assert stale.actual_export_count == 3
    assert stale.held_actual_count == 3
    assert "ORIGINAL_NFB_DXF_MISSING_OR_SHA_CHANGED" in stale.unresolved_dependencies
    assert stale.require_export(("side1",), partial=True) == ("side1",)
    with pytest.raises(ValueError, match="BLOCKED"):
        stale.require_export(("inner1",), partial=True)


@pytest.mark.parametrize("base_cutting_held", (False, True))
def test_ac41_real_source_in_scope_whole_does_not_claim_completed_pad_ear_assembly(
    tmp_path, base_cutting_held,
):
    """#1504 AC41: committed physical-part export != full cabinet assembly.

    Native NFB source, source-verified inner CUTTING, actual 2+1+3 sheets
    and the original UI consumer share one report. Independently unfinished
    PAD/formed-EAR attachment/full-cabinet manufacture cannot be inferred
    from even a fully READY in-scope NFB manifest.
    """
    from dataclasses import replace
    import ezdxf
    from ae_engine.receiving_nfb_dxf_source import inspect_nfb_dxf_source
    from gui_modules.application.receiving_nfb_manifest_view import (
        nfb_manifest_display_lines,
    )

    options = _prepared(tmp_path)
    options["scope"] = NfbPhysicalScope(
        "setA", "bayA", "version-1", True, "inner1", ("base1",), (),
    )
    options["actual_parts"] = tuple(
        part for part in options["actual_parts"] if part.part_id != "middle1"
    )
    source = tmp_path / "AC41_real_source.dxf"
    dxf = ezdxf.new("R2010")
    model = dxf.modelspace()
    model.add_lwpolyline(
        ((0, 0), (57, 0), (57, 96), (0, 96)),
        close=True, dxfattribs={"color": 150},
    )
    if base_cutting_held:
        model.add_circle((12, 18), 2, dxfattribs={"color": 30})
    dxf.saveas(source)
    inventory = inspect_nfb_dxf_source(source)
    options.update(
        source_path=source,
        source_inventory=inventory,
        verified_inner_door=replace(
            options["verified_inner_door"],
            source_sha256=inventory.source_sha256,
        ),
    )

    manifest = derive_nfb_partial_export_manifest(**options)
    report = manifest.report()
    assert manifest.scope.identity == ("setA", "bayA", "version-1")
    assert manifest.nfb_config_submitted is True
    assert [row.part_id for row in manifest.rows] == ["inner1", "base1", "side1"]
    assert report["assembly_status"] == "NOT_VALIDATED_AS_COMPLETE_NFB_ASSEMBLY"
    assert report["deferred_assembly"] == ["PAD", "EAR_ATTACHMENT"]
    assert report["nfb_config_submitted"] is True
    assert report["actual_export_count"] == (5 if base_cutting_held else 6)
    assert report["held_actual_count"] == (1 if base_cutting_held else 0)
    assert manifest.whole_ready is (not base_cutting_held)
    assert manifest.partial_only is base_cutting_held
    assert manifest.require_export(("side1",), partial=True) == ("side1",)

    if base_cutting_held:
        assert next(row for row in manifest.rows if row.part_id == "base1").status == BLOCKED
        with pytest.raises(ValueError, match="partial only"):
            manifest.require_export(("inner1", "base1", "side1"), partial=False)
        with pytest.raises(ValueError, match="BLOCKED"):
            manifest.require_export(("base1",), partial=True)
        state = "PARTIAL_ONLY"
    else:
        assert manifest.require_export(
            ("inner1", "base1", "side1"), partial=False,
        ) == ("inner1", "base1", "side1")
        state = "WHOLE_READY"

    display = nfb_manifest_display_lines({**report, "status": state})
    assert "整箱製造" in display[0] if not base_cutting_held else (
        "僅部分可出" in display[0]
    )
    assert not any("整套可交付完成" in line for line in display)
    if base_cutting_held:
        assert "不代表整套可交付" in display[-1]

    # Revoked original source cannot borrow an older whole-ready report:
    # re-derived physical readiness, not the UI/status flag, controls DXF.
    source.write_bytes(source.read_bytes() + b"\nSOURCE_SHA_REVOKED")
    stale = derive_nfb_partial_export_manifest(**options)
    assert stale.authorized_part_ids == ("side1",)
    assert stale.actual_export_count == 3
    assert not stale.whole_ready
    assert stale.report()["assembly_status"] == (
        "NOT_VALIDATED_AS_COMPLETE_NFB_ASSEMBLY"
    )
    with pytest.raises(ValueError, match="partial only"):
        stale.require_export(("side1",), partial=False)
