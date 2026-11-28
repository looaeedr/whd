"""Standard wire-pull P1 hole candidate. No production admission or GUI math."""
from dataclasses import dataclass, replace
from math import ceil, isfinite

from shapely.geometry import LineString, Point, box

from ..assembly_geometry_primitives import triangle_bounds
from ..physical_sheet_features import with_physical_sheet_features
from ..sheetmetal_feature_core import CircleFeature, FeatureAnchor, ProfileFeature
from ..sheetmetal_feature_surface import _feature_footprint
from ..sheetmetal_geometry import Vec2
from ..sheetmetal_drawing import CirclePrimitive, LinePrimitive, PolylinePrimitive
from .policy import resolve_standard_cabinet_topology as resolve
from .wire_pull_topology import TOL


@dataclass(frozen=True)
class HoleDefaults:
    fixed_pitch: float = 500.
    seal_offset: float = 100.
    anchor_break: float = 1000.
    anchor_near: float = 100.
    anchor_far: float = 150.
    anchor_extra: float = 1800.


@dataclass(frozen=True)
class HoleOptions:
    defaults: HoleDefaults = HoleDefaults()
    fixed: bool = True
    seal: bool = True
    anchor: bool = True
    opposite_diagonal: bool = False


@dataclass(frozen=True)
class HoleMember:
    group_id: str
    kind: str
    part_key: str
    face_id: str
    world: tuple
    feature: object


@dataclass(frozen=True)
class HoleAddition:
    """Operator-owned stable group ID; one record adds the whole pair."""
    group_id: str
    kind: str
    face_id: str
    xy: tuple[float, float]


@dataclass(frozen=True)
class HoleSizeOverride:
    """Explicit member dimensions; defaults remain independent of edits."""
    group_id: str
    part_key: str
    diameter: float | None = None
    slot_width: float | None = None
    slot_length: float | None = None


@dataclass(frozen=True)
class HoleAlternative:
    group_id: str
    xy: tuple[float, float]
    overrides: tuple


@dataclass(frozen=True)
class HoleProposal:
    spec: object
    options: HoleOptions
    overrides: tuple
    manual: tuple
    members: tuple
    conflicts: tuple
    additions: tuple = ()
    removed: tuple = ()
    alternatives: tuple = ()
    sizes: tuple = ()


def member_size(proposal, group_id, part_key):
    """Read the selected physical member's current dimensions, not defaults.

    Profile points are the Engine's unrotated capsule source. This projection
    never changes a Feature, and does not admit any additional hole type.
    """
    matches = [m for m in proposal.members
               if m.group_id == group_id and m.part_key == part_key]
    if len(matches) != 1:
        raise ValueError("WIRE_PULL_HOLE_MEMBER_SOURCE_REQUIRED")
    member = matches[0]
    feature = member.feature
    if isinstance(feature, CircleFeature):
        return HoleSizeOverride(group_id, part_key, diameter=feature.diameter)
    if (isinstance(feature, ProfileFeature) and member.kind == "fixed"
            and member.part_key == "lid"):
        xs = [p.x for p in feature.points]
        ys = [p.y for p in feature.points]
        return HoleSizeOverride(group_id, part_key,
                                slot_width=max(ys)-min(ys), slot_length=max(xs)-min(xs))
    raise ValueError("WIRE_PULL_HOLE_MEMBER_KIND_UNSUPPORTED")


def _positive(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value <= 0:
        raise ValueError("WIRE_PULL_HOLE_INVALID_DEFAULT")
    return float(value)


def _dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def _world(face, u, v):
    u0, v0, _, _ = face.flat_bounds
    return tuple(o+(u-u0)*a+(v-v0)*b for o,a,b in
                 zip(face.world_origin, face.u_direction, face.v_direction))


def _uv(face, world):
    delta = tuple(a-b for a,b in zip(world, face.world_origin))
    return (face.flat_bounds[0]+_dot(delta,face.u_direction),
            face.flat_bounds[1]+_dot(delta,face.v_direction))


def _face(part, key):
    found = [f for f in part.mounting_faces if f.face_id == key]
    if len(found) != 1 or found[0].part_key != part.part_key:
        raise ValueError("WIRE_PULL_HOLE_FACE_SOURCE_REQUIRED:"+key)
    return found[0]


def _face_world_bounds(face):
    u0,v0,u1,v1 = face.flat_bounds
    pts = [_world(face,u,v) for u in (u0,u1) for v in (v0,v1)]
    return tuple((min(p[i] for p in pts),max(p[i] for p in pts)) for i in range(3))


def _rear_bounds(body, rear):
    # Formed exterior skin includes the adjacent corner miter extension;
    # flat UV bounds are NOT the outside width for threshold decisions.
    if rear.outward_normal != (0,0,-1):
        raise ValueError("WIRE_PULL_REAR_DIRECTION_UNSUPPORTED")
    plane = rear.world_origin[2]
    pts = [p for tri in body.world_triangles
           if all(abs(p[2]-plane) <= TOL for p in tri) for p in tri]
    if not pts:
        raise ValueError("WIRE_PULL_REAR_OUTSIDE_SOURCE_REQUIRED")
    return tuple((min(p[i] for p in pts),max(p[i] for p in pts)) for i in (0,1))


def _anchor_points(bounds, d):
    rows=[]
    for lo,hi in bounds:
        span=hi-lo
        inset=d.anchor_near if span <= d.anchor_break+TOL else d.anchor_far
        if hi-inset <= lo+inset+TOL:
            raise ValueError("WIRE_PULL_ANCHOR_MATERIAL_INSUFFICIENT")
        rows.append((lo+inset,hi-inset,(lo+hi)/2,span>d.anchor_extra+TOL))
    x0,x1,xm,extra_x=rows[0]; y0,y1,ym,extra_y=rows[1]
    points=[("bl",x0,y0),("br",x1,y0),("tl",x0,y1),("tr",x1,y1)]
    if extra_x: points.extend((("bottom-mid",xm,y0),("top-mid",xm,y1)))
    if extra_y: points.extend((("left-mid",x0,ym),("right-mid",x1,ym)))
    return points


def _slot(width, length):
    width,length=_positive(width),_positive(length)
    if length<=width:
        raise ValueError("WIRE_PULL_HOLE_SLOT_LENGTH_INVALID")
    a=(length-width)/2
    shape=LineString(((-a,0.),(a,0.))).buffer(width/2,quad_segs=32)
    return tuple(Vec2(x,y) for x,y in shape.exterior.coords[:-1])


def _member(group, kind, part, face, xy, diameter, *, slot_rotation=None):
    # Use the actual face plane and its own UV transform; this P1 has Z-normal
    # front/rear only, and the two paired world points are deliberately distinct.
    if face.outward_normal not in ((0,0,1),(0,0,-1)):
        raise ValueError("WIRE_PULL_HOLE_DIRECTION_UNSUPPORTED")
    p=(xy[0],xy[1],face.world_origin[2]); u,v=_uv(face,p)
    kw=dict(anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,offset=Vec2(u,v),
            layer="CUTTING",source_type="WIRE_PULL_"+kind.upper(),
            source_params=(("group_id",group),("face_id",face.face_id)))
    if slot_rotation is None:
        feature=CircleFeature(diameter=diameter,**kw)
    else:
        # Existing ProfileFeature/FinalScene path for a 9 x 13 capsule.
        feature=ProfileFeature(points=_slot(9.,13.),
                               rotation_deg=slot_rotation,**kw)
    return HoleMember(group,kind,part.part_key,face.face_id,p,feature)


def _protected_ink(render):
    for p in render.scene.primitives:
        if p.layer not in ("MARKING", "BLIND_HOLE"):
            continue
        if isinstance(p,CirclePrimitive):
            disk=Point(p.center.x,p.center.y).buffer(p.radius,quad_segs=32)
            yield disk if p.layer=="BLIND_HOLE" else disk.boundary
        elif isinstance(p,LinePrimitive):
            yield LineString(((p.p1.x,p.p1.y),(p.p2.x,p.p2.y)))
        elif isinstance(p,PolylinePrimitive):
            pts=[(v.x,v.y) for v in p.points]
            if p.closed: pts.append(pts[0])
            yield LineString(pts)
        else:
            raise ValueError("WIRE_PULL_HOLE_PROTECTED_INK_UNSUPPORTED")


# One rear opening on the original body in the first P2 slice. The shared
# ProfileFeature serializer persists the source tag along with the contour.
REAR_OPENING = "WIRE_PULL:box_body:rear:cover_opening"


def _rear_profile(bounds):
    if not isinstance(bounds, (tuple, list)) or len(bounds) != 4:
        raise ValueError("WIRE_PULL_REAR_OPENING_BOUNDS_INVALID")
    x, y, right, top = bounds
    if any(type(n) not in (float, int) or not isfinite(n) for n in bounds) or right <= x or top <= y:
        raise ValueError("WIRE_PULL_REAR_OPENING_BOUNDS_INVALID")
    w, h = right-x, top-y
    return ProfileFeature(tuple(Vec2(u,v) for u,v in ((0,0),(w,0),(w,h),(0,h))),
                          FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(x,y), source_type=REAR_OPENING)


def set_rear_opening(proposal, bounds):
    """Replace the single rear configuration, or selectively cancel with None."""
    confirm(proposal.spec, proposal, manual=proposal.manual)
    manual = dict(proposal.manual)
    retained = tuple(f for f in manual.get("box_body", ()) if f.source_type != REAR_OPENING)
    if bounds is None and retained == manual.get("box_body", ()):
        return proposal
    if bounds is not None:
        retained += (_rear_profile(bounds),)
    if retained:
        manual["box_body"] = retained
    else:
        manual.pop("box_body", None)
    fresh = propose(proposal.spec, proposal.options, manual=manual.items(),
                    overrides=proposal.overrides, additions=proposal.additions,
                    removed=proposal.removed, sizes=proposal.sizes)
    confirm(proposal.spec, fresh, manual=fresh.manual)
    return fresh


def rear_opening_bounds(proposal):
    """Read the saved canonical rear opening bounds from an Engine proposal."""
    confirm(proposal.spec, proposal, manual=proposal.manual)
    openings = tuple(f for f in dict(proposal.manual).get("box_body", ())
                     if f.source_type == REAR_OPENING)
    if not openings:
        return None
    if len(openings) != 1 or not isinstance(openings[0], ProfileFeature):
        raise ValueError("WIRE_PULL_REAR_OPENING_PROFILE_INVALID")
    feature = openings[0]
    if len(feature.points) != 4:
        raise ValueError("WIRE_PULL_REAR_OPENING_PROFILE_INVALID")
    x, y = feature.offset.x, feature.offset.y
    corner = feature.points[2]
    bounds = (x, y, x + corner.x, y + corner.y)
    if feature != _rear_profile(bounds):
        raise ValueError("WIRE_PULL_REAR_OPENING_PROFILE_INVALID")
    return bounds


def propose_with_rear_opening(spec, options=HoleOptions(), *, flat_bounds,
                              manual=(), overrides=(), additions=(), removed=(), sizes=()):
    """Atomically replace or clear the rear opening before validating a proposal."""
    manual_map = dict(manual)
    retained = tuple(feature for feature in manual_map.get("box_body", ())
                     if feature.source_type != REAR_OPENING)
    if flat_bounds is not None:
        retained += (_rear_profile(flat_bounds),)
    if retained:
        manual_map["box_body"] = retained
    else:
        manual_map.pop("box_body", None)
    return propose(spec, options, manual=tuple(manual_map.items()), overrides=overrides,
                   additions=additions, removed=removed, sizes=sizes)


def _check_rear_opening(part, features):
    openings = [f for f in features if f.source_type == REAR_OPENING]
    if not openings:
        return
    if len(openings) != 1 or part.part_key != "box_body":
        raise ValueError("WIRE_PULL_REAR_OPENING_OWNER_INVALID")
    opening = openings[0]
    if not isinstance(opening, ProfileFeature) or len(opening.points) != 4:
        raise ValueError("WIRE_PULL_REAR_OPENING_PROFILE_INVALID")
    x, y = opening.offset.x, opening.offset.y
    corner = opening.points[2]
    bounds = (x,y,x+corner.x,y+corner.y)
    if opening != _rear_profile(bounds):
        raise ValueError("WIRE_PULL_REAR_OPENING_PROFILE_INVALID")
    footprint = box(*bounds)
    rear = box(*_face(part,"rear").flat_bounds)
    prior = with_physical_sheet_features(part.part_key, part.render_data,
                                         tuple(f for f in features if f is not opening))
    from ..operator_manual_marking import _circle_crosses_path
    if (not rear.contains_properly(footprint) or not prior.material.contains_properly(footprint)
            or any(ink.intersects(footprint) for ink in _protected_ink(prior))
            or any(isinstance(p, CirclePrimitive) and p.layer == "MARKING"
                   and _circle_crosses_path(p, footprint.exterior) for p in prior.scene.primitives)):
        raise ValueError("WIRE_PULL_REAR_OPENING_MATERIAL_CONFLICT")


def _build(spec, options, *, manual=(), overrides=(), additions=(), removed=(), sizes=(), topology=None):
    """Pure candidate generation. Manual is ((part_key, tuple(Feature)), ...).

    Overrides are ((group_id, (world_x,world_y)), ...); one override moves
    the whole pair. No scene is changed on proposal/cancel or on conflict.
    """
    if not isinstance(options,HoleOptions) or not isinstance(options.defaults,HoleDefaults):
        raise ValueError("WIRE_PULL_HOLE_OPTIONS_REQUIRED")
    for v in vars(options.defaults).values(): _positive(v)
    if any(type(v) is not bool for v in (options.fixed,options.seal,options.anchor,options.opposite_diagonal)):
        raise ValueError("WIRE_PULL_HOLE_ENABLE_INVALID")
    d=options.defaults
    topology=resolve(spec) if topology is None else topology
    body=topology.part("box_body"); lid=topology.part("lid")
    lid_face=_face(lid,"outer"); rear=_face(body,"rear")
    manual=tuple((key,tuple(features)) for key,features in manual)
    manual_map=dict(manual)
    if len(manual_map)!=len(manual) or set(manual_map)-{p.part_key for p in topology.parts}:
        raise ValueError("WIRE_PULL_HOLE_MANUAL_OWNER_INVALID")
    overrides=tuple((key,tuple(point)) for key,point in overrides)
    moves=dict(overrides)
    if len(moves)!=len(overrides) or any(len(p)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not isfinite(v) for v in p) for p in moves.values()):
        raise ValueError("WIRE_PULL_HOLE_OVERRIDE_INVALID")
    additions=tuple(additions); removed=tuple(removed)
    if any(not isinstance(a,HoleAddition) or not isinstance(a.group_id,str)
           or not a.group_id.startswith("added:") or not a.group_id[6:]
           or a.kind not in ("fixed","seal","anchor") for a in additions):
        raise ValueError("WIRE_PULL_HOLE_ADDITION_INVALID")
    if len({a.group_id for a in additions})!=len(additions):
        raise ValueError("WIRE_PULL_HOLE_ADDITION_DUPLICATE")
    if any(not isinstance(k,str) or not k for k in removed) or len(set(removed))!=len(removed):
        raise ValueError("WIRE_PULL_HOLE_REMOVAL_INVALID")
    removed_ids=set(removed)
    members=[]; conflicts=[]; used=set()
    def xy(group,x,y):
        used.add(group); return moves.get(group,(x,y))
    supports=[]
    for key in ("front_left_return","front_right_return"):
        face=_face(body,key)
        matches=[j for j in topology.joints if j.subject_part=="lid" and j.target_part=="box_body" and j.target_region==key and j.relation.value=="OVERLAY" and j.direction=="+Z"]
        if len(matches)!=1 or face.outward_normal!=(0,0,1):
            raise ValueError("WIRE_PULL_HOLE_SUPPORT_SOURCE_REQUIRED:"+key)
        bounds=_face_world_bounds(face)
        if abs(bounds[2][0]-triangle_bounds(lid.world_triangles)[2][0])>TOL:
            raise ValueError("WIRE_PULL_HOLE_SUPPORT_NOT_CONTACTING:"+key)
        supports.append((face,bounds))
    def pair(group,kind,face,x,y,rotation=None):
        center=xy(group,x,y)
        if group in removed_ids: return
        members.extend((_member(group,kind,body,face,center,5.3 if kind=="fixed" else 13.),
                        _member(group,kind,lid,lid_face,center,16.,slot_rotation=rotation)))
    if options.fixed:
        # Only the two actual continuous support rails exist in this P1.
        # A candidate end setback uses the larger rail half-width, not a
        # guessed factory distance. Pitch applies along each supported rail.
        setback=max((b[0][1]-b[0][0])/2 for _,b in supports)
        low=max(b[1][0] for _,b in supports)+setback
        high=min(b[1][1] for _,b in supports)-setback
        if high<=low: conflicts.append("WIRE_PULL_FIXED_MATERIAL_INSUFFICIENT")
        else:
            n=max(1,ceil((high-low)/d.fixed_pitch))
            if n>10000: raise ValueError("WIRE_PULL_HOLE_COUNT_EXCESSIVE")
            for side,(face,b) in enumerate(supports):
                x=sum(b[0])/2
                for i in range(n+1):
                    label="bottom" if i==0 else "top" if i==n else str(i)
                    order=i if side==0 else 2*n+1-i
                    pair(f"fixed:{face.face_id}:{label}","fixed",face,x,low+(high-low)*i/n,90*(order%2))
    if options.seal:
        for i,(face,b) in enumerate(supports):
            top=(i==0)!=options.opposite_diagonal
            pair(f"seal:{face.face_id}","seal",face,sum(b[0])/2,
                 b[1][1]-d.seal_offset if top else b[1][0]+d.seal_offset)
    if options.anchor:
        for label,x,y in _anchor_points(_rear_bounds(body,rear),d):
            group="anchor:"+label
            center=xy(group,x,y)
            if group not in removed_ids:
                members.append(_member(group,"anchor",body,rear,center,16.))
    # Additional groups are explicit sources, never guessed new support faces.
    for a in additions:
        face=_face(body,a.face_id)
        if (a.kind=="anchor" and face.face_id!="rear") or (a.kind!="anchor" and face not in tuple(f for f,_ in supports)):
            raise ValueError("WIRE_PULL_HOLE_ADDITION_FACE_UNSUPPORTED")
        if not isinstance(a.xy,tuple) or len(a.xy)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not isfinite(v) for v in a.xy):
            raise ValueError("WIRE_PULL_HOLE_ADDITION_POSITION_INVALID")
        used.add(a.group_id)
        if not getattr(options,a.kind) or a.group_id in removed_ids:
            continue
        if a.kind=="anchor":
            members.append(_member(a.group_id,a.kind,body,face,xy(a.group_id,*a.xy),16.))
        else:
            pair(a.group_id,a.kind,face,*a.xy,0 if a.kind=="fixed" else None)
    def dormant_kind(key):
        # Disabling a category hides only its derived members. Retain explicit
        # operator edit sources, so re-enable can replay them. Unrecognized
        # identities or stale active IDs still fail closed.
        parts=key.split(":") if isinstance(key,str) else ()
        if len(parts)==3 and parts[0]=="fixed" and parts[1] in {f.face_id for f,_ in supports}:
            if parts[2] in ("bottom","top") or (parts[2].isdigit() and int(parts[2])>0):
                return "fixed" if not options.fixed else None
        if len(parts)==2 and parts[0]=="seal" and parts[1] in {f.face_id for f,_ in supports}:
            return "seal" if not options.seal else None
        if len(parts)==2 and parts[0]=="anchor" and parts[1] in ("bl","br","tl","tr","bottom-mid","top-mid","left-mid","right-mid"):
            return "anchor" if not options.anchor else None
        return None
    if any(not dormant_kind(k) for k in (set(moves)|removed_ids)-used):
        conflicts.append("WIRE_PULL_HOLE_OVERRIDE_SOURCE_CHANGED")
    # Explicit fixed-group edits may change the cyclic parity. Reassign only
    # the derived slots after add/remove, not on an ordinary position override.
    if any(a.kind=="fixed" for a in additions) or any(k.startswith("fixed:") for k in removed):
        order=[]
        for i,(face,_) in enumerate(supports):
            order.extend(m.group_id for m in sorted((m for m in members if m.kind=="fixed" and m.part_key=="box_body" and m.face_id==face.face_id),key=lambda m:m.world[1],reverse=bool(i)))
        rotations={k:90*(i%2) for i,k in enumerate(order)}
        members=[replace(m,feature=replace(m.feature,rotation_deg=rotations[m.group_id]))
                 if m.kind=="fixed" and m.part_key=="lid" else m for m in members]
    sizes=tuple(sizes)
    if any(not isinstance(e,HoleSizeOverride) for e in sizes):
        raise ValueError("WIRE_PULL_HOLE_SIZE_OVERRIDE_INVALID")
    by_member={(e.group_id,e.part_key):e for e in sizes}
    if len(by_member)!=len(sizes):
        raise ValueError("WIRE_PULL_HOLE_SIZE_OVERRIDE_DUPLICATE")
    found=set()
    for i,m in enumerate(members):
        key=(m.group_id,m.part_key)
        if key not in by_member: continue
        edit=by_member[key]; found.add(key)
        if isinstance(m.feature,CircleFeature):
            if edit.slot_width is not None or edit.slot_length is not None:
                raise ValueError("WIRE_PULL_HOLE_SIZE_OVERRIDE_KIND_MISMATCH")
            feature=replace(m.feature,diameter=_positive(edit.diameter))
        else:
            if edit.diameter is not None:
                raise ValueError("WIRE_PULL_HOLE_SIZE_OVERRIDE_KIND_MISMATCH")
            feature=replace(m.feature,points=_slot(edit.slot_width,edit.slot_length))
        members[i]=replace(m,feature=feature)
    added_kinds={a.group_id:a.kind for a in additions}
    for group,part_key in set(by_member)-found:
        kind=added_kinds.get(group) or dormant_kind(group)
        if kind is None and group in used and group in removed_ids:
            kind=group.split(":")[0]
        if (kind not in ("fixed","seal","anchor") or part_key not in
                (("box_body",) if kind=="anchor" else ("box_body","lid"))
                or (group not in removed_ids and getattr(options,kind))):
            conflicts.append("WIRE_PULL_HOLE_SIZE_OVERRIDE_SOURCE_CHANGED")
    # Canonical existing feature renderer preserves manual CUTTING and MARKING.
    # Validate complete footprints against both the actual face and material.
    occupied={}
    for part in topology.parts:
        _check_rear_opening(part, manual_map.get(part.part_key, ()))
        old=with_physical_sheet_features(part.part_key,part.render_data,manual_map.get(part.part_key,()))
        occupied[part.part_key]=[]
        protected=tuple(_protected_ink(old))
        rows=[m for m in members if m.part_key==part.part_key]
        for m in rows:
            face=_face(part,m.face_id)
            footprint=_feature_footprint(m.feature,0.,0.)
            region=box(*face.flat_bounds)
            if not region.contains(footprint) or region.boundary.intersects(footprint):
                conflicts.append(m.group_id+":"+m.part_key+":FACE_MATERIAL_INSUFFICIENT")
            elif not old.material.contains(footprint) or old.material.boundary.intersects(footprint):
                conflicts.append(m.group_id+":"+m.part_key+":EXISTING_CUTTING_OR_MATERIAL")
            if any(footprint.intersects(ink) for ink in protected):
                conflicts.append(m.group_id+":"+m.part_key+":EXISTING_MARKING_OR_BLIND_HOLE")
            for other,shape in occupied[part.part_key]:
                if footprint.intersects(shape): conflicts.append(m.group_id+":OVERLAP:"+other)
            occupied[part.part_key].append((m.group_id,footprint))
        # Existing shared marking validator sees the entire proposed CUTTING
        # inventory and refuses marks made stale by a new hole.
        if not conflicts:
            try:
                with_physical_sheet_features(part.part_key,part.render_data,
                    (*manual_map.get(part.part_key,()),*(m.feature for m in rows)))
            except ValueError as exc: conflicts.append(part.part_key+":"+str(exc))
    if options.fixed:
        # Keep alternating long axes in the actual order after a user move.
        lid_slots={m.group_id:m.feature.rotation_deg for m in members if m.kind=="fixed" and m.part_key=="lid"}
        cycle=[]
        for i,(face,_) in enumerate(supports):
            row=sorted((m for m in members if m.kind=="fixed" and m.part_key=="box_body" and m.face_id==face.face_id),key=lambda m:m.world[1],reverse=bool(i))
            cycle.extend(lid_slots[m.group_id] for m in row)
        if len(cycle)%2 or (cycle and any(a==b for a,b in zip(cycle,cycle[1:]+cycle[:1]))):
            conflicts.append("WIRE_PULL_FIXED_SLOT_ALTERNATION_CONFLICT")
        for face,_ in supports:
            rows=sorted((m.world[1] for m in members if m.kind=="fixed" and m.part_key=="box_body" and m.face_id==face.face_id))
            if len(rows)<2:
                conflicts.append("WIRE_PULL_FIXED_SUPPORT_COUNT_INSUFFICIENT:"+face.face_id)
            if any(b-a>d.fixed_pitch+TOL for a,b in zip(rows,rows[1:])):
                conflicts.append("WIRE_PULL_FIXED_PITCH_EXCEEDED:"+face.face_id)
    return HoleProposal(spec,options,overrides,manual,tuple(members),tuple(dict.fromkeys(conflicts)),additions,removed,sizes=sizes)



def propose(spec, options=HoleOptions(), *, manual=(), overrides=(), additions=(), removed=(), sizes=()):
    """Return original conflicts plus optional verified, unapplied alternatives.

    Bounded deterministic search: 5..100 mm along the same rail (or the two
    rear axes). No automatic relocation and no promise of a global solution.
    """
    topology=resolve(spec)
    plan=_build(spec,options,manual=manual,overrides=overrides,additions=additions,
                removed=removed,sizes=sizes,topology=topology)
    if not plan.conflicts or any("FACE_MATERIAL_INSUFFICIENT" in c for c in plan.conflicts):
        return plan
    alternatives=[]
    groups={m.group_id:m for m in plan.members if m.part_key=="box_body"}
    moved=dict(plan.overrides)
    # A narrow support cannot be repaired by sliding its holes along the rail.
    relevant=[k for k in groups if any((c.startswith(k+":") or c.endswith(":OVERLAP:"+k))
                  and (":OVERLAP:" in c or ":EXISTING_" in c) for c in plan.conflicts)]
    relevant.sort(key=lambda k:(k not in moved,groups[k].kind!="seal",k))
    for key in relevant[:4]:
        member=groups[key]; x,y=member.world[:2]
        directions=((0,1),(0,-1)) if member.kind!="anchor" else ((0,1),(0,-1),(1,0),(-1,0))
        for distance in (5.,10.,15.,20.,30.,40.,60.,80.,100.):
            for dx,dy in directions:
                point=(x+distance*dx,y+distance*dy)
                trial=dict(moved); trial[key]=point
                candidate=_build(spec,options,manual=plan.manual,overrides=tuple(trial.items()),
                                 additions=plan.additions,removed=plan.removed,sizes=plan.sizes,topology=topology)
                if not candidate.conflicts:
                    alternatives.append(HoleAlternative(key,point,candidate.overrides))
                    if len(alternatives)>=3:
                        return replace(plan,alternatives=tuple(alternatives))
        if alternatives:
            break
    return replace(plan,alternatives=tuple(alternatives))


def choose_alternative(spec, proposal, alternative, *, manual=()):
    """Select a candidate, not commit it. Revalidate against the current source."""
    fresh=propose(spec,proposal.options,manual=manual,overrides=proposal.overrides,
                  additions=proposal.additions,removed=proposal.removed,sizes=proposal.sizes)
    if fresh!=proposal or alternative not in fresh.alternatives:
        raise ValueError("WIRE_PULL_HOLE_SOURCE_CHANGED")
    chosen=propose(spec,proposal.options,manual=manual,overrides=alternative.overrides,
                   additions=proposal.additions,removed=proposal.removed,sizes=proposal.sizes)
    if chosen.conflicts:
        raise ValueError("WIRE_PULL_HOLE_CONFLICT:"+";".join(chosen.conflicts))
    return chosen


def _confirmed_renders(spec, proposal, *, manual=()):
    """One source check and canonical render owner, independent of hole meshing."""
    source=resolve(spec)
    fresh=_build(spec,proposal.options,manual=manual,overrides=proposal.overrides,
                 additions=proposal.additions,removed=proposal.removed,sizes=proposal.sizes,
                 topology=source)
    if fresh!=replace(proposal,alternatives=()):
        raise ValueError("WIRE_PULL_HOLE_SOURCE_CHANGED")
    if fresh.conflicts:
        raise ValueError("WIRE_PULL_HOLE_CONFLICT:"+";".join(fresh.conflicts))
    old=dict(fresh.manual)
    def render_transform(key, render):
        return with_physical_sheet_features(key,render,
                   (*old.get(key,()),*(m.feature for m in fresh.members if m.part_key==key)))
    # Reuse the existing topology owner's material/identity/hinge checks.
    # Use the original physical part's canonical scene, including dual-axis end caps.
    from .wire_pull_topology import _render_with_features
    renders=tuple((part.part_key,_render_with_features(
        part.part_key,part.x_profile,part.y_profile,
        sum(row.length for row in part.y_profile),render_transform,source=part.render_data,
    )[0]) for part in source.parts)
    return source,renders


def confirm_topology(spec, proposal, *, manual=()):
    """Atomic confirmed canonical scene + matching closed physical mesh."""
    source,renders=_confirmed_renders(spec,proposal,manual=manual)
    by_key=dict(renders)
    from .wire_pull_topology import resolve as resolve_physical
    # Consume the already-confirmed renders. The physical resolver retains
    # its own source identity, exact triangulation and closed-shell checks.
    result=resolve_physical(spec,render_transform=lambda key,render:by_key[key])
    if (result.joint_graph!=source.joint_graph or result.manufacturing_verified
            or any(a.mounting_faces!=b.mounting_faces for a,b in zip(result.parts,source.parts))
            or any(abs(a-b)>TOL for ab,bb in zip(result.outside_bounds,source.outside_bounds) for a,b in zip(ab,bb))):
        raise ValueError("WIRE_PULL_HOLE_ASSEMBLY_IDENTITY_CHANGED")
    return result


def confirm(spec, proposal, *, manual=()):
    """Canonical 2D only; no perforated mesh or manufacturing admission."""
    return _confirmed_renders(spec,proposal,manual=manual)[1]
