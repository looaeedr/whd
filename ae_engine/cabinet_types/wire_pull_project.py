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
    identity = {
        'parts': [[p.part_key, [f.face_id for f in p.mounting_faces]] for p in topology.parts],
        'holes': [[m.group_id, m.kind, m.part_key, m.face_id] for m in proposal.members],
    }
    # Historical flat identity stays byte-compatible. New folded sources bind
    # the exact rule revision and role; never silently promote an old preview.
    rules = [[p.part_key,list(p.render_data.metadata['wire_pull_corner_rules'])]
             for p in topology.parts if 'wire_pull_corner_rules' in p.render_data.metadata]
    if rules:
        identity['corner_rules'] = rules
    return identity


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
    source = raw['spec']
    # Version 1 flat projects predate adjustable three-edge cap fields. Only
    # that exact historical shape may fill unused DTO defaults; do not migrate
    # its physical topology or accept incomplete new folded sources.
    new_fields = {f.name for f in fields(WirePullBoxSpec) if f.name.startswith(("head_", "tail_")) and f.name.endswith("_material_mm")}
    all_fields = {f.name for f in fields(WirePullBoxSpec)}
    if (isinstance(source, dict) and set(source) == all_fields-new_fields
            and source.get('head_form') == source.get('tail_form') == 'flat'):
        spec = WirePullBoxSpec(**source)
    else:
        spec = _typed(WirePullBoxSpec, source)
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
