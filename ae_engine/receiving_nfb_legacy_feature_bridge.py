# -*- coding: utf-8 -*-
"""#1497: existing Hole Editor Features -> same physical inner-door FinalScene.

Only the EXACT physical panel stable_id owns these features. "door_c1_r1"
is the OUTER door, not an inner-door alias; never transfer its holes. Feature
positions are authored on the finished face; convert by the SAME fold/T2
compensation already used by WHD's manufactured panel.

Unknown feature encodings and multiple competing feature stores fail closed.
This is a read-only projection; original Feature, snapshot, legacy and
user-maintained source files are never modified. The existing #1497 native
FinalScene/legacy claim guard still owns Q16 collisions and physical CUTTING.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Mapping

from .inner_door_panels import InnerDoorPanelPart
from .manufacturing_api import build_inner_door_panel_render_data
from .manufacturing_render_data import (
    PartRenderData, _translated_scene, material_polygon_from_final_scene,
)
from .sheetmetal_drawing import (
    CirclePrimitive, DrawingScene, LinePrimitive, PolylinePrimitive,
    resolved_features_to_primitives,
)
from .sheetmetal_feature_surface import (
    feature_is_strictly_within_surface, feature_surface_from_rect,
    resolve_surface_features,
)
from .sheetmetal_features import CircleFeature, RectFeature, ProfileFeature
from .sheetmetal_geometry import Vec2


def existing_inner_door_feature_finalscene(
    snapshot: Mapping[str, object],
    panel: InnerDoorPanelPart,
    *,
    existing_render_data: PartRenderData | None = None,
) -> PartRenderData | None:
    """Preserve current same-part legacy Hole Editor Features in manufacturing UV.

    If no same-physical-part Features are present, return existing_render_data
    unchanged. A nonempty legacy Feature set cannot be manufactured from a
    silently regenerated blank. The generated FinalScene retains structural
    CUTTING/BEND as its exact prefix, then native legacy hole/marking geometry.
    """
    if not isinstance(panel, InnerDoorPanelPart):
        raise TypeError("NFB legacy source needs the actual inner-door panel")
    if not isinstance(snapshot, Mapping):
        raise TypeError("NFB legacy source requires current physical snapshot")
    choices = []
    for key in ("part_features", "surface_features"):
        store = snapshot.get(key)
        if store is None:
            continue
        if not isinstance(store, Mapping):
            raise ValueError(f"NFB legacy {key} owner store invalid")
        listed = store.get(panel.stable_id)
        if listed is None:
            continue
        if not isinstance(listed, (tuple, list)):
            raise ValueError("NFB legacy inner-door Feature list format unresolved")
        if listed:
            choices.append((key, tuple(listed)))
    faces = snapshot.get("part_face_features")
    if faces is not None:
        if not isinstance(faces, Mapping):
            raise ValueError("NFB legacy face Feature source is invalid")
        if faces.get(panel.stable_id):
            # Inner-door is one finished-face sheet; a generic face-key
            # mapping without a proven inner-door face datum is ambiguous.
            raise ValueError("NFB legacy inner-door face Feature owner not verified")
    if not choices:
        return existing_render_data
    if len(choices) != 1:
        raise ValueError("NFB legacy inner-door has competing physical Feature stores")

    features = choices[0][1]
    if any(not isinstance(f, (CircleFeature, RectFeature, ProfileFeature))
           for f in features):
        raise ValueError("NFB legacy Hole Editor Feature format unsupported")
    # Finished-face WHD width/height includes thickness compensation; the
    # actual flat core lies from fold_left..(blank_width-fold_right).
    # Hence UV = finished XY + fold length - thickness on each axis.
    t = float(panel.thickness)
    surface = feature_surface_from_rect(
        panel.stable_id + ":finished-face",
        Vec2(t, t),
        Vec2(panel.width - t, panel.height - t),
    )
    for feature in features:
        if not feature_is_strictly_within_surface(
            surface, feature, panel.width, panel.height,
        ):
            raise ValueError("NFB legacy Feature outside the actual finished inner-door core")
    resolved = resolve_surface_features(
        surface, features, panel.width, panel.height,
    )
    created = resolved_features_to_primitives(resolved)
    projected = _translated_scene(
        DrawingScene(list(created)),
        float(panel.fold_left) - t,
        float(panel.fold_bottom) - t,
    )
    canonical = build_inner_door_panel_render_data(panel)
    if existing_render_data is not None:
        if not isinstance(existing_render_data, PartRenderData):
            raise TypeError("NFB legacy existing render must be PartRenderData")
        if (
            existing_render_data.metadata.get("stable_id") != panel.stable_id
            or existing_render_data.unfolded_topology != canonical.unfolded_topology
            or existing_render_data.fold_guides != canonical.fold_guides
        ):
            raise ValueError("NFB existing legacy FinalScene does not match physical panel")
        existing = tuple(existing_render_data.scene.primitives)
        prefix = tuple(canonical.scene.primitives)
        if existing[:len(prefix)] != prefix:
            raise ValueError("NFB existing legacy FinalScene structural baseline changed")
        available = list(existing[len(prefix):])
        for required in projected.primitives:
            # An identity/source tag may be attached to an already rendered
            # feature; geometric primitive ownership must still match once.
            found = [
                index for index, actual in enumerate(available)
                if _same_feature_geometry(actual, required)
            ]
            if len(found) != 1:
                raise ValueError("NFB existing FinalScene does not uniquely own current legacy Feature")
            del available[found[0]]
        return existing_render_data

    scene = DrawingScene()
    scene.extend(canonical.scene.primitives)
    scene.extend(projected.primitives)
    return replace(
        canonical,
        scene=scene,
        material=material_polygon_from_final_scene(scene),
        metadata={
            **dict(canonical.metadata),
            "nfb_legacy_feature_owner": panel.stable_id,
            "nfb_legacy_feature_store": choices[0][0],
            "nfb_legacy_feature_count": len(features),
        },
    )


def _same_feature_geometry(left, right) -> bool:
    """Ignore only a Circle source_id tag; never ignore actual geometry."""
    if type(left) is not type(right):
        return False
    if isinstance(left, CirclePrimitive):
        return (left.center == right.center and left.radius == right.radius
                and left.layer == right.layer and left.color == right.color
                and left.source_type == right.source_type)
    if isinstance(left, (PolylinePrimitive, LinePrimitive)):
        return left == right
    return False
