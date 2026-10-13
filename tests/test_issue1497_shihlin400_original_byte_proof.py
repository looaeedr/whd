# -*- coding: utf-8 -*-
"""#1497 original Shihlin 400 bytes + Color150 source geometry replay.

CI does not pretend to possess customer DXF; optional exact replay
requires WHD_NFB_ORIGINAL_DXF and WHD_NFB_NUMBERED_DXF. Derived factual
golden remains tracked, never the customer original source bytes.
"""
import hashlib
import json
import os
from pathlib import Path

import pytest


GOLDEN=Path(__file__).parent/"fixtures"/"receiving_nfb_shihlin400_original_identity.json"
PROFILE=Path(__file__).parent/"fixtures"/"receiving_nfb_upper_source_profiles.json"


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_two_original_filenames_have_same_recorded_byte_identity_not_x_approval():
    record=json.loads(GOLDEN.read_text(encoding="utf-8"))
    profile=json.loads(PROFILE.read_text(encoding="utf-8"))["profiles"][0]
    assert record["indexed_name"]==profile["indexed_filename"]
    assert record["download_name"]==record["indexed_name"][:-4]+"(1).dxf"
    assert record["byte_identical"] is True
    assert record["source_sha256"]==profile["source_sha256"]
    assert record["each_size_bytes"]==123089
    assert profile["source_alias_status"]=="SOURCE_ALIAS_SHA256_IDENTICAL"
    assert record["upper_reference"]["dxf_handle"]==profile["upper_handle"]
    assert record["upper_reference"]["width_mm"]==profile["upper_size_mm"][0]
    assert record["upper_reference"]["height_mm"]==profile["upper_size_mm"][1]
    assert record["lower_reference_excluded"]["dxf_handle"]=="597"
    assert record["color_entity_counts"]["150"]==1
    assert sum(record["color_entity_counts"].values())==record["modelspace_entity_count"]
    assert "WORLD_X_POSITION" in record["not_approval"]
    assert "WHOLE_SET_EXPORT" in record["not_approval"]


def test_optional_two_original_dxf_byte_and_upper_handle_replay():
    paths=(os.environ.get("WHD_NFB_ORIGINAL_DXF"),
           os.environ.get("WHD_NFB_NUMBERED_DXF"))
    if not all(paths):
        pytest.skip("true customer source DXFs absent; golden metadata is not E2E")
    import ezdxf
    data=json.loads(GOLDEN.read_text(encoding="utf-8"))
    for name,path in zip((data["indexed_name"],data["download_name"]),paths):
        source=Path(path)
        assert source.is_file() and source.name==name
        assert source.stat().st_size==data["each_size_bytes"]
        assert _sha(source)==data["source_sha256"]
        drawing=ezdxf.readfile(source)
        entities=list(drawing.modelspace())
        assert len(entities)==data["modelspace_entity_count"]
        upper=drawing.entitydb[data["upper_reference"]["dxf_handle"]]
        assert upper.dxftype()=="LWPOLYLINE" and upper.closed
        assert upper.dxf.color==150
        xy=list(upper.get_points("xy"))
        width=max(p[0] for p in xy)-min(p[0] for p in xy)
        height=max(p[1] for p in xy)-min(p[1] for p in xy)
        assert width==pytest.approx(57)
        assert height==pytest.approx(96)
    assert Path(paths[0]).read_bytes()==Path(paths[1]).read_bytes()
