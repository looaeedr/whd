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
from .contracts import DoorPartSpec
from .part_dimension_projection import door_part_projections
from .sheetmetal_part_adapters import validate_door_layout_dimensions
from .sheetmetal_geometry import FourCornerTypePolicy
from .sheetmetal_feature_core import CircleFeature, RectFeature, ProfileFeature, FeatureAnchor

_SOURCE_KEYS = frozenset(("w", "h", "d", "t"))
_BOX_KEYS = ("fw", "zl1", "zl2", "zr2")
_CORE_PARTS = ("box_body", "head", "tail")
_DOOR_VALUES = ("fw", "door_gap_w", "door_gap_h", "door_fold_l", "door_fold_r", "door_fold_t", "door_fold_b")
_FAMILY = "受電箱"


def _confirmed_finished_face_cutting_features(raw, *, allowed_roles, invalid_code):
    """Validate explicitly source-confirmed CUTTING in finished-face coordinates."""
    if raw is None:
        return {}
    if not isinstance(raw, Mapping) or set(raw) - set(allowed_roles):
        raise ValueError(invalid_code)
    result = {}
    for role, rows in raw.items():
        if not isinstance(rows, (tuple, list)):
            raise ValueError(invalid_code)
        for feature in rows:
            if not isinstance(feature, (CircleFeature, RectFeature, ProfileFeature)):
                raise ValueError(invalid_code)
            if feature.anchor is not FeatureAnchor.ABSOLUTE_FINISHED_FACE or feature.layer != "CUTTING":
                raise ValueError(invalid_code)
            # Both Head/Tail and Door receive source-confirmed physical CUTTING.
            # A Profile's layered sub-contours can encode another, unconfirmed
            # manufacturing operation. No part role may silently inherit it.
            if isinstance(feature, ProfileFeature) and feature.layered_profiles:
                raise ValueError(invalid_code)
            # Python bool is an integer subclass; never turn True into an
            # unconfirmed one-degree physical rotation on EndCap CUTTING.
            if type(feature.rotation_deg) is not int:
                raise ValueError(invalid_code)
            coords = [feature.offset.x, feature.offset.y]
            if isinstance(feature, CircleFeature):
                coords.append(feature.diameter)
                if type(feature.diameter) not in (int, float) or feature.diameter <= 0:
                    raise ValueError(invalid_code)
            elif isinstance(feature, RectFeature):
                coords.extend((feature.width, feature.height))
                if any(type(v) not in (int, float) or v <= 0 for v in (feature.width, feature.height)):
                    raise ValueError(invalid_code)
            else:
                if len(feature.points) < 3:
                    raise ValueError(invalid_code)
                coords.extend(a for point in feature.points for a in (point.x, point.y))
            if any(type(v) not in (int, float) or not isfinite(float(v)) for v in coords):
                raise ValueError(invalid_code)
        result[role] = tuple(deepcopy(rows))
    return result


def _confirmed_endcap_source_features(raw):
    """The Head/Tail public source error must match the strict Door boundary."""
    code = "RECEIVING_ENDCAP_SOURCE_FEATURES_INVALID"
    try:
        return _confirmed_finished_face_cutting_features(
            raw, allowed_roles={"head", "tail"}, invalid_code=code,
        )
    except (AttributeError, TypeError, ValueError, OverflowError) as exc:
        # Frozen Feature DTOs are not runtime-validated: a direct caller may
        # still supply a missing Vec2, malformed Profile or overflowing int.
        # Fail closed with the source contract, never stage a physical DXF.
        raise ValueError(code) from exc


def _require_saved_endcap_cutting_source_parity(values, confirmed):
    """Saved Head/Tail CUTTING cannot vanish in a source-confirmed Bay.

    An independently confirmed original CADSplit Head/Tail feature is still
    admitted when the saved operator did not already author that role; a
    persisted nonempty role, however, may never be silently dropped or
    overridden by an unrelated external physical hole.
    """
    code = "RECEIVING_SAVED_ENDCAP_SOURCE_FEATURES_MISMATCH"
    stored = values.get("part_features", {})
    if not isinstance(stored, Mapping):
        # Other saved feature owner (e.g. Door) supplies its own diagnostic.
        # Only claim a Head/Tail source failure if one was actually submitted.
        if confirmed:
            raise ValueError(code)
        return
    for role in ("head", "tail"):
        if role not in stored:
            continue
        original = stored[role]
        if not isinstance(original, (tuple, list)):
            raise ValueError(code)
        if original and tuple(original) != confirmed.get(role, ()):
            raise ValueError(code)


def _confirmed_door_source_features(raw, *, part_keys):
    """Only Engine physical Door cell IDs may carry confirmed CUTTING inputs."""
    code = "RECEIVING_DOOR_SOURCE_FEATURES_INVALID"
    try:
        verified = _confirmed_finished_face_cutting_features(
            raw, allowed_roles=set(part_keys), invalid_code=code,
        )
        # The same confirmed CUTTING source guard applies to Door and
        # Head/Tail; avoid maintaining a second Door-only physical policy.
    except (AttributeError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError(code) from exc
    return verified


def _confirmed_base_plate_source_features(raw):
    """Admit only saved, source-confirmed physical BasePlate CUTTING DTOs."""
    code = "RECEIVING_FACTORY_BASE_SOURCE_FEATURES_INVALID"
    try:
        return _confirmed_finished_face_cutting_features(
            raw, allowed_roles={"base_plate"}, invalid_code=code,
        )
    except (AttributeError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError(code) from exc


_PHYSICAL_BOX_BODY_ROLES = frozenset((
    "box_body:left_side", "box_body:back", "box_body:right_side",
))


def _confirmed_saved_box_body_piece_features(values, confirmed, *, confirmation):
    """Verify original physical-sheet CUTTING before constructing a Body spec.

    These are material-sheet UV features, unlike finished-face BoxBody
    features. The existing physical-sheet FinalScene resolver owns
    placement and outline validation. Never silently omit saved holes or
    accept unconfirmed physical features from a persisted snapshot.
    """
    code = "RECEIVING_FACTORY_BOX_BODY_PIECE_FEATURE_SOURCE_UNCONFIRMED"
    if confirmation != "saved_operator_confirmed":
        if confirmed is not None:
            raise ValueError("RECEIVING_FACTORY_BOX_BODY_FEATURES_REQUIRE_SAVED_OPERATOR")
        return {}
    try:
        if values.get("box_body_face_features"):
            # Different finished-face source space. Its certification is not
            # covered by a physical-sheet UV confirmation.
            raise ValueError("RECEIVING_FACTORY_BOX_BODY_FACE_SOURCE_UNCONFIRMED")
        stored_parts = values.get("part_features", {})
        explicit = values.get("physical_piece_features")
        if not isinstance(stored_parts, Mapping):
            if confirmed is not None or explicit is not None:
                # An explicit Body request cannot trust an unreadable store.
                raise ValueError(code)
            # No BoxBody physical source was supplied. Leave malformed Door
            # and BasePlate saved-state diagnostics to their original owners.
            return {}
        if stored_parts.get("box_body"):
            raise ValueError("RECEIVING_FACTORY_BOX_BODY_FACE_SOURCE_UNCONFIRMED")
        legacy = {
            key: rows for key, rows in stored_parts.items()
            if isinstance(key, str) and key.startswith("box_body:")
        }
        if explicit is not None and not isinstance(explicit, Mapping):
            raise ValueError(code)
        if explicit is not None and legacy:
            for key in set(explicit) | set(legacy):
                a, b = explicit.get(key, ()), legacy.get(key, ())
                if not isinstance(a, (list, tuple)) or not isinstance(b, (list, tuple)):
                    raise ValueError(code)
                if tuple(a) != tuple(b):
                    raise ValueError(code)
        original = explicit if explicit is not None else legacy
        for role, rows in original.items():
            if role not in _PHYSICAL_BOX_BODY_ROLES and rows:
                raise ValueError(code)
            if not isinstance(rows, (tuple, list)):
                raise ValueError(code)
        physical = _confirmed_finished_face_cutting_features(
            confirmed, allowed_roles=_PHYSICAL_BOX_BODY_ROLES, invalid_code=code,
        )
        for role in _PHYSICAL_BOX_BODY_ROLES:
            saved_rows = original.get(role, ())
            if not isinstance(saved_rows, (tuple, list)) or tuple(saved_rows) != physical.get(role, ()):
                raise ValueError(code)
        return physical
    except (AttributeError, TypeError, ValueError, OverflowError) as exc:
        if isinstance(exc, ValueError) and str(exc) in (
            code, "RECEIVING_FACTORY_BOX_BODY_FACE_SOURCE_UNCONFIRMED",
        ):
            raise
        raise ValueError(code) from exc


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
    # The Family Registry accepts both persisted model and cabinet_type.
    # Read the *same saved snapshot identity* as GUI and other Engine APIs:
    # a cabinet_type-only legacy project must not be rejected or replaced
    # with fresh factory defaults. A conflicting explicit model still wins.
    if family_policy.canonical_family_name(saved) != _FAMILY:
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



def _confirmed_door_parts(values, source, confirmed_columns, *, confirmation, confirmed_features=None):
    """Use explicit, confirmed Door topology and the existing Engine projector.

    No source-panel labels, inferred upper/lower heights or preview-only holes
    may enter canonical manufacturing. Empty columns preserve the old 3-role
    source contract for callers that have not confirmed Doors.
    """
    if not confirmed_columns:
        return ()
    try:
        cells = validate_door_layout_dimensions(
            confirmed_columns, total_width=source["w"], total_height=source["h"],
        )
        if confirmation == "saved_operator_confirmed":
            if values.get("multi_door_enabled") is not True:
                raise ValueError("disabled saved Door layout")
            saved_cells = validate_door_layout_dimensions(
                values.get("door_layout_columns") or (),
                total_width=source["w"], total_height=source["h"],
            )
            if cells != saved_cells:
                raise ValueError("confirmed Door layout differs from saved state")
            indicator_states = values.get("door_layout_indicator_states", {})
            if not isinstance(indicator_states, Mapping):
                raise ValueError("unverified saved Door indicator source")
            from .fold_designer_snapshot_dimensions import (
                project_operator_door_cell_indicator_manufacturing_source,
            )
            for cell in cells:
                part_key = f"door_c{cell.column_index + 1}_r{cell.row_index + 1}"
                # Persisted GUI projects use zero-based col:row keys; accept
                # canonical physical IDs and older tuple keys as well.
                candidates = (
                    f"{cell.column_index}:{cell.row_index}",
                    (cell.column_index, cell.row_index),
                    part_key,
                )
                present = [indicator_states[key] for key in candidates
                           if key in indicator_states]
                if len(present) > 1:
                    raise ValueError("ambiguous saved Door indicator source")
                if present:
                    indicator = project_operator_door_cell_indicator_manufacturing_source(
                        present[0],
                    )
                    if indicator["mode"] != "none":
                        raise ValueError(
                            "saved Door indicator holes need separately confirmed Feature inputs"
                        )
        for key in _DOOR_VALUES:
            value = values[key]
            if (type(value) not in (float, int) or not isfinite(float(value))
                    or (float(value) <= 0 if key not in ("door_gap_w", "door_gap_h")
                        else float(value) < 0)):
                raise ValueError(f"invalid confirmed Door setting: {key}")
        projections = door_part_projections({
            **values, "model": _FAMILY, "multi_door_enabled": True,
            "door_layout_columns": confirmed_columns,
        })
        if len(projections) != len(cells) or any(
            row.formed_width <= 0 or row.formed_height <= 0
            or not isfinite(row.formed_width) or not isfinite(row.formed_height)
            for row in projections
        ):
            raise ValueError("invalid Door finished size")
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError("RECEIVING_CONFIRMED_DOOR_SOURCE_INVALID") from exc

    features_by_part = _confirmed_door_source_features(
        confirmed_features, part_keys=(cell.part_key for cell in projections),
    )
    if confirmation == "saved_operator_confirmed":
        saved_features = values.get("part_features", {})
        if not isinstance(saved_features, Mapping):
            raise ValueError("RECEIVING_CONFIRMED_DOOR_SOURCE_INVALID: RECEIVING_SAVED_DOOR_SOURCE_FEATURES_MISMATCH")
        for cell in projections:
            if cell.part_key in saved_features:
                saved_rows = saved_features[cell.part_key]
                if not isinstance(saved_rows, (list, tuple)):
                    raise ValueError("RECEIVING_CONFIRMED_DOOR_SOURCE_INVALID: RECEIVING_SAVED_DOOR_SOURCE_FEATURES_MISMATCH")
            else:
                saved_rows = ()
            if saved_rows and tuple(saved_rows) != features_by_part.get(cell.part_key, ()):
                raise ValueError("RECEIVING_CONFIRMED_DOOR_SOURCE_INVALID: RECEIVING_SAVED_DOOR_SOURCE_FEATURES_MISMATCH")

    return tuple((cell.part_key, DoorPartSpec(
        width=cell.start_width, height=cell.start_height,
        thickness=float(values["t"]), frame_width=float(values["fw"]),
        model_name=_FAMILY, gap_w=float(values["door_gap_w"]),
        gap_h=float(values["door_gap_h"]),
        fold_left=float(values["door_fold_l"]),
        fold_right=float(values["door_fold_r"]),
        fold_top=float(values["door_fold_t"]),
        fold_bottom=float(values["door_fold_b"]),
        frame_edges=cell.frame_edges, feature_space="finished_face",
        features=features_by_part.get(cell.part_key, ()),
    )) for cell in projections)



def _confirmed_saved_ordinary_base_plate(
    values, *, structure, body_rows, confirmed_features=None,
):
    """Materialize an explicitly saved ordinary Base Plate using Engine owners.

    NFB-submitted base plates, tiers, PADs and welded EARs are separate
    source-certified manufacturing operations.  They cannot be granted access
    to the ordinary verified-Bay part path by this optional source adapter.
    """
    if values.get("nfb_config_submitted") is True:
        raise ValueError("RECEIVING_FACTORY_NFB_BASE_REQUIRES_VERIFIED_PAIR_API")
    config = values.get("receiving_base_plate")
    if not isinstance(config, Mapping):
        raise ValueError("RECEIVING_FACTORY_CONFIRMED_BASE_SOURCE_REQUIRED")
    from .receiving_base_plate_settings_validation import (
        validate_receiving_base_plate_settings,
    )
    from .receiving_base_plate_config import receiving_base_plate_values
    from .operator_auxiliary_part_specs import build_base_plate_operator_part_spec
    from .sheetmetal_part_adapters import (
        RECEIVING_BASE_PATTERN_LEFT, RECEIVING_BASE_PATTERN_RIGHT,
    )
    # The verified-Bay batch admits only ordinary LEFT/RIGHT sources.
    # Reject CENTER/tier semantics before a family-specific EAR pitch probe
    # so the API reports an explicit unsupported manufacturing role.
    if config.get("pattern") not in (
        RECEIVING_BASE_PATTERN_LEFT, RECEIVING_BASE_PATTERN_RIGHT,
    ):
        raise ValueError("RECEIVING_FACTORY_ORDINARY_BASE_PATTERN_UNVERIFIED")
    # This is the exact Engine settings preflight used on the operator side:
    # source dimensions, physical EAR pitch, contour and pattern must agree.
    validate_receiving_base_plate_settings(
        input_snapshot=values, settings_values={}, config=config,
    )
    physical = receiving_base_plate_values(values)
    if physical is None or physical["receiving_bend_pattern"] not in (
        RECEIVING_BASE_PATTERN_LEFT, RECEIVING_BASE_PATTERN_RIGHT,
    ):
        raise ValueError("RECEIVING_FACTORY_ORDINARY_BASE_PATTERN_UNVERIFIED")
    # The original typed saved Hole Editor source and separately confirmed
    # physical CUTTING must match exactly. Never silently drop a saved hole,
    # accept an unsaved caller hole, or derive geometry in CADSplit.
    confirmed = _confirmed_base_plate_source_features(confirmed_features)
    input_rows = confirmed.get("base_plate", ())
    stored_features = values.get("part_features", {})
    if not isinstance(stored_features, Mapping):
        raise ValueError("RECEIVING_FACTORY_BASE_FEATURE_SOURCE_UNCONFIRMED")
    saved_rows = stored_features.get("base_plate", ())
    if (not isinstance(saved_rows, (tuple, list))
            or tuple(saved_rows) != tuple(input_rows)):
        raise ValueError("RECEIVING_FACTORY_BASE_FEATURE_SOURCE_UNCONFIRMED")
    base_values = {**values, **physical, "model": _FAMILY}
    spec = build_base_plate_operator_part_spec(
        base_values, features=input_rows,
        box_body_structure_state=structure, box_body_fold_profile=body_rows,
    )
    if spec.physical_id != "base_plate" or spec.receiving_nfb_depth_pair_mm is not None:
        raise ValueError("RECEIVING_FACTORY_ORDINARY_BASE_PATTERN_UNVERIFIED")
    return "base_plate", spec


def build_receiving_factory_confirmed_parts(
    source_dimensions: Mapping[str, object], *,
    confirmation: str | None = None,
    operator_snapshot: Mapping[str, object] | None = None,
    confirmed_endcap_features: Mapping[str, object] | None = None,
    confirmed_door_layout_columns=(),
    confirmed_door_features: Mapping[str, object] | None = None,
    include_confirmed_base_plate: bool = False,
    confirmed_base_plate_features: Mapping[str, object] | None = None,
    confirmed_box_body_piece_features: Mapping[str, object] | None = None,
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
    if type(include_confirmed_base_plate) is not bool:
        raise ValueError("RECEIVING_FACTORY_BASE_SELECTION_MUST_BE_BOOLEAN")
    source = _source_dimensions(source_dimensions)
    features_by_role = _confirmed_endcap_source_features(confirmed_endcap_features)
    if confirmation not in ("fresh_family_confirmed", "saved_operator_confirmed"):
        raise ValueError("RECEIVING_OPERATOR_CONFIRMATION_REQUIRED")
    if confirmed_door_features is not None and not confirmed_door_layout_columns:
        raise ValueError("RECEIVING_DOOR_LAYOUT_REQUIRED_FOR_FEATURES")
    if include_confirmed_base_plate and confirmation != "saved_operator_confirmed":
        raise ValueError("RECEIVING_FACTORY_BASE_REQUIRES_SAVED_OPERATOR_CONFIRMATION")
    if confirmed_base_plate_features is not None and not include_confirmed_base_plate:
        raise ValueError("RECEIVING_FACTORY_BASE_SELECTION_REQUIRED_FOR_FEATURES")

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
        _require_saved_endcap_cutting_source_parity(values, features_by_role)

    confirmed_body_pieces = _confirmed_saved_box_body_piece_features(
        values, confirmed_box_body_piece_features, confirmation=confirmation,
    )
    # Force the BoxBody owner to consume only source-confirmed sheets even
    # when a legacy saved snapshot contained extra, untrusted physical data.
    body_snapshot = {**values, "physical_piece_features": confirmed_body_pieces}
    body = build_box_body_operator_part_spec(
        values, model_name=_FAMILY,
        fold_profile=body_rows,
        structure_state=structure,
        endcap_y_profiles={
            part: folds[part]["Y"] for part in ("head", "tail")
        },
        source_part_features=confirmed_body_pieces,
        snapshot=body_snapshot,
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
            # Match GUI's canonical EndCap owner: its assembly FW datum comes
            # from this exact BoxBody Fold, not an absent or caller-computed
            # formed-width scalar. The Engine recomputes adjacent real bends.
            box_body_fold_profile=body_rows,
            box_body_structure_state=structure,
        )
        parts.append((part, spec))
    assert tuple(key for key, _ in parts) == _CORE_PARTS
    parts.extend(_confirmed_door_parts(
        values, source, tuple(confirmed_door_layout_columns or ()),
        confirmation=confirmation, confirmed_features=confirmed_door_features,
    ))
    if include_confirmed_base_plate:
        parts.append(_confirmed_saved_ordinary_base_plate(
            values, structure=structure, body_rows=body_rows,
            confirmed_features=confirmed_base_plate_features,
        ))
    return tuple(parts)
