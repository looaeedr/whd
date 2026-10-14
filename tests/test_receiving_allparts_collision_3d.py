# -*- coding: utf-8 -*-
"""Full Receiving collision preview must never equate absent red overlay with safe."""
import pytest

from ae_engine.assembly_all_parts_collision import (
    _frame_terminal_contact,
    audit_all_physical_part_pairs,
)


def test_every_unordered_part_is_covered_and_no_fake_aggregate_box_body():
    a = ((0.,-1.,-1.), (0.,1.,-1.), (0.,0.,1.))
    b = ((-1.,0.,-0.5), (1.,0.,-0.5), (0.,0.,1.))
    c = ((10.,10.,10.), (11.,10.,10.), (10.,11.,10.))
    result = audit_all_physical_part_pairs({
        "left": (a,), "right": (b,), "head": (c,),
        "box_body": (a,b),
    })
    assert result.visible_keys == ("head", "left", "right")
    assert len(result.pairs) == 3
    assert result.evaluated_pair_count == 3
    assert [(p.left,p.right) for p in result.unresolved] == [("left","right")]
    assert result.unresolved[0].segments
    assert any(p.status == "AABB_SEPARATED" for p in result.pairs)
    with pytest.raises(ValueError,match="ASSEMBLY_PHYSICAL_CROSSING_UNVERIFIED"):
        result.require_no_unresolved()


def test_frame_terminal_contact_requires_derived_opposed_ends_not_a_name_whitelist():
    left = "inner_door:upper:left_frame"
    divider = "box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1"
    frame_bounds=((-398.,-350.),(-300.,798.),(84.,107.))
    divider_bounds=((-398.,398.),(-327.,-300.),(70.,174.))
    correct=[(-370.,-300.,85.),(-370.,-300.,105.)]
    assert _frame_terminal_contact(left,divider,frame_bounds,divider_bounds,correct,1e-5)
    assert not _frame_terminal_contact(left,divider,frame_bounds,divider_bounds,
                                       [(-370.,-300.,85.),(-370.,-299.,105.)],1e-5)
    assert not _frame_terminal_contact(left,"box_body:right_side",frame_bounds,
                                       divider_bounds,correct,1e-5)
    assert not _frame_terminal_contact(left,"head",frame_bounds,
                                       ((-398.,398.),(784.,798.),(-174.,174.)),
                                       [(-370.,798.,85.)],1e-5)


def test_missing_selected_mesh_must_fail_closed():
    triangle=((0.,0.,0.),(1.,0.,0.),(0.,1.,0.))
    with pytest.raises(ValueError, match="ASSEMBLY_COLLISION_MISSING_VISIBLE_PARTS"):
        audit_all_physical_part_pairs({"head":(triangle,)},visible_part_keys={"head","frame"})


def test_receiving_actual_all_part_world_includes_head_frames_and_divider():
    from tests.test_issue1050_receiving_mother_plate_marking import _snapshot,_full_receiving_geometry
    from phase6_manufacturing_geometry import (
        _phase6_resolve_family_divider_reliefs,_phase6_build_joint_world_geometry,
    )
    s=_snapshot();g=_full_receiving_geometry(s)
    parts,d,_=_phase6_resolve_family_divider_reliefs(
        g.parts,finished_dimensions=(s["w"],s["h"],s["d"]),sheet_thickness=s["t"])
    assert len(d)==1 and not d[0].illegal_penetration
    w=_phase6_build_joint_world_geometry(parts,(s["w"],s["h"],s["d"]),s["t"])
    audit=audit_all_physical_part_pairs(
        w["world_triangles_by_part"],
        certified_relief_diagnostics=tuple(d),
    )
    pairs={(r.left,r.right):r for r in audit.pairs}
    def select(a,b):
        return pairs[tuple(sorted((a,b)))]
    divider="box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1"
    left="inner_door:upper:left_frame"
    right="inner_door:upper:right_frame"
    assert select(left,divider).status == "VERIFIED_TERMINAL_CONTACT"
    assert select("box_body:left_side",divider).status == "VERIFIED_CERTIFIED_RELIEF_CONTACT"
    assert select("box_body:right_side",divider).status == "VERIFIED_CERTIFIED_RELIEF_CONTACT"
    assert select(right,divider).status == "VERIFIED_TERMINAL_CONTACT"
    assert select("head","box_body:left_side").status == "UNRESOLVED_CROSSING"
    assert select("head","box_body:right_side").status == "UNRESOLVED_CROSSING"
    assert select(left,"head").status == "UNRESOLVED_CROSSING"
    assert select(right,"head").status == "UNRESOLVED_CROSSING"
    assert select(left,"box_body:left_side").status == "NO_NONCOPLANAR_CROSSING"
    assert select(right,"box_body:right_side").status == "NO_NONCOPLANAR_CROSSING"
    assert audit.unresolved
    with pytest.raises(ValueError,match="ASSEMBLY_PHYSICAL_CROSSING_UNVERIFIED"):
        audit.require_no_unresolved()
