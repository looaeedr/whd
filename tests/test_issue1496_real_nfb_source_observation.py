# -*- coding: utf-8 -*-
"""Genuine customer-supplied NFB #1496 witness, without bundling source DXF.

The witness is a measured JSON record, not a synthetic model certification.
For a local source-file recheck, set WHD_NFB_400_SOURCE_DXF to its actual path;
the real DXF stays outside Git and CI does not falsely claim to read it.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path

import pytest

from ae_engine.receiving_nfb_dxf_source import (
    inspect_nfb_dxf_source,
    resolve_upper_color150_reference,
    place_upper_nfb_point_from_color150,
)

WITNESS = (
    Path(__file__).resolve().parent
    / "fixtures" / "nfb_400_140x257_107_source_observation.json"
)


def _witness():
    return json.loads(WITNESS.read_text(encoding="utf-8"))


def test_source_witness_has_traceable_region_partition_and_no_false_certs():
    witness = _witness()
    assert witness["schema"] == "WHD_NFB_SOURCE_OBSERVATION_V1"
    assert witness["sha256"] == (
        "8daecaacacb9683c1436d29aa75fbba85c09d54536b92945fbaad06e049fadf3"
    )
    assert witness["insunits"] == 4
    assert witness["dxf_version"] == "AC1015"
    assert witness["modelspace_entity_count"] == 41
    assert witness["modelspace_insert_count"] == 0
    assert witness["modelspace_layer_counts"] == {"0": 41}
    assert witness["entity_aci_counts"] == {
        "3": 5, "30": 8, "150": 1, "212": 27,
    }
    groups = witness["regions"]
    assert len(groups) == 2
    all_handles = []
    for group in groups.values():
        assert group["status"] == "SOURCE_REGION_CANDIDATE_ONLY"
        assert sum(group["entity_color_counts"].values()) == group["entity_count"]
        assert sum(group["entity_type_counts"].values()) == group["entity_count"]
        assert len(set(group["handles"])) == group["entity_count"]
        all_handles.extend(group["handles"])
    assert len(all_handles) == len(set(all_handles)) == 41
    assert groups["upper_opening_candidate"]["entity_count"] == 13
    assert groups["upper_opening_candidate"]["entity_color_counts"] == {
        "30": 8, "150": 1, "212": 4,
    }
    assert groups["lower_spacer_candidate"]["entity_count"] == 28
    assert groups["lower_spacer_candidate"]["entity_color_counts"] == {
        "3": 5, "212": 23,
    }
    top = witness["upper_color150_rectangle"]
    bottom = witness["lower_color3_envelope"]
    assert top["handle"] in groups["upper_opening_candidate"]["handles"]
    assert bottom["handle"] in groups["lower_spacer_candidate"]["handles"]
    assert top["size_mm"] == [57.0, 96.0]
    assert bottom["size_mm"] == [144.0, 257.0]
    assert top["geometric_bbox_center_mm"] == [3771.967234, 2608.809181]
    assert bottom["geometric_bbox_center_mm"] == [3771.967234, 2223.769181]
    assert round(top["geometric_bbox_center_mm"][1] - bottom["geometric_bbox_center_mm"][1], 6) == 385.04
    approved = witness["user_confirmed_upper_reference"]
    assert approved["reference_handle"] == "585"
    assert approved["reference_color_aci"] == 150
    assert approved["center_rule"] == "CENTER_OF_EXPLICIT_UPPER_COLOR150_CLOSED_RECTANGLE"
    assert approved["owner_parts"] == ["MIDDLE_PLATE", "INNER_DOOR"]
    assert approved["source_reference_confirmed"] is True
    assert approved["lower_region_policy"] == "IGNORE_FOR_THIS_OPERATION"
    assert approved["center_xy_mm"] == [3771.967234, 2608.809181]
    assert approved["rectangle_size_mm"] == [57, 96]
    assert approved["output_manufacturing_ready"] is False
    assert witness["source_main_cutting_pivot_certified"] is False
    assert witness["source_nfb_model_certified"] is False
    assert witness["ready_for_1497_manufacturing"] is False


def test_original_uploaded_dxf_matches_witness_when_explicitly_available():
    source = os.environ.get("WHD_NFB_400_SOURCE_DXF")
    if not source:
        pytest.skip("Original source DXF not bundled in Git; set WHD_NFB_400_SOURCE_DXF")
    path = Path(source)
    expected = _witness()
    assert path.is_file()
    data = path.read_bytes()
    assert len(data) == expected["bytes"]
    assert sha256(data).hexdigest() == expected["sha256"]
    import ezdxf

    doc = ezdxf.readfile(path)
    assert doc.dxfversion == expected["dxf_version"]
    assert doc.header.get("$INSUNITS") == expected["insunits"]
    native = list(doc.modelspace())
    assert len(native) == expected["modelspace_entity_count"]
    assert sum(e.dxftype() == "INSERT" for e in native) == 0
    observed = inspect_nfb_dxf_source(path)
    assert observed.source_sha256 == expected["sha256"]
    assert observed.main_hole_source_id is None
    assert observed.approved_manufacturing_rule_revision is None
    assert len(observed.entities) == 41
    counts = {}
    for e in observed.entities:
        key = str(e.effective_color_aci)
        counts[key] = counts.get(key, 0) + 1
    assert counts == expected["entity_aci_counts"]
    handles = {e.handle_path: e for e in observed.entities}
    for region in expected["regions"].values():
        for handle in region["handles"]:
            assert handle in handles

    top = handles[expected["upper_color150_rectangle"]["handle"]]
    bottom = handles[expected["lower_color3_envelope"]["handle"]]
    assert top.closed and top.effective_color_aci == 150
    assert bottom.closed and bottom.effective_color_aci == 3
    assert len(top.vertices_xy) == 4
    assert len(bottom.vertices_xy) == 20
    for part, actual in [(expected["upper_color150_rectangle"], top),
                         (expected["lower_color3_envelope"], bottom)]:
        xs, ys = [p[0] for p in actual.vertices_xy], [p[1] for p in actual.vertices_xy]
        assert [round(min(xs), 6), round(min(ys), 6),
                round(max(xs), 6), round(max(ys), 6)] == part["bbox_mm"]
    # Recompute the selected physical reference from original DXF geometry,
    # with EXPLICIT upper source identities only. The lower group is ignored.
    upper = expected["regions"]["upper_opening_candidate"]["handles"]
    upper_ids = [handles[handle].source_id for handle in upper]
    reference = resolve_upper_color150_reference(
        observed, upper_source_entity_ids=upper_ids,
    )
    approved = expected["user_confirmed_upper_reference"]
    assert reference.source_entity_id == handles[approved["reference_handle"]].source_id
    assert reference.consumers == ("MIDDLE_PLATE", "INNER_DOOR")
    assert reference.size_mm == pytest.approx(approved["rectangle_size_mm"])
    assert reference.center_xy == pytest.approx(approved["center_xy_mm"], abs=1e-6)
    assert place_upper_nfb_point_from_color150(
        reference.center_xy, reference=reference, target_center_xy=(0, 0),
        rotation_deg=90,
    ) == pytest.approx((0.0, 0.0), abs=1e-8)
    # This still cannot activate NFB model certification or finished CUTTING.
    assert observed.main_hole_source_id is None
    assert expected["ready_for_1497_manufacturing"] is False
