# -*- coding: utf-8 -*-
from dataclasses import replace

from ae_engine.drawing_annotations import FeatureCallout, LinearDimensionAnnotation
from ae_engine.sheetmetal_geometry import Vec2


def _semantic_id(annotation):
    value = getattr(annotation, "semantic_id", None)
    assert value not in (None, ""), (
        "DM6 RED: annotation semantics must carry a stable identity that is "
        "independent from display text/label"
    )
    return value


def test_dm6_red_label_format_mutation_does_not_change_dimension_identity():
    original = LinearDimensionAnnotation(
        axis="x",
        value=100.0,
        start=Vec2(0.0, 0.0),
        end=Vec2(100.0, 0.0),
        label="100",
    )
    semantic_id = _semantic_id(original)

    reformatted = replace(original, label="100.0 mm")

    assert _semantic_id(reformatted) == semantic_id


def test_dm6_red_duplicate_callout_labels_keep_distinct_source_identity():
    first = FeatureCallout(
        source_id="H1",
        source_type="mounting_hole",
        anchor=Vec2(10.0, 20.0),
        label="⌀10",
    )
    second = FeatureCallout(
        source_id="H2",
        source_type="mounting_hole",
        anchor=Vec2(90.0, 20.0),
        label="⌀10",
    )

    assert _semantic_id(first) != _semantic_id(second)


def test_dm6_red_same_value_x_y_dimensions_have_distinct_semantic_identity():
    x_dim = LinearDimensionAnnotation(
        axis="x",
        value=100.0,
        start=Vec2(0.0, 0.0),
        end=Vec2(100.0, 0.0),
        label="100",
    )
    y_dim = LinearDimensionAnnotation(
        axis="y",
        value=100.0,
        start=Vec2(0.0, 0.0),
        end=Vec2(0.0, 100.0),
        label="100",
    )

    assert _semantic_id(x_dim) != _semantic_id(y_dim)
