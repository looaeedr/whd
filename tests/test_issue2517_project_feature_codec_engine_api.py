"""#2517 .p6fold Feature/Vec2 encoding is the Engine's public API."""
from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
import ae_engine.project_feature_codec as codec
from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
import phase6_project_file as project


def test_gui_file_codec_uses_same_engine_callable_objects():
    assert project._encode is api.encode_project_value is codec._encode
    assert project._decode is api.decode_project_value is codec._decode
    assert project._decode_feature is api.decode_project_feature is codec._decode_feature
    assert project._as_vec2 is api.project_vec2_from_raw is codec._as_vec2


def test_public_engine_feature_codec_preserves_real_circle_and_vec2_without_tk():
    feature = CircleFeature(
        diameter=12.0, anchor=FeatureAnchor.PANEL_CENTER,
        offset=Vec2(3.0, -4.0), layer="CUTTING", source_type="test",
    )
    source = {"nested": [{"feature": feature, "location": Vec2(1.5, -2.25)}]}
    encoded = api.encode_project_value(source)
    assert encoded["nested"][0]["feature"]["__phase6_type__"] == "CircleFeature"
    loaded = api.decode_project_value(json.loads(json.dumps(encoded, ensure_ascii=False)))
    actual = loaded["nested"][0]
    assert actual["feature"] == feature
    assert actual["location"] == Vec2(1.5, -2.25)
    assert actual["feature"] is not feature


def test_public_engine_codec_rejects_invalid_physical_feature_type_and_vec2():
    with pytest.raises(ValueError, match="unsupported feature type"):
        api.decode_project_feature("ForgedFeature", {"__phase6_type__": "ForgedFeature"})
    with pytest.raises(ValueError, match="invalid Vec2"):
        api.project_vec2_from_raw("not coordinates")
    with pytest.raises(ValueError):
        api.decode_project_feature("CircleFeature", {
            "diameter": 12, "anchor": "UNKNOWN_ANCHOR",
        })


def test_project_gui_codec_is_only_public_engine_alias_not_geometry_constructor():
    src = Path(project.__file__).read_text(encoding="utf-8")
    assert "from ae_engine.sheetmetal_features import" not in src
    assert "from ae_engine.sheetmetal_geometry import" not in src
    assert "def _decode_feature(" not in src
    tree = ast.parse(inspect.getsource(codec))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0:
            assert not (node.module or "").startswith(("phase6_", "gui_modules", "tkinter"))
        if isinstance(node, ast.Import):
            assert all(not item.name.startswith(("phase6_", "gui_modules", "tkinter")) for item in node.names)
