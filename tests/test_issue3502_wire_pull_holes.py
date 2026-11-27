from dataclasses import replace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import WirePullBoxSpec
from ae_engine.cabinet_types.wire_pull_holes import HoleDefaults, HoleOptions
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.sheetmetal_drawing import CirclePrimitive


def source(w=637.,h=1200.,left=27.):
    return WirePullBoxSpec(w,h,223.,3.,left,34.,"flat","flat")


def anchors(d=HoleDefaults()):
    return HoleOptions(d,fixed=False,seal=False)


def points(plan,kind):
    return {m.group_id:m.world[:2] for m in plan.members if m.kind==kind and m.part_key=="box_body"}


@pytest.mark.parametrize("w,count,edge",[(999,4,100),(1000,4,100),(1001,4,150),
                                        (1799,4,150),(1800,4,150),(1801,6,150)])
def test_rear_threshold_uses_actual_outside_not_flat(w,count,edge):
    spec=source(w)
    proposal=api.propose_wire_pull_holes(spec,anchors())
    assert not proposal.conflicts
    expected={(x,y) for x in (-w/2+edge,w/2-edge) for y in (-450.,450.)}
    if count==6: expected.update({(0.,-450.),(0.,450.)})
    got={(round(x,6),round(y,6)) for x,y in points(proposal,"anchor").values()}
    assert got==expected
    assert (0.,0.) not in got
    assert len(proposal.members)==count
    result=dict(api.confirm_wire_pull_holes(spec,proposal))
    circles=[p for p in result["box_body"].scene.primitives if isinstance(p,CirclePrimitive) and p.layer=="CUTTING"]
    assert len(circles)==count and all(p.radius==8. for p in circles)


def test_double_threshold_and_no_center():
    p=api.propose_wire_pull_holes(source(1801.,1900.),anchors())
    assert not p.conflicts and len(p.members)==8
    assert (0.,0.) not in points(p,"anchor").values()


@pytest.mark.parametrize("field,value",[("fixed_pitch",350.),("seal_offset",120.),("anchor_break",900.),
    ("anchor_near",125.),("anchor_far",175.),("anchor_extra",900.)])
def test_independent_defaults(field,value):
    # W1000 and H1200 witness both near/far tiers on one non-square cabinet.
    spec=source(1000.)
    base=api.propose_wire_pull_holes(spec)
    edited=api.propose_wire_pull_holes(spec,HoleOptions(replace(HoleDefaults(),**{field:value})))
    affected="fixed" if field=="fixed_pitch" else "seal" if field=="seal_offset" else "anchor"
    for kind in ("fixed","seal","anchor"):
        assert (points(edited,kind)!=points(base,kind))==(kind==affected)
    assert vars(edited.options.defaults)[field]==value
    assert vars(base.options.defaults)[field]!=value


def test_pairs_have_same_axis_not_same_world_point_and_confirm_cancel():
    spec=source(); proposal=api.propose_wire_pull_holes(spec)
    assert not proposal.conflicts
    for kind in ("fixed","seal"):
        for key in points(proposal,kind):
            a,b=[m for m in proposal.members if m.group_id==key]
            assert a.world[:2]==b.world[:2] and b.world[2]-a.world[2]==pytest.approx(3.)
            assert a.feature.diameter==(5.3 if kind=="fixed" else 13.)
            if kind=="seal": assert b.feature.diameter==16.
            else:
                assert max(p.x for p in b.feature.points)-min(p.x for p in b.feature.points)==pytest.approx(13.)
                assert max(p.y for p in b.feature.points)-min(p.y for p in b.feature.points)==pytest.approx(9.)
    old=dict(api.confirm_wire_pull_holes(spec,proposal))
    key=next(iter(points(proposal,"seal"))); x,y=points(proposal,"seal")[key]
    moved=api.propose_wire_pull_holes(spec,overrides=((key,(x,y-20.)),))
    assert not moved.conflicts
    assert all(m.world[:2]==(x,y-20.) for m in moved.members if m.group_id==key)
    # Cancel is dropping the candidate; original immutable source is unchanged.
    assert dict(api.confirm_wire_pull_holes(spec,proposal))["box_body"].material.equals(old["box_body"].material)
    with pytest.raises(ValueError,match="SOURCE_CHANGED"):
        api.confirm_wire_pull_holes(replace(spec,width=spec.width+1),proposal)
    disabled=api.propose_wire_pull_holes(spec,HoleOptions(seal=False))
    assert not any(m.kind=="seal" for m in disabled.members)
    assert points(disabled,"fixed")==points(proposal,"fixed")
    assert points(disabled,"anchor")==points(proposal,"anchor")


def test_insufficient_support_and_manual_cutting_marking_protected():
    narrow=api.propose_wire_pull_holes(source(left=4.))
    assert any("FACE_MATERIAL_INSUFFICIENT" in c for c in narrow.conflicts)
    with pytest.raises(ValueError,match="HOLE_CONFLICT"):
        api.confirm_wire_pull_holes(narrow.spec,narrow)
    spec=source(); base=api.propose_wire_pull_holes(spec,anchors())
    first=base.members[0].feature
    hole=replace(first,diameter=4.,source_type="MANUAL_TEST",source_params=())
    marking=replace(hole,layer="MARKING",diameter=2.)
    for f in (hole,marking):
        manual=(("box_body",(f,)),)
        bad=api.propose_wire_pull_holes(spec,anchors(),manual=manual)
        assert bad.conflicts
        with pytest.raises(ValueError,match="HOLE_CONFLICT"):
            api.confirm_wire_pull_holes(spec,bad,manual=manual)
        # Turning off anchors must leave the original feature and BEND intact.
        off=api.propose_wire_pull_holes(spec,HoleOptions(fixed=False,seal=False,anchor=False),manual=manual)
        render=dict(api.confirm_wire_pull_holes(spec,off,manual=manual))["box_body"]
        assert any(isinstance(p,CirclePrimitive) and p.layer==f.layer and p.radius==f.diameter/2 for p in render.scene.primitives)
        original=api.resolve_standard_cabinet_topology(spec).part("box_body").render_data
        assert [p for p in render.scene.primitives if p.layer=="BEND"]==[p for p in original.scene.primitives if p.layer=="BEND"]


@pytest.mark.parametrize("field",tuple(vars(HoleDefaults())))
def test_invalid_defaults_fail_closed(field):
    with pytest.raises(ValueError,match="INVALID_DEFAULT"):
        api.propose_wire_pull_holes(source(),HoleOptions(replace(HoleDefaults(),**{field:float("nan")})))


def test_seal_conflict_returns_validated_same_face_alternatives_and_explicit_selection():
    spec=source(); original=api.propose_wire_pull_holes(spec)
    seal=next(m for m in original.members if m.kind=="seal" and m.part_key=="box_body")
    fixed=next(m for m in original.members if m.kind=="fixed" and m.part_key=="box_body" and m.face_id==seal.face_id)
    # Existing mark near the conflicting pair must never be overwritten by a
    # candidate. This is an existing generic MARKING Feature, not V1 admission.
    mark=CircleFeature(2.,FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                       Vec2(fixed.feature.offset.x,fixed.feature.offset.y+20.),
                       layer="MARKING",source_type="MANUAL_TEST")
    manual=(("box_body",(mark,)),)
    bad=api.propose_wire_pull_holes(spec,manual=manual,overrides=((seal.group_id,fixed.world[:2]),))
    assert bad.conflicts and bad.alternatives
    assert points(bad,"seal")[seal.group_id]==fixed.world[:2]
    with pytest.raises(ValueError,match="HOLE_CONFLICT"):
        api.confirm_wire_pull_holes(spec,bad,manual=manual)
    for alt in bad.alternatives:
        assert alt.group_id==seal.group_id
        chosen=api.choose_wire_pull_hole_alternative(spec,bad,alt,manual=manual)
        pair=[m for m in chosen.members if m.group_id==seal.group_id]
        assert not chosen.conflicts and len(pair)==2
        assert pair[0].face_id==seal.face_id
        assert pair[0].world[:2]==pair[1].world[:2]==alt.xy
        assert pair[0].world[2]!=pair[1].world[2]
        assert points(chosen,"fixed")==points(original,"fixed")
        assert points(chosen,"anchor")==points(original,"anchor")
        assert chosen.manual==manual
    chosen=api.choose_wire_pull_hole_alternative(spec,bad,bad.alternatives[0],manual=manual)
    body=dict(api.confirm_wire_pull_holes(spec,chosen,manual=manual))["box_body"]
    assert any(isinstance(p,CirclePrimitive) and p.layer=="MARKING" and p.radius==1.
               and p.center==mark.offset for p in body.scene.primitives)
    # Selecting is not a mutation; stale or forged selection is rejected.
    alt=bad.alternatives[0]
    with pytest.raises(ValueError,match="SOURCE_CHANGED"):
        api.choose_wire_pull_hole_alternative(spec,bad,replace(alt,xy=(0.,0.)),manual=manual)
    assert points(bad,"seal")[seal.group_id]==fixed.world[:2]
    assert points(original,"seal")[seal.group_id]==seal.world[:2]


def test_add_remove_resize_pair_and_cancel_keep_other_features_and_identity():
    from ae_engine.cabinet_types.wire_pull_holes import HoleAddition, HoleSizeOverride
    spec=source(); base=api.propose_wire_pull_holes(spec)
    old=next(m for m in base.members if m.kind=="seal" and m.part_key=="box_body")
    x,y=old.world[:2]
    # Replace a seal group explicitly, keep its original face, change both
    # diameters independently without altering the six global defaults.
    add=HoleAddition("added:seal-A","seal",old.face_id,(x,y-30.))
    sizes=(HoleSizeOverride(add.group_id,"box_body",diameter=12.),
           HoleSizeOverride(add.group_id,"lid",diameter=15.))
    proposed=api.propose_wire_pull_holes(spec,base.options,additions=(add,),removed=(old.group_id,),sizes=sizes)
    assert not proposed.conflicts
    assert not any(m.group_id==old.group_id for m in proposed.members)
    pair=[m for m in proposed.members if m.group_id==add.group_id]
    assert len(pair)==2 and pair[0].world[:2]==pair[1].world[:2]==add.xy
    assert [m.feature.diameter for m in pair]==[12.,15.]
    assert pair[0].face_id==old.face_id
    assert proposed.options.defaults==base.options.defaults
    assert points(proposed,"fixed")==points(base,"fixed")
    assert points(proposed,"anchor")==points(base,"anchor")
    moved=api.propose_wire_pull_holes(spec,base.options,additions=(add,),removed=(old.group_id,),sizes=sizes,
                                     overrides=((add.group_id,(x,y-40.)),))
    assert not moved.conflicts
    assert all(m.world[:2]==(x,y-40.) for m in moved.members if m.group_id==add.group_id)
    # Cancel means retaining the old immutable source, not removing any half-pair.
    assert len([m for m in base.members if m.group_id==old.group_id])==2
    assert not any(m.group_id==add.group_id for m in base.members)
    assert api.propose_wire_pull_holes(spec)==base
    with pytest.raises(ValueError,match="ADDITION_FACE_UNSUPPORTED"):
        api.propose_wire_pull_holes(spec,additions=(replace(add,face_id="rear"),))
    stale=api.propose_wire_pull_holes(spec,removed=("missing",))
    assert "WIRE_PULL_HOLE_OVERRIDE_SOURCE_CHANGED" in stale.conflicts


def test_fixed_add_remove_preserves_alternation_and_pitch():
    from ae_engine.cabinet_types.wire_pull_holes import HoleAddition
    spec=source(); options=HoleOptions(seal=False,anchor=False)
    original=api.propose_wire_pull_holes(spec,options)
    rails=[m for m in original.members if m.kind=="fixed" and m.part_key=="box_body"]
    additions=[]
    for i,face in enumerate(("front_left_return","front_right_return")):
        rows=sorted((m for m in rails if m.face_id==face),key=lambda m:m.world[1])
        a,b=rows[:2]
        additions.append(HoleAddition(f"added:fixed-{i}","fixed",face,(a.world[0],(a.world[1]+b.world[1])/2)))
    odd=api.propose_wire_pull_holes(spec,options,additions=tuple(additions[:1]))
    assert "WIRE_PULL_FIXED_SLOT_ALTERNATION_CONFLICT" in odd.conflicts
    even=api.propose_wire_pull_holes(spec,options,additions=tuple(additions))
    assert not even.conflicts
    assert len(even.members)==len(original.members)+4
    deleted=api.propose_wire_pull_holes(spec,options,additions=tuple(additions),removed=tuple(a.group_id for a in additions))
    assert not deleted.conflicts and deleted.members==original.members


def _signed_volume(mesh):
    def cross(a,b):
        return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
    return sum(sum(x*y for x,y in zip(a,cross(b,c))) for a,b,c in mesh)/6.


@pytest.mark.parametrize("t",[1.5,3.])
def test_confirmed_holes_are_open_on_both_actual_skins_and_remove_exact_volume(t):
    from ae_engine.assembly_geometry import diagnose_world_mesh_triangle_edge_incidence
    from shapely.geometry import Point, Polygon
    from shapely.ops import unary_union
    spec=replace(source(),thickness=t)
    bare=api.resolve_standard_cabinet_topology(spec)
    proposal=api.propose_wire_pull_holes(spec)
    assert not proposal.conflicts
    result=api.confirm_wire_pull_hole_topology(spec,proposal)
    assert result.outside_bounds==bare.outside_bounds
    assert result.joint_graph==bare.joint_graph
    assert not result.manufacturing_verified
    for part in result.parts:
        original=bare.part(part.part_key)
        assert part.mounting_faces==original.mounting_faces
        assert part.render_data.fold_guides==original.render_data.fold_guides
        assert diagnose_world_mesh_triangle_edge_incidence(part.world_triangles).edges_manifold_closed
        area=original.render_data.material.area-part.render_data.material.area
        assert _signed_volume(original.world_triangles)-_signed_volume(part.world_triangles)==pytest.approx(area*t,abs=1e-4)
        assert _signed_volume(part.world_triangles)>0
        if part.part_key in ("head","tail"):
            assert part.world_triangles==original.world_triangles
    # Inspect actual installed triangles, not a hole flag, UV or visual marker.
    for m in proposal.members:
        part=result.part(m.part_key)
        face=next(f for f in part.mounting_faces if f.face_id==m.face_id)
        for z in (m.world[2],m.world[2]-face.outward_normal[2]*t):
            triangles=[Polygon([(p[0],p[1]) for p in tri]) for tri in part.world_triangles
                       if all(abs(p[2]-z)<1e-6 for p in tri)]
            skin=unary_union([p for p in triangles if p.area>1e-9])
            center=Point(*m.world[:2])
            assert not skin.covers(center)
            # The hole's centre has a genuine material-free disk, not a tiny crack.
            radius=m.feature.diameter/2 if hasattr(m.feature,"diameter") else 4.5
            assert not skin.intersects(center.buffer(radius*.9))
    # Compatibility 2D result must be exactly the same canonical scene.
    renders=dict(api.confirm_wire_pull_holes(spec,proposal))
    for part in result.parts:
        assert renders[part.part_key].scene.primitives==part.render_data.scene.primitives


def test_manual_hole_crossing_fold_cannot_be_silently_filled_in_3d():
    spec=source(); topology=api.resolve_standard_cabinet_topology(spec)
    bend=topology.part("box_body").render_data.fold_guides[0]
    hole=CircleFeature(4.,FeatureAnchor.ABSOLUTE_FINISHED_FACE,Vec2(bend.position,300.),source_type="MANUAL_TEST")
    manual=(("box_body",(hole,)),)
    p=api.propose_wire_pull_holes(spec,HoleOptions(fixed=False,seal=False,anchor=False),manual=manual)
    with pytest.raises(ValueError,match="CROSSES_FOLD_OR_EDGE"):
        api.confirm_wire_pull_hole_topology(spec,p,manual=manual)


def test_disabled_seal_keeps_manual_edits_dormant_and_reenable_replays():
    from ae_engine.cabinet_types.wire_pull_holes import HoleSizeOverride
    spec=source(); original=api.propose_wire_pull_holes(spec)
    seal=next(m for m in original.members if m.kind=="seal" and m.part_key=="box_body")
    x,y=seal.world[:2]; overrides=((seal.group_id,(x,y-20.)),)
    sizes=(HoleSizeOverride(seal.group_id,"lid",diameter=15.),)
    edited=api.propose_wire_pull_holes(spec,overrides=overrides,sizes=sizes)
    assert not edited.conflicts
    off=api.propose_wire_pull_holes(spec,HoleOptions(seal=False),overrides=overrides,sizes=sizes)
    assert not off.conflicts and not any(m.kind=="seal" for m in off.members)
    assert off.overrides==overrides and off.sizes==sizes
    assert points(off,"fixed")==points(original,"fixed")
    assert points(off,"anchor")==points(original,"anchor")
    again=api.propose_wire_pull_holes(spec,overrides=off.overrides,sizes=off.sizes)
    assert again==edited


def test_confirmed_2d_survives_missing_exact_triangulation_without_3d_fallback(monkeypatch):
    import shapely
    spec=source()
    proposal=api.propose_wire_pull_holes(spec)
    assert not proposal.conflicts
    expected=dict(api.confirm_wire_pull_holes(spec,proposal))
    physical=api.confirm_wire_pull_hole_topology(spec,proposal)
    for part in physical.parts:
        assert expected[part.part_key]==part.render_data
    assert not physical.manufacturing_verified
    monkeypatch.delattr(shapely,"constrained_delaunay_triangles",raising=False)
    actual=dict(api.confirm_wire_pull_holes(spec,proposal))
    assert actual==expected
    assert all(r.metadata["formed_geometry_verified"] is False for r in actual.values())
    with pytest.raises(ValueError,match="WHD_EXACT_MATERIAL_TRIANGULATION_UNAVAILABLE"):
        api.confirm_wire_pull_hole_topology(spec,proposal)
    # A failed 3D request cannot mutate the proposal or 2D readback.
    assert api.propose_wire_pull_holes(spec)==proposal
    assert dict(api.confirm_wire_pull_holes(spec,proposal))==expected


@pytest.mark.parametrize("missing_exact",[False,True])
def test_both_confirmations_reject_the_same_invalid_source(missing_exact,monkeypatch):
    import shapely
    spec=source()
    good=api.propose_wire_pull_holes(spec)
    seal=next(m for m in good.members if m.kind=="seal" and m.part_key=="box_body")
    fixed=next(m for m in good.members if m.kind=="fixed" and m.part_key=="box_body" and m.face_id==seal.face_id)
    bad=api.propose_wire_pull_holes(spec,overrides=((seal.group_id,fixed.world[:2]),))
    assert bad.conflicts
    bend=api.resolve_standard_cabinet_topology(spec).part("box_body").render_data.fold_guides[0]
    hole=CircleFeature(4.,FeatureAnchor.ABSOLUTE_FINISHED_FACE,Vec2(bend.position,300.),source_type="MANUAL_TEST")
    manual=(("box_body",(hole,)),)
    crossing=api.propose_wire_pull_holes(spec,HoleOptions(fixed=False,seal=False,anchor=False),manual=manual)
    if missing_exact:
        monkeypatch.delattr(shapely,"constrained_delaunay_triangles",raising=False)
    for entry in (api.confirm_wire_pull_holes,api.confirm_wire_pull_hole_topology):
        with pytest.raises(ValueError,match="WIRE_PULL_HOLE_CONFLICT"):
            entry(spec,bad)
        with pytest.raises(ValueError,match="WIRE_PULL_HOLE_SOURCE_CHANGED"):
            entry(replace(spec,width=spec.width+1),good)
        with pytest.raises(ValueError,match="WIRE_PULL_HOLE_CROSSES_FOLD_OR_EDGE"):
            entry(spec,crossing,manual=manual)
