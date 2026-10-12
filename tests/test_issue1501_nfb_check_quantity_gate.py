# -*- coding: utf-8 -*-
"""#1501 filtered actual CHECK/Q must never count held NFB physical pieces."""
import re

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.manufacturing_equivalence import ManufacturingParameters
from ae_engine.manufacturing_quantity import PhysicalPartDemand
from ae_engine.manufacturing_render_data import (
    PartRenderData,material_polygon_from_final_scene,
)
from ae_engine.sheetmetal_drawing import DrawingScene
from ae_engine.receiving_nfb_export_manifest import (
    NfbPartialExportManifest,NfbManifestRow,
    INNER_DOOR,MIDDLE_PLATE,OTHER,
)
from ae_engine.receiving_nfb_part_readiness import (
    NfbPhysicalScope,READY,BLOCKED,UNAFFECTED,LEGACY,
)
from ae_engine.receiving_nfb_quantity_gate import gate_nfb_quantity_physical_demands


def _render(*,width=200,opening=None):
    scene=DrawingScene()
    scene.add_polyline(((0,0),(width,0),(width,160),(0,160)),
                       layer="CUTTING",closed=True)
    if opening is not None:
        scene.add_circle((opening,80),6,layer="CUTTING")
    return PartRenderData(scene,material_polygon_from_final_scene(scene))


def _scope(version,counts=(1,1,1),*,middle_blocked=True):
    physical=NfbPhysicalScope(
        "set-"+version,"bay-"+version,version,True,
        "inner",middle_plate_part_ids=("middle",),
    )
    def make(part,role,status,count):
        return NfbManifestRow(
            physical.set_id,physical.bay_id,version,part,role,status,
            ("MIDDLE_PLATE_NFB_COLOR150_UNVERIFIED",) if status==BLOCKED else (),
            count,status!=BLOCKED,
        )
    return NfbPartialExportManifest(
        physical,(
            make("inner",INNER_DOOR,READY,counts[0]),
            make("middle",MIDDLE_PLATE,BLOCKED if middle_blocked else READY,counts[1]),
            make("side",OTHER,UNAFFECTED,counts[2]),
        ),
        ("MIDDLE_MFG2_BLOCKED",) if middle_blocked else (),
        True,not middle_blocked,
    )


def _demands():
    rows=[]
    for version,count,hole_x in (("v1",6,30),("v2",4,80)):
        for name,render in (
            ("inner",_render(opening=hole_x)),
            ("middle",_render(width=100,opening=42)),
            ("side",_render(width=90)),
        ):
            rows.append(PhysicalPartDemand(
                version,name,name,count,1,render,
            ))
    return tuple(rows)


def _params(rows):
    return {
        (d.version_id,d.source_part_id):
            ManufacturingParameters("STEEL",2,{"cut":"laser"})
        for d in rows
    }


def test_real_grouping_omits_blocked_mfg2_and_preserves_q10_q6_q4(tmp_path):
    demands=_demands()
    manifests=(_scope("v1"),_scope("v2"))
    gate=gate_nfb_quantity_physical_demands(
        demands,manifests=manifests,partial=True,
    )
    assert gate.partial_only
    assert gate.permitted_total_pieces==20  # 6+4 inner + 6+4 side
    assert gate.held_total_pieces==10       # 6+4 blocked middle
    assert {d.physical_id for d in gate.permitted}=={"inner","side"}
    groups=gate.group_checked(_params(demands))
    # inner differs in X so cannot be accidentally merged, side is identical.
    assert sorted(g.quantity for g in groups)==[4,6,10]
    assert all(all(m.physical_id!="middle" for m in g.members) for g in groups)
    written=api.save_quantity_manufacturing_groups_dxf(groups,tmp_path)
    assert len(written)==3
    actual_q=[]
    for path in written.values():
        dxf=ezdxf.readfile(path)
        labels=[row.plain_text() for row in dxf.modelspace().query("MTEXT")
                if re.fullmatch(r"Q[0-9]+",row.plain_text())]
        assert len(labels)==1
        actual_q.extend(labels)
    assert sorted(actual_q)==["Q10","Q4","Q6"]


def test_full_grouping_with_any_blocked_part_refuses_before_any_dxf(tmp_path):
    demands=_demands()
    with pytest.raises(ValueError,match="partial only"):
        gate_nfb_quantity_physical_demands(
            demands,manifests=(_scope("v1"),_scope("v2")),partial=False,
        )
    assert not list(tmp_path.glob("*.dxf"))


def test_missing_scope_duplicate_physical_owner_and_unknown_part_are_not_omitted():
    rows=_demands()
    with pytest.raises(ValueError,match="missing scoped"):
        gate_nfb_quantity_physical_demands(
            rows,manifests=(_scope("v1"),),partial=True,
        )
    with pytest.raises(ValueError,match="ambiguous"):
        gate_nfb_quantity_physical_demands(
            rows,manifests=(_scope("v1"),_scope("v1")),partial=True,
        )
    with pytest.raises(ValueError,match="duplicate physical"):
        gate_nfb_quantity_physical_demands(
            rows+(rows[0],),manifests=(_scope("v1"),_scope("v2")),partial=True,
        )
    wrong=PhysicalPartDemand("v1","unlisted","unlisted",6,1,_render())
    with pytest.raises(ValueError,match="missing scoped"):
        gate_nfb_quantity_physical_demands(
            rows+(wrong,),manifests=(_scope("v1"),_scope("v2")),partial=True,
        )


def test_quantity_uses_actual_per_box_piece_count_and_never_theoretical_multiplier():
    rows=_demands()
    item=rows[0]
    from dataclasses import replace
    modified=replace(item,per_box_count=2)
    with pytest.raises(ValueError,match="count mismatch"):
        gate_nfb_quantity_physical_demands(
            (modified,),manifests=(_scope("v1"),),partial=True,
        )
    allowed=gate_nfb_quantity_physical_demands(
        (modified,),manifests=(_scope("v1",counts=(2,1,1)),),partial=True,
    )
    assert allowed.permitted_total_pieces==12
    assert allowed.group_checked(_params((modified,)))[0].quantity==12


def test_no_part_or_nonboolean_partial_flag_fails_closed():
    rows=(x for x in _demands() if x.physical_id=="middle")
    with pytest.raises(ValueError,match="no authorized"):
        gate_nfb_quantity_physical_demands(
            rows,manifests=(_scope("v1"),_scope("v2")),partial=True,
        )
    with pytest.raises(TypeError,match="boolean"):
        gate_nfb_quantity_physical_demands(
            _demands(),manifests=(_scope("v1"),_scope("v2")),partial=1,
        )


def test_inconsistent_manifest_decisions_cannot_enter_check_grouping():
    from dataclasses import replace
    good=_scope("v1")
    ready,middle,side=good.rows
    for altered in (
        replace(middle,may_export=True),
        replace(ready,may_export=False),
        replace(middle,status=READY,reasons=(),may_export=False),
    ):
        bad=replace(good,rows=tuple(
            altered if row.part_id==altered.part_id else row
            for row in good.rows
        ))
        with pytest.raises(ValueError,match="export decision conflicts"):
            gate_nfb_quantity_physical_demands(
                (next(x for x in _demands() if x.version_id=="v1" and
                      x.physical_id==altered.part_id),),
                manifests=(bad,),partial=True,
            )


def test_cross_bay_stale_manifest_identity_and_duplicate_scope_fail_closed():
    from dataclasses import replace
    good=_scope("v1")
    changed=replace(good.rows[0],bay_id="different-bay")
    stale=replace(good,rows=(changed,*good.rows[1:]))
    with pytest.raises(ValueError,match="row Set/Bay/version"):
        gate_nfb_quantity_physical_demands(
            (next(x for x in _demands() if x.version_id=="v1"
                  and x.physical_id=="inner"),),
            manifests=(stale,),partial=True,
        )
    with pytest.raises(ValueError,match="duplicate Set/Bay/version scope"):
        gate_nfb_quantity_physical_demands(
            (next(x for x in _demands() if x.version_id=="v1"
                  and x.physical_id=="inner"),),
            manifests=(good,replace(good,rows=(good.rows[-1],))),
            partial=True,
        )


def test_manifest_submission_readiness_and_count_claims_are_verified():
    from dataclasses import replace
    good=_scope("v1")
    inner=next(x for x in _demands() if x.version_id=="v1" and
               x.physical_id=="inner")
    cases=(
        (replace(good,nfb_config_submitted=False),"submitted fact"),
        (replace(good,whole_ready=True),"whole readiness"),
        (replace(good,rows=(replace(good.rows[0],actual_count=0),*good.rows[1:])),
         "physical count invalid"),
        (replace(good,rows=(replace(good.rows[1],reasons=()),good.rows[0],
                            good.rows[2])),"blocked row missing diagnostic"),
        (replace(good,rows=(replace(good.rows[0],status=LEGACY),*good.rows[1:])),
         "status conflicts"),
    )
    for altered,expected in cases:
        with pytest.raises(ValueError,match=expected):
            gate_nfb_quantity_physical_demands(
                (inner,),manifests=(altered,),partial=True,
            )


def test_manifest_integrity_failure_writes_no_dxf_even_with_valid_count(tmp_path):
    from dataclasses import replace
    good=_scope("v1")
    blocked=good.rows[1]
    forged=replace(good,rows=(good.rows[0],
                   replace(blocked,may_export=True),good.rows[2]))
    demands=tuple(x for x in _demands() if x.version_id=="v1")
    with pytest.raises(ValueError,match="export decision conflicts"):
        gate=gate_nfb_quantity_physical_demands(
            demands,manifests=(forged,),partial=True,
        )
        groups=gate.group_checked(_params(demands))
        api.save_quantity_manufacturing_groups_dxf(groups,tmp_path)
    assert list(tmp_path.glob("*.dxf"))==[]
