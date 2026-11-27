"""Source-only standard wire-pull project state, within the existing .p6fold schema.

Persist confirmed operator inputs and stable owner witnesses, never FinalScene
or mesh. All reconstruction uses the existing P1/P2 source owners.
"""
from dataclasses import asdict, fields
from copy import deepcopy

from ..contracts import WirePullBoxSpec
from .policy import canonical_family_name, resolve_standard_cabinet_topology
from .wire_pull_holes import HoleDefaults, HoleOptions, HoleAddition, HoleSizeOverride, propose, confirm

KEY = 'wire_pull_standard'
FAMILY = '拉線箱'


def is_wire_pull_project_snapshot(snapshot):
    return KEY in snapshot or canonical_family_name(snapshot) == FAMILY


def _strict_record(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError('WIRE_PULL_PROJECT_SOURCE_INVALID')
    return value


def _typed(cls, value):
    return cls(**_strict_record(value, (f.name for f in fields(cls))))


def _identity(spec, proposal):
    topology = resolve_standard_cabinet_topology(spec)
    return {
        'parts': [[p.part_key, [f.face_id for f in p.mounting_faces]] for p in topology.parts],
        'holes': [[m.group_id, m.kind, m.part_key, m.face_id] for m in proposal.members],
    }


def _source_snapshot(spec, proposal):
    if canonical_family_name(spec.model_name) != FAMILY or spec.model_name != FAMILY:
        raise ValueError('WIRE_PULL_PROJECT_FAMILY_INVALID')
    # Standard project UI has no nonzero-clearance control. Do not silently
    # turn a legacy explicit preview into a standard job on reload.
    if spec.head_clearance_mm != 0 or spec.tail_clearance_mm != 0:
        raise ValueError('WIRE_PULL_STANDARD_INSERT_ZERO_REQUIRED')
    return {'model': FAMILY, KEY: {
        'version': 1,
        'spec': asdict(spec), 'options': asdict(proposal.options),
        'manual': [[key, list(features)] for key, features in proposal.manual],
        'overrides': [[key, list(point)] for key, point in proposal.overrides],
        'additions': [{**asdict(a), 'xy': list(a.xy)} for a in proposal.additions],
        'removed': list(proposal.removed), 'sizes': [asdict(s) for s in proposal.sizes],
        'identity': _identity(spec, proposal),
    }}


def build_wire_pull_project_snapshot(spec, proposal):
    # Reject stale/conflicting proposals through the original confirmation owner.
    confirm(spec, proposal, manual=proposal.manual)
    return _source_snapshot(spec, proposal)


def restore_wire_pull_project_snapshot(snapshot):
    _strict_record(snapshot, ('model', KEY))
    if snapshot['model'] != FAMILY:
        raise ValueError('WIRE_PULL_PROJECT_FAMILY_INVALID')
    raw = _strict_record(snapshot[KEY], ('version', 'spec', 'options', 'manual',
                                         'overrides', 'additions', 'removed', 'sizes', 'identity'))
    if type(raw['version']) is not int or raw['version'] != 1:
        raise ValueError('WIRE_PULL_PROJECT_VERSION_UNSUPPORTED')
    spec = _typed(WirePullBoxSpec, raw['spec'])
    options = dict(_strict_record(raw['options'], (f.name for f in fields(HoleOptions))))
    options['defaults'] = _typed(HoleDefaults, options['defaults'])
    additions = []
    for record in raw['additions']:
        row = dict(_strict_record(record, (f.name for f in fields(HoleAddition))))
        row['xy'] = tuple(row['xy'])
        additions.append(HoleAddition(**row))
    proposal = propose(spec, HoleOptions(**options), manual=raw['manual'],
                       overrides=raw['overrides'], additions=additions,
                       removed=raw['removed'], sizes=tuple(_typed(HoleSizeOverride, r) for r in raw['sizes']))
    renders = confirm(spec, proposal, manual=proposal.manual)
    canonical = _source_snapshot(spec, proposal)
    if raw['identity'] != canonical[KEY]['identity']:
        raise ValueError('WIRE_PULL_PROJECT_PHYSICAL_IDENTITY_CHANGED')
    return proposal, renders


def normalize_wire_pull_project_snapshot(snapshot):
    proposal, _ = restore_wire_pull_project_snapshot(snapshot)
    return deepcopy(_source_snapshot(proposal.spec, proposal))
