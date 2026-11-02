# -*- coding: utf-8 -*-
"""Canonical Receiving source dimensions -> confirmed Engine manufacturing requests.

No CADSplit, GUI, DXF serializer, manufacturing geometry formula, or parallel
export path lives here.  This is a bounded adapter *inside* WHD Engine between
the source W/H/D/T contract and the already-existing Family/Fold/PartSpec
owners.  A returned request is not whole-cabinet or source-feature certification.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from math import isclose, isfinite

from .box_body_fold_profile import build_box_body_profile
from .box_body_operator_part_spec import build_box_body_operator_part_spec
from .cabinet_types import policy as family_policy
from .endcap_factory_fold import build_endcap_xy_fold_profiles
from .endcap_operator_part_spec import build_endcap_operator_part_spec
from .sheetmetal_geometry import FourCornerTypePolicy
from .sheetmetal_feature_core import CircleFeature, RectFeature, ProfileFeature, FeatureAnchor

_SOURCE_KEYS = frozenset(("w", "h", "d", "t"))
_BOX_KEYS = ("fw", "zl1", "zl2", "zr2")
_PARTS = ("box_body", "head", "tail")
_FAMILY = "受電箱"


def _confirmed_endcap_source_features(raw):
    """Accept explicitly confirmed Head/Tail CUTTING Features in finished-face mm."""
    if raw is None:
        return {}
    if not isinstance(raw, Mapping) or set(raw) - {"head", "tail"}:
        raise ValueError("RECEIVING_ENDCAP_SOURCE_FEATURES_INVALID")
    result = {}
    for role, rows in raw.items():
        if not isinstance(rows, (tuple, list)):
            raise ValueError("RECEIVING_ENDCAP_SOURCE_FEATURES_INVALID")
        for feature in rows:
            if not isinstance(feature, (CircleFeature, RectFeature, ProfileFeature)):
                raise ValueError("RECEIVING_ENDCAP_SOURCE_FEATURES_INVALID")
            if feature.anchor is not FeatureAnchor.ABSOLUTE_FINISHED_FACE or feature.layer != "CUTTING":
                raise ValueError("RECEIVING_ENDCAP_SOURCE_FEATURES_INVALID")
            coords = [feature.offset.x, feature.offset.y]
            if isinstance(feature, CircleFeature):
                coords.append(feature.diameter)
                if type(feature.diameter) not in (int, float) or feature.diameter <= 0:
                    raise ValueError("RECEIVING_ENDCAP_SOURCE_FEATURES_INVALID")
            elif isinstance(feature, RectFeature):
                coords.extend((feature.width, feature.height))
                if any(type(v) not in (int, float) or v <= 0 for v in (feature.width, feature.height)):
                    raise ValueError("RECEIVING_ENDCAP_SOURCE_FEATURES_INVALID")
            else:
                if len(feature.points) < 3:
                    raise ValueError("RECEIVING_ENDCAP_SOURCE_FEATURES_INVALID")
                coords.extend(a for point in feature.points for a in (point.x, point.y))
            if any(type(v) not in (int, float) or not isfinite(float(v)) for v in coords):
                raise ValueError("RECEIVING_ENDCAP_SOURCE_FEATURES_INVALID")
        result[role] = tuple(deepcopy(rows))
    return result


def _source_dimensions(value: Mapping[str, object]) -> dict[str, float]:
    """Accept only original-source OUTSIDE W/H/D/T; never factory values."""
    if not isinstance(value, Mapping) or set(value) != _SOURCE_KEYS:
        raise ValueError("RECEIVING_SOURCE_DIMENSIONS_INVALID")
    if any(
        type(value[key]) not in (int, float)
        or not isfinite(float(value[key]))
        or float(value[key]) <= 0
        for key in _SOURCE_KEYS
    ):
        raise ValueError("RECEIVING_SOURCE_DIMENSIONS_INVALID")
    return {key: float(value[key]) for key in ("w", "h", "d", "t")}


def _saved_operator_state(source: dict[str, float], operator_snapshot):
    """Use confirmed persisted manufacturing authority; never use fresh defaults."""
    if not isinstance(operator_snapshot, Mapping):
        raise ValueError("RECEIVING_SAVED_PHYSICAL_STATE_INCOMPLETE")
    saved = deepcopy(dict(operator_snapshot))
    if family_policy.canonical_family_name(saved.get("model")) != _FAMILY:
        raise ValueError("RECEIVING_SAVED_PHYSICAL_STATE_INCOMPLETE")
    try:
        for key in _SOURCE_KEYS:
            candidate = saved[key]
            if (type(candidate) not in (int, float)
                    or not isfinite(float(candidate))
                    or not isclose(float(candidate), source[key], rel_tol=0, abs_tol=1e-6)):
                raise ValueError("RECEIVING_SOURCE_SAVED_DIMENSIONS_CONFLICT")
    except KeyError as exc:
        raise ValueError("RECEIVING_SAVED_PHYSICAL_STATE_INCOMPLETE") from exc

    try:
        if any(type(saved[key]) not in (float, int)
               or not isfinite(float(saved[key])) for key in _BOX_KEYS):
            raise ValueError("RECEIVING_SAVED_PHYSICAL_STATE_INCOMPLETE")
        structure = deepcopy(dict(saved["box_body_structure_state"]))
        if structure.get("active_type") != "three_piece_side_back_split":
            raise ValueError("RECEIVING_SAVED_PHYSICAL_STATE_INCOMPLETE")
        body_rows = deepcopy(tuple(saved["box_body_fold_profile"]))
        folds = deepcopy(dict(saved["endcap_fold_profiles"]))
        if not body_rows or any(
            part not in folds or
            not isinstance(folds[part], Mapping) or
            not folds[part].get("X") or not folds[part].get("Y")
            for part in ("head", "tail")
        ):
            raise ValueError("RECEIVING_SAVED_PHYSICAL_STATE_INCOMPLETE")
        if "endcap_corner_policies" in saved:
            policies = dict(saved["endcap_corner_policies"])
        elif "corner_state" in saved:
            from .manufacturing_api import resolve_operator_snapshot_corner_policy
            policies = {
                part: resolve_operator_snapshot_corner_policy(
                    part, corner_state=saved["corner_state"],
                    input_snapshot=saved,
                )
                for part in ("head", "tail")
            }
        else:
            raise ValueError("RECEIVING_SAVED_PHYSICAL_STATE_INCOMPLETE")
        if any(not isinstance(policies.get(part), FourCornerTypePolicy)
               for part in ("head", "tail")):
            raise ValueError("RECEIVING_SAVED_PHYSICAL_STATE_INCOMPLETE")
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("RECEIVING_SAVED_PHYSICAL_STATE_INCOMPLETE") from exc

    # Original source is authoritative for W/H/D/T; the verified saved state
    # owns all other operator geometry. Neither layer overwrites the other.
    for key, number in source.items():
        saved[key] = number
    return saved, structure, body_rows, folds, policies


def build_receiving_factory_confirmed_parts(
    source_dimensions: Mapping[str, object], *,
    confirmation: str | None = None,
    operator_snapshot: Mapping[str, object] | None = None,
    confirmed_endcap_features: Mapping[str, object] | None = None,
):
    """Resolve a confirmed Receiving P1/Bay's Body, Head and Tail via WHD Engine.

    ``source_dimensions`` contains *only* the original W/H/D/T, not FW,
    bends, corner choices or manufacture parameters.

    ``fresh_family_confirmed`` explicitly accepts the current WHD Family's
    fresh operator defaults; it does not imply CADSplit inferred or approved
    them.  ``saved_operator_confirmed`` requires the real persisted profiles,
    structure and Corner authority and never silently resets them to fresh
    defaults. Unconfirmed source-only requests remain in the existing blocked
    integration route.

    The output is the existing physical PartSpec tuple for
    ``ManufacturingResolvedBayInput.confirmed_parts``, subsequently rendered,
    verified and committed by ``export_verified_resolved_integration_bays``.
    This subset is NOT full-cabinet/NFB/Feature certification.
    """
    source = _source_dimensions(source_dimensions)
    features_by_role = _confirmed_endcap_source_features(confirmed_endcap_features)
    if confirmation not in ("fresh_family_confirmed", "saved_operator_confirmed"):
        raise ValueError("RECEIVING_OPERATOR_CONFIRMATION_REQUIRED")

    if confirmation == "fresh_family_confirmed":
        if operator_snapshot is not None:
            raise ValueError("RECEIVING_OPERATOR_CONFIRMATION_AMBIGUOUS")
        # Family's existing fresh-project defaults are authoritative; reapply
        # the independently confirmed source dimensions because the Family's
        # nominal W/H/D are only new-project initial values.
        values = family_policy.apply_fresh_family_defaults(source, _FAMILY)
        values.update(source)
        structure = family_policy.resolve_box_body_structure_state(_FAMILY)
        body_rows = build_box_body_profile(values)
        folds = {
            part: build_endcap_xy_fold_profiles(values, part_key=part)
            for part in ("head", "tail")
        }
        policies = {
            part: family_policy.endcap_corner_policy(
                _FAMILY, frame_width=values["fw"],
                thickness=values["t"], state=structure,
            )
            for part in ("head", "tail")
        }
        if any(not isinstance(policies[part], FourCornerTypePolicy)
               for part in ("head", "tail")):
            raise ValueError("RECEIVING_FAMILY_CORNER_POLICY_UNAVAILABLE")
    else:
        values, structure, body_rows, folds, policies = _saved_operator_state(
            source, operator_snapshot
        )

    body = build_box_body_operator_part_spec(
        values, model_name=_FAMILY,
        fold_profile=body_rows,
        structure_state=structure,
        endcap_y_profiles={
            part: folds[part]["Y"] for part in ("head", "tail")
        },
        snapshot=values,
    )

    # Supply only cabinet dimensions and the Engine-owned BoxBody datum to the
    # compatibility scalar seam. The actual EndCap X/Y physical Fold is the
    # authored canonical profile and is read back by the EndCap Engine.
    endcap_values = {key: values[key] for key in ("w", "h", "d", "t", "fw", "zl1")}
    parts = [("box_body", body)]
    for part in ("head", "tail"):
        spec = build_endcap_operator_part_spec(
            endcap_values, model_name=_FAMILY,
            is_tail=(part == "tail"), holes=features_by_role.get(part, ()),
            fold_profiles=folds[part],
            corner_policy=policies[part],
            box_body_structure_state=structure,
        )
        parts.append((part, spec))
    assert tuple(key for key, _ in parts) == _PARTS
    return tuple(parts)
