"""Bounded first-type saved-source admission for the existing atomic DXF sink.

No caller-supplied render, qualification flag or legacy PartSpec is accepted.
The project file is the operator source; no saved derived scene is authority.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
from math import fsum, isclose, isfinite
from pathlib import Path

from ..assembly_geometry import diagnose_world_mesh_triangle_edge_incidence
from ..assembly_geometry_primitives import triangle_bounds
from ..manufacturing_render_data import material_polygon_from_final_scene, fold_guides_from_final_scene
from ..operator_project_persistence import project_operator_project_for_read, PROJECT_SCHEMA_V1
from ..project_feature_codec import _decode
from ..operator_manual_marking import verify_manual_marking_output
from ..sheetmetal_drawing import CirclePrimitive, PolylinePrimitive
from shapely.geometry import Polygon
from .wire_pull_project import restore_wire_pull_project_snapshot, _source_snapshot
from .wire_pull_holes import confirm_topology
from .wire_pull_topology import PART_KEYS, GAP_MM, TOL, resolve


@dataclass(frozen=True)
class WirePullSavedExportSource:
    """Readback identity only; not an export authorization or a render receipt."""
    source_sha256: str
    part_keys: tuple[str, ...]


def _volume(triangles):
    return fsum(a[0]*(b[1]*c[2]-b[2]*c[1]) + a[1]*(b[2]*c[0]-b[0]*c[2])
                + a[2]*(b[0]*c[1]-b[1]*c[0]) for a,b,c in triangles)/6.


def _close(actual, expected):
    return isclose(actual, expected, rel_tol=0., abs_tol=TOL)


def _read(path, expected=None):
    if path.suffix.lower() != '.p6fold':
        raise ValueError('WIRE_PULL_SAVED_PROJECT_REQUIRED')
    raw = path.read_bytes()
    digest = sha256(raw).hexdigest()
    if expected is not None and digest != expected:
        raise ValueError('WIRE_PULL_SAVED_SOURCE_CHANGED')
    payload = _decode(json.loads(raw.decode('utf-8')))
    if not isinstance(payload, dict) or payload.get('schema') != PROJECT_SCHEMA_V1:
        raise ValueError('WIRE_PULL_SAVED_PROJECT_REQUIRED')
    # Validate through the same persisted source authority as Main Open.
    payload = project_operator_project_for_read(payload)
    proposal, renders = restore_wire_pull_project_snapshot(payload['snapshot'])
    return digest, proposal, renders


def inspect(project_path, *, expected_snapshot=None):
    path = Path(project_path).absolute()
    digest, proposal, renders = _read(path)
    if expected_snapshot is not None and expected_snapshot != _source_snapshot(proposal.spec, proposal):
        raise ValueError('WIRE_PULL_SAVED_SOURCE_CHANGED')
    if tuple(key for key, _ in renders) != PART_KEYS:
        raise ValueError('WIRE_PULL_SAVED_PHYSICAL_IDENTITY_CHANGED')
    return WirePullSavedExportSource(digest, PART_KEYS)


def _validate_process_shapes(render, key):
    # P1 permits closed individual cutting contours only. The common material
    # parser can repair/merge legacy linework; that must not hide duplicate,
    # nested or open manual cuts in this new operation.
    cuts = [p for p in render.scene.primitives if p.layer == 'CUTTING']
    for p in cuts:
        if isinstance(p, CirclePrimitive):
            valid = isfinite(p.radius) and p.radius > 0
        elif isinstance(p, PolylinePrimitive):
            polygon = Polygon([(v.x,v.y) for v in p.points])
            valid = p.closed and polygon.is_valid and polygon.area > 0
        else:
            valid = False
        if not valid:
            raise ValueError('WIRE_PULL_SAVED_CUTTING_CONTOUR_UNSUPPORTED: '+key)
    if (sum(getattr(p,'semantic_id',None)=='OUTER_BOUNDARY' for p in cuts)!=1
            or len(cuts)!=len(render.material.interiors)+1):
        raise ValueError('WIRE_PULL_SAVED_CUTTING_CONTOUR_CONFLICT: '+key)
    # Shared reopen currently compares MARKING polylines/circles, not generic
    # line ink or blind-hole geometry. Do not manufacture unproven operations.
    for p in render.scene.primitives:
        if p.layer=='BLIND_HOLE' or (p.layer=='MARKING' and not isinstance(p,(PolylinePrimitive,CirclePrimitive))):
            raise ValueError('WIRE_PULL_SAVED_PROCESS_UNSUPPORTED: '+key)


def _validate_physical(proposal, renders):
    spec = proposal.spec
    if (spec.model_name != '拉線箱' or spec.head_form != 'flat' or spec.tail_form != 'flat'
            or spec.head_clearance_mm != 0 or spec.tail_clearance_mm != 0):
        raise ValueError('WIRE_PULL_SAVED_STANDARD_SCOPE_REQUIRED')
    # Existing Family topology + confirmed holes are the single geometry owner.
    bare = resolve(spec)
    physical = confirm_topology(spec, proposal, manual=proposal.manual)
    if (tuple(p.part_key for p in physical.parts) != PART_KEYS
            or tuple(key for key,_ in renders) != PART_KEYS
            or physical.joint_graph != bare.joint_graph
            or any(j.clearance_policy != 'ZERO' or j.clearance_intent != 'ZERO' or j.solver_constraints
                   for j in physical.joints)):
        raise ValueError('WIRE_PULL_SAVED_PHYSICAL_IDENTITY_CHANGED')
    bounds = triangle_bounds(tuple(tri for part in physical.parts for tri in part.world_triangles))
    if not all(_close(hi-lo,size) for (lo,hi),size in zip(bounds,(spec.width,spec.height,spec.depth))):
        raise ValueError('WIRE_PULL_SAVED_OUTSIDE_MISMATCH')
    body, head, tail, lid = physical.parts
    b,l = triangle_bounds(body.world_triangles),triangle_bounds(lid.world_triangles)
    t=spec.thickness
    if (not all(_close(gap,GAP_MM) for axis in (0,1) for gap in
                (l[axis][0]-b[axis][0],b[axis][1]-l[axis][1]))
            or not _close(l[2][0],b[2][1]) or not _close(l[2][1]-l[2][0],t)):
        raise ValueError('WIRE_PULL_SAVED_LID_CONTACT_MISMATCH')
    faces={f.face_id:f for f in body.mounting_faces}
    for cap,side in ((head,1),(tail,0)):
        cb=triangle_bounds(cap.world_triangles)
        values=(cb[0][0],cb[0][1],cb[2][0],cb[2][1],cb[1][side],cb[1][1]-cb[1][0])
        expected=(faces['left'].world_origin[0]+t,faces['right'].world_origin[0]-t,
                  faces['rear'].world_origin[2]+t,l[2][0]-t,b[1][side],t)
        if not all(_close(a,e) for a,e in zip(values,expected)):
            raise ValueError('WIRE_PULL_SAVED_INSERT_CONTACT_MISMATCH')
    for part,(key,render) in zip(physical.parts,renders):
        original=bare.part(key)
        material=render.material
        if (part.render_data != render or render.metadata.get('stable_id') != key
                or render.unfolded_topology != original.render_data.unfolded_topology
                or render.unfolded_topology.source != 'WIRE_PULL_EXPLICIT_TOPOLOGY'
                or render.fold_guides != original.render_data.fold_guides
                or render.fold_guides != fold_guides_from_final_scene(render.scene)
                or len(render.fold_guides) != (4 if key=='box_body' else 0)
                or not material.is_valid or material.is_empty
                or not material.equals(material_polygon_from_final_scene(render.scene))
                or not original.render_data.material.covers(material)
                or not material.exterior.equals(original.render_data.material.exterior)
                or any(p.layer not in ('CUTTING','BEND','MARKING','BLIND_HOLE') for p in render.scene.primitives)
                or part.mounting_faces != original.mounting_faces
                or not diagnose_world_mesh_triangle_edge_incidence(part.world_triangles).edges_manifold_closed):
            raise ValueError('WIRE_PULL_SAVED_RENDER_SOURCE_CHANGED: '+key)
        _validate_process_shapes(render,key)
        # Thickness/removed material readback: no invented bend allowance.
        # For the folded body use its unchanged thick baseline (hinge miters).
        volume=_volume(part.world_triangles)
        expected=_volume(original.world_triangles)-(original.render_data.material.area-material.area)*t
        if volume <= 0 or not isclose(volume,expected,rel_tol=1e-10,abs_tol=TOL):
            raise ValueError('WIRE_PULL_SAVED_THICK_MATERIAL_MISMATCH: '+key)
        verify_manual_marking_output(render)  # preserve existing V1 family gate
    return tuple((key,key+'.dxf',render) for key,render in renders)


def _row_signature(rows):
    return tuple((key,name,tuple(render.scene.primitives),render.material.wkb,
                  render.fold_guides,render.unfolded_topology,repr(render.metadata))
                 for key,name,render in rows)


@dataclass(frozen=True, init=False)
class _SavedProjectRows:
    """Private, transaction-local source check, never a reusable qualification."""
    path: Path
    digest: str
    rows: tuple
    signature: tuple
    operator_guard: object

    def __init__(self, project_path, expected_source_sha256, operator_guard=None):
        if operator_guard is not None and not callable(operator_guard):
            raise TypeError('WHD_PRECOMMIT_SOURCE_GUARD_INVALID')
        if (not isinstance(expected_source_sha256,str) or len(expected_source_sha256)!=64
                or any(c not in '0123456789abcdef' for c in expected_source_sha256)):
            raise ValueError('WIRE_PULL_SAVED_SOURCE_FINGERPRINT_REQUIRED')
        path=Path(project_path).absolute()
        digest, proposal, renders = _read(path,expected_source_sha256)
        rows=_validate_physical(proposal,renders)
        object.__setattr__(self,'path',path)
        object.__setattr__(self,'digest',digest)
        object.__setattr__(self,'rows',rows)
        object.__setattr__(self,'signature',_row_signature(rows))
        object.__setattr__(self,'operator_guard',operator_guard)
        self.assert_current()

    def assert_rows(self, rows):
        if (tuple(key for key,_,_ in rows)!=PART_KEYS or _row_signature(rows)!=self.signature
                or any(a[2] is not b[2] for a,b in zip(rows,self.rows))):
            raise ValueError('WIRE_PULL_SAVED_EXPORT_ROWS_CHANGED')
        self.assert_current()

    def assert_current(self):
        if self.operator_guard is not None:
            self.operator_guard()
        if sha256(self.path.read_bytes()).hexdigest()!=self.digest:
            raise ValueError('WIRE_PULL_SAVED_SOURCE_CHANGED')
        if _row_signature(self.rows)!=self.signature:
            raise ValueError('WIRE_PULL_SAVED_EXPORT_ROWS_CHANGED')


def save(project_path, output_dir, *, expected_source_sha256, overwrite=False, pre_commit_guard=None):
    from .. import manufacturing_export
    from ..dxf_serialization import save_scene_dxf
    manufacturing_export.require_dxf_overwrite_boolean(overwrite)
    source=_SavedProjectRows(project_path,expected_source_sha256,pre_commit_guard)
    # Reuse the original stage, writer, independent reopen and rollback. No
    # generic caller render is ever relabeled as manufacturing_verified.
    return manufacturing_export._save_resolved_rows_atomic(
        source.rows,output_dir,overwrite=overwrite,verify_all_staged=True,
        save_part_render_data_dxf=lambda render,target,*,overwrite:
            manufacturing_export.save_part_render_data_dxf(render.scene,target,
                serializer=save_scene_dxf,overwrite=overwrite),
        pre_commit_guard=source.assert_current,guard_during_atomic_move=True,
        _wire_pull_saved_source=source,
    )
