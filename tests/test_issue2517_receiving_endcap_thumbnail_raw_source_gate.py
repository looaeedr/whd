"""#2517: Receiving Head/Tail thumbnail face dimensions remain Engine-owned.

The preview is read-only, not a CUTTING or DXF manufacturing certification.
"""
from __future__ import annotations

from copy import deepcopy
import inspect
import tkinter as tk

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from gui_modules.application import receiving_endcap_thumbnail as gui


def _source_feature():
    return CircleFeature(
        diameter=20, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(40, 30), layer="CUTTING",
    )


@pytest.mark.parametrize("width,depth", [
    (True, 100), (200, False), (None, 100), (200, None),
    (float("nan"), 100), (200, float("inf")),
    (0, 100), (200, -1), ("invalid", 100),
])
def test_public_engine_rejects_invalid_raw_endcap_face_before_feature_geometry(width, depth):
    features = (_source_feature(),)
    before = deepcopy(features)
    with pytest.raises(ValueError):
        api.receiving_endcap_feature_preview_shapes(features, width, depth)
    assert features == before


def test_public_engine_preserves_decimal_face_sources_and_saved_feature_identity():
    features = (_source_feature(),)
    before = deepcopy(features)
    result = api.receiving_endcap_feature_preview_shapes(
        features, "200.25", "100.75",
    )
    assert result == ((("circle", "CUTTING", (40, 30, 10.0)),), 0)
    assert result == gui.endcap_preview_geometry(features, 200.25, 100.75)
    assert features == before
    engine_source = inspect.getsource(api.receiving_endcap_feature_preview_shapes)
    assert 'normalize_operator_source_dimension(width, field="w")' in engine_source
    assert 'normalize_operator_source_dimension(depth, field="d")' in engine_source


@pytest.mark.parametrize("features", [None, ()])
@pytest.mark.parametrize("width,depth", [(True, 100), (200, False), (0, 100), (200, float("nan"))])
def test_tk_thumbnail_does_not_erase_existing_preview_when_raw_source_invalid(
    features, width, depth,
):
    root = tk.Tk()
    root.withdraw()
    try:
        canvas = tk.Canvas(root, width=220, height=134)
        canvas.pack()
        marker = canvas.create_text(30, 30, text="old preview")
        old = {"source_count": "sentinel"}
        canvas._receiving_endcap_preview = old
        with pytest.raises(ValueError):
            gui.paint_endcap_thumbnail(canvas, features, width, depth)
        assert canvas.find_all() == (marker,)
        assert canvas.itemcget(marker, "text") == "old preview"
        assert canvas._receiving_endcap_preview is old
    finally:
        root.destroy()


def test_unselected_thumbnail_still_renders_valid_engine_dimensions():
    root = tk.Tk()
    root.withdraw()
    try:
        canvas = tk.Canvas(root, width=220, height=134)
        canvas.pack()
        outcome = gui.paint_endcap_thumbnail(canvas, None, 200.25, 100.75)
        assert outcome["source_count"] is None
        assert outcome["shapes"] == ()
        assert any(
            "尚未選擇" in canvas.itemcget(item, "text")
            for item in canvas.find_all() if canvas.type(item) == "text"
        )
    finally:
        root.destroy()
