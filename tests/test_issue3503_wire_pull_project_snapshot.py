"""Real .p6fold source replay, including dormant manual edits and fail closed."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from ae_engine import manufacturing_api as api, WirePullBoxSpec
from ae_engine.cabinet_types.wire_pull_holes import HoleAddition, HoleSizeOverride
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project


def test_standard_source_roundtrip_preserves_manual_features_and_member_identity(tmp_path):
    spec = WirePullBoxSpec(637.,1200.,223.,3.,27.,34.,'flat','flat')
    base = api.propose_wire_pull_holes(spec)
    seal = next(m for m in base.members if m.kind == 'seal' and m.part_key == 'box_body')
    x,y = seal.world[:2]
    # Explicit operator edits; not defaults and not synthetic rendering.
    add = HoleAddition('added:seal-A','seal',seal.face_id,(x,y-30.))
    sizes = (HoleSizeOverride(add.group_id,'box_body',diameter=12.),
             HoleSizeOverride(add.group_id,'lid',diameter=15.))
    hole = CircleFeature(4., FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(400.,600.),
                         source_type='MANUAL_TEST')
    mark = replace(hole, layer='MARKING', diameter=2., offset=Vec2(420.,620.))
    manual = (('box_body',(hole,mark)),)
    proposal = api.propose_wire_pull_holes(spec,manual=manual,additions=(add,),
        removed=(seal.group_id,),sizes=sizes,overrides=((add.group_id,(x,y-40.)),))
    assert not proposal.conflicts
    snapshot = api.build_wire_pull_project_snapshot(spec,proposal)
    path = write_project(tmp_path/'test.p6fold', {'schema':PROJECT_SCHEMA,'snapshot':snapshot})
    payload = read_project(path)
    restored, renders = api.restore_wire_pull_project_snapshot(payload['snapshot'])
    assert restored == proposal
    assert payload['snapshot'] == snapshot
    assert payload['final_geometry'] == {}
    assert dict(renders) == dict(api.confirm_wire_pull_holes(spec,proposal,manual=manual))
    physical = api.confirm_wire_pull_hole_topology(spec,restored,manual=restored.manual)
    assert all(part.render_data == dict(renders)[part.part_key] for part in physical.parts)
    assert not physical.manufacturing_verified
    target = tmp_path/'existing.dxf'; target.write_bytes(b'old manufacturing file')
    with pytest.raises(ValueError,match='CABINET_FAMILY_NOT_IMPLEMENTED'):
        api.save_part_render_data_dxf(dict(renders)['lid'],target,overwrite=True)
    assert target.read_bytes() == b'old manufacturing file'
    # Identity mismatches must reject before replacing the existing project.
    original = path.read_bytes()
    corrupt = deepcopy(snapshot)
    corrupt['wire_pull_standard']['identity']['parts'][0][1][0] = 'wrong-face'
    with pytest.raises(ValueError,match='PHYSICAL_IDENTITY_CHANGED'):
        write_project(path,{'schema':PROJECT_SCHEMA,'snapshot':corrupt})
    assert path.read_bytes() == original
    bad_file = tmp_path/'corrupt.p6fold'
    raw = json.loads(original)
    raw['snapshot']['wire_pull_standard']['identity']['holes'][0][3] = 'wrong-face'
    bad_file.write_text(json.dumps(raw),encoding='utf-8')
    with pytest.raises(ValueError,match='PHYSICAL_IDENTITY_CHANGED'):
        read_project(bad_file)


def test_standard_snapshot_never_uses_legacy_family_or_nonzero_preview():
    spec = WirePullBoxSpec(637.,1200.,223.,3.,27.,34.,'flat','flat')
    with pytest.raises(ValueError,match='WIRE_PULL_PROJECT_SOURCE_INVALID'):
        api.restore_wire_pull_project_snapshot({'model':'拉線箱'})
    nonzero = replace(spec,head_clearance_mm=.5)
    with pytest.raises(ValueError,match='INSERT_ZERO_REQUIRED'):
        api.build_wire_pull_project_snapshot(nonzero,api.propose_wire_pull_holes(nonzero))
    with pytest.raises(ValueError,match='SOURCE_CHANGED'):
        api.build_wire_pull_project_snapshot(replace(spec,width=700),api.propose_wire_pull_holes(spec))
