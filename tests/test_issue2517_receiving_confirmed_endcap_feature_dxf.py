# -*- coding: utf-8 -*-
"""#2517 trusted EndCap source Features survive canonical manufactured DXF."""
from pathlib import Path
import ezdxf
import pytest
from ae_engine import manufacturing_api
from ae_engine.contracts import ManufacturingContext, ResolvedManufacturingGeometry
from ae_engine.integration_api import (
    ManufacturingResolvedBayInput, ManufacturingSourceIdentity,
    export_verified_resolved_integration_bays,
)
from ae_engine.sheetmetal_feature_core import CircleFeature, RectFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2

ROOT = Path(__file__).resolve().parents[1]
SOURCE = {"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0}


def _circle(x=400.0):
    return CircleFeature(9.6, FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                         Vec2(x, 100.0), layer="CUTTING", source_type="verified-dxf")


def _bay(features, **kwargs):
    data = dict(family="受電箱", source=ManufacturingSourceIdentity(
        "P1", "verified-revision", "Set1", "Bay1"),
        source_dimensions_mm=SOURCE, operator_confirmation="fresh_family_confirmed",
        confirmed_endcap_features=features)
    data.update(kwargs)
    return ManufacturingResolvedBayInput(**data)


def test_verified_head_feature_is_part_of_real_reopened_dxf(tmp_path):
    f = _circle()
    raw = {"head": [f], "tail": []}
    specs = manufacturing_api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="fresh_family_confirmed", confirmed_endcap_features=raw)
    assert specs[1][1].holes == (f,) and specs[2][1].holes == ()
    raw["head"].clear()
    assert specs[1][1].holes == (f,)
    checked = []
    result = export_verified_resolved_integration_bays(
        (_bay({"head": (f,)}),), tmp_path / "export",
        context=ManufacturingContext(resource_root=ROOT),
        pre_commit_guard=lambda: checked.append("source-current"))
    assert checked == ["source-current", "source-current"]
    assert result.physical_dxf_roundtrip_verified and len(result.output_files) == 5
    head = [path for path in result.output_files.values() if "head" in Path(path).stem]
    assert len(head) == 1
    circles = [e for e in ezdxf.readfile(head[0]).modelspace()
               if e.dxftype() == "CIRCLE" and e.dxf.layer == "CUTTING"]
    assert any(abs(e.dxf.radius - 4.8) < 1e-6 for e in circles)


@pytest.mark.parametrize("bad", [
    {"P1": (_circle(),)},
    {"head": {"circle": _circle()}},
    {"head": ({"diameter": 9.6, "x": 400},)},
    {"head": (_circle(float("nan")),)},
    {"head": (_circle(float("inf")),)},
    {"head": (_circle(),), "door": ()},
    {"tail": (RectFeature(0, 10, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(30, 40)),)},
    {"head": (CircleFeature(9.6, FeatureAnchor.PANEL_CENTER, Vec2(0, 0)),)},
    {"head": (CircleFeature(9.6, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(400, 100), layer="BLIND_HOLE"),)},
])
def test_invalid_source_feature_cannot_write_dxf(tmp_path, bad):
    with pytest.raises(ValueError, match="RECEIVING_ENDCAP_SOURCE_FEATURES_INVALID"):
        export_verified_resolved_integration_bays(
            (_bay(bad),), tmp_path / "blocked", pre_commit_guard=lambda: None,
            context=ManufacturingContext(resource_root=ROOT))
    assert not (tmp_path / "blocked").exists()


def test_source_features_are_not_manufacturing_confirmation(tmp_path):
    with pytest.raises(ValueError, match="RECEIVING_OPERATOR_CONFIRMATION_REQUIRED"):
        export_verified_resolved_integration_bays(
            (_bay({"head": (_circle(),)}, operator_confirmation=None),),
            tmp_path / "blocked", pre_commit_guard=lambda: None)
    with pytest.raises(ValueError, match="RECEIVING_AMBIGUOUS_MANUFACTURING_INPUT"):
        export_verified_resolved_integration_bays(
            (_bay({"head": (_circle(),)}, resolved_geometry=ResolvedManufacturingGeometry(parts=())),),
            tmp_path / "blocked", pre_commit_guard=lambda: None)
    assert not (tmp_path / "blocked").exists()
