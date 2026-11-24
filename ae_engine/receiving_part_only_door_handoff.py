"""One physical Receiving Door and its source-authorized indicator bundle."""

from dataclasses import dataclass, replace
from math import isfinite
from typing import Literal, Mapping

from .contracts import (
    IndicatorBoxPartSpec, ManufacturingContext, ResolvedManufacturingGeometry,
    ResolvedManufacturingPart,
)
from .fold_designer_snapshot_dimensions import (
    normalize_fold_designer_indicator_groups, normalize_fold_designer_indicator_offsets,
)
from .manufacturing_baseline_policy import expected_baseline_path_for
from .manufacturing_door_indicator import (
    door_finished_face_size, door_indicator_offset_for_finished_center,
    indicator_box_opening_feature, indicator_small_door_spec,
)
from .receiving_factory_requests import plan_receiving_factory_confirmed_door_handoff
from .sheetmetal_feature_core import CircleFeature, FeatureAnchor, ProfileFeature, RectFeature
from .sheetmetal_features import (
    feature_is_strictly_within_surface, feature_is_within_surface, feature_surface_from_rect,
)
from .sheetmetal_geometry import Vec2


@dataclass(frozen=True)
class ReceivingPartOnlyDoorIndicatorIntent:
    """Source-side semantic intent, not PartSpec, topology, or manufacture."""
    kind: Literal["door_indicator", "indicator_box"]
    groups: tuple[int, ...]
    finished_center: Vec2



_SOURCE_PROCESS_LAYERS = frozenset(("CUTTING", "BLIND_HOLE", "MARKING"))
_PROFILE_PROCESS_LAYERS = _SOURCE_PROCESS_LAYERS | {"DATUM"}
_BAD_FEATURE = "RECEIVING_PART_ONLY_DOOR_FEATURE_SOURCE_INVALID"


def _point_is_finite(point):
    return isinstance(point, Vec2) and all(
        type(value) in (int, float) and isfinite(value) for value in (point.x, point.y)
    )


def _validate_observed_features(features, *, surface, width, height):
    for item in features:
        # CADSplit's existing extractor uses both absolute and relative
        # finished-face anchors. Every offset is checked in the real face;
        # a raw string/unfolded or arbitrary caller frame is not such an anchor.
        profile = isinstance(item, ProfileFeature)
        layers = item.layered_profiles if profile else ()
        if (not isinstance(item.anchor, FeatureAnchor) or not _point_is_finite(item.offset)
                or type(item.rotation_deg) is not int or type(item.layer) is not str
                or (item.layer not in _SOURCE_PROCESS_LAYERS
                    and not (profile and item.layer == "FROM_DXF" and layers))):
            raise ValueError(_BAD_FEATURE)
        dimensions = ((item.diameter,) if isinstance(item, CircleFeature)
                      else (item.width, item.height) if isinstance(item, RectFeature) else ())
        if any(type(n) not in (int, float) or not isfinite(n) or n <= 0 for n in dimensions):
            raise ValueError(_BAD_FEATURE)
        if profile:
            if (not isinstance(item.points, (tuple, list)) or len(item.points) < 3
                    or not all(_point_is_finite(p) for p in item.points)
                    or not isinstance(layers, (tuple, list))):
                raise ValueError(_BAD_FEATURE)
            for layer in layers:
                if (not isinstance(layer, (tuple, list)) or len(layer) != 3
                        or type(layer[0]) is not str or layer[0] not in _PROFILE_PROCESS_LAYERS
                        or not isinstance(layer[1], (tuple, list)) or type(layer[2]) is not bool
                        or len(layer[1]) < (3 if layer[2] else 2)
                        or not all(_point_is_finite(p) for p in layer[1])):
                    raise ValueError(_BAD_FEATURE)
        # Use the same strict source footprint helper as CADSplit, not the
        # inclusive interactive editor rule. A layered profile footprint is
        # the union of its inner layers; independently check an emitted
        # primary contour, which is not redundant for normal (non-FROM_DXF)
        # ProfileFeature rows.
        if (not feature_is_strictly_within_surface(surface, item, width, height)
                or (layers and item.layer != "FROM_DXF" and not feature_is_strictly_within_surface(
                    surface, replace(item, layered_profiles=()), width, height,
                ))):
            raise ValueError("feature outside canonical finished face")

def resolve_receiving_part_only_door_request(
    source_dimensions: Mapping[str, object], *,
    confirmation: str | None = None,
    confirmed_door_layout_columns,
    door_part_key: str,
    features=(),
    indicator: ReceivingPartOnlyDoorIndicatorIntent | None = None,
    context: ManufacturingContext | None = None,
) -> ResolvedManufacturingGeometry:
    """Resolve exactly one fresh, confirmed Door, never a full Bay.

    The Factory owns identity, partition, finished face and base PartSpecs.
    Source observations remain independently scoped to the chosen Door. An
    indicator box is an inseparable result with its opening and small Door.
    This operation writes no files and grants neither Set/Bay assembly
    authorization nor permission to bypass the existing verified DXF sink.
    """
    if context is not None and (
        not isinstance(context, ManufacturingContext) or context.policy is not None
    ):
        raise ValueError("RECEIVING_PART_ONLY_DOOR_CONTEXT_INVALID")
    if confirmation != "fresh_family_confirmed":
        raise ValueError("RECEIVING_PART_ONLY_DOOR_CONFIRMATION_REQUIRED")
    if type(door_part_key) is not str or not door_part_key:
        raise ValueError("RECEIVING_PART_ONLY_DOOR_OWNER_REQUIRED")
    if not isinstance(features, (tuple, list)) or not all(
        isinstance(f, (CircleFeature, RectFeature, ProfileFeature)) for f in features
    ):
        raise ValueError("RECEIVING_PART_ONLY_DOOR_FEATURE_SOURCE_INVALID")

    owner_plan = plan_receiving_factory_confirmed_door_handoff(
        source_dimensions, confirmation=confirmation,
        confirmed_door_layout_columns=confirmed_door_layout_columns,
    )
    door = dict(owner_plan.door_parts).get(door_part_key)
    if door is None:
        raise ValueError("RECEIVING_PART_ONLY_DOOR_OWNER_REQUIRED")
    if door.feature_space != "finished_face":
        raise ValueError("RECEIVING_ENGINE_CONFIRMED_PART_ROLES_INVALID")
    fw, fh = door_finished_face_size(door, context)
    face = feature_surface_from_rect("door_finished_face", Vec2(0., 0.), Vec2(fw, fh))
    _validate_observed_features(features, surface=face, width=fw, height=fh)
    door = replace(door, features=tuple(features))
    extras = ()
    if indicator is not None:
        if (not isinstance(indicator, ReceivingPartOnlyDoorIndicatorIntent)
                or indicator.kind not in ("door_indicator", "indicator_box")
                or not isinstance(indicator.finished_center, Vec2)):
            raise ValueError("RECEIVING_DOOR_SEMANTIC_REPLACEMENT_UNKNOWN")
        groups = normalize_fold_designer_indicator_groups(indicator.groups)
        x, y = normalize_fold_designer_indicator_offsets(
            indicator.finished_center.x, indicator.finished_center.y,
        )
        center = Vec2(x, y)
        if indicator.kind == "door_indicator":
            offset = door_indicator_offset_for_finished_center(door, groups, center, context)
            door = replace(door, door_indicator=groups,
                           door_indicator_offset=(offset.x, offset.y))
        else:
            opening = indicator_box_opening_feature(
                groups, thickness=door.thickness, center=center, context=context,
            )
            if not feature_is_within_surface(face, opening, fw, fh):
                raise ValueError("RECEIVING_DOOR_INDICATOR_BOX_OUTSIDE_FACE")
            door = replace(door, features=(*door.features, opening))
            small = indicator_small_door_spec(groups, thickness=door.thickness, context=context)
            baseline = expected_baseline_path_for(small, context or ManufacturingContext())
            if baseline is None or not baseline.is_file():
                raise ValueError("RECEIVING_DOOR_INDICATOR_SMALL_DOOR_BASELINE_REQUIRED")
            extras = (
                (door_part_key + "_indicator_box", IndicatorBoxPartSpec(groups, door.thickness)),
                (door_part_key + "_indicator_small_door", small),
            )

    # Keep the existing public manufacturing resolver, not a parallel solver.
    from .manufacturing_api import build_operator_part_render_data
    return ResolvedManufacturingGeometry(parts=tuple(
        ResolvedManufacturingPart(key, build_operator_part_render_data(spec, context))
        for key, spec in ((door_part_key, door), *extras)
    ))
