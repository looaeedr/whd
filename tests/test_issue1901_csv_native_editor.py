# -*- coding: utf-8 -*-
"""#1901 CSV → real inner-door FinalScene → original Hole Editor (no DXF)."""
from copy import deepcopy

import pytest

from ae_engine.cabinet_types import policy
from ae_engine.receiving_nfb_csv_editor_features import (
    stage_csv_openings, csv_openings_to_editor_features,
)
from ae_engine.receiving_nfb_model_identity import numeric_model_ref
from ae_engine.receiving_nfb_ui1a import new_nfb_ui1a_draft
from ae_engine.receiving_nfb_v5_configured_inner_door import (
    NfbV5ConfiguredInnerDoorHole, trial_configured_nfb_v5_inner_door_render_data,
)
from phase6_project_file import _decode, _encode
from phase6_receiving_modes import fresh_receiving_mode


def _real_csv_door():
    snap = fresh_receiving_mode("quantity", {
        "w": 800, "h": 1600, "d": 350, "t": 2,
    })
    panel = policy.derive_inner_door_panels(snap)[0]
    model = numeric_model_ref("士林", "2P400")
    slot = NfbV5ConfiguredInnerDoorHole(
        "nfb:quantity:unit1", "士林", model, 0.0, 1, 0,
    )
    trial = trial_configured_nfb_v5_inner_door_render_data(
        snap, panel.inner_door_id, holes=(slot,),
    )
    draft = new_nfb_ui1a_draft(
        set_brand="士林", layer_count=1, model_layers=[[model], []],
    )
    return snap, panel, trial, draft


def test_actual_csv_creates_real_57x96_native_door_profile_without_dxf():
    snapshot, panel, trial, draft = _real_csv_door()
    proof = stage_csv_openings(
        trial, snapshot=snapshot, draft=draft, current_features=(),
    )
    features = csv_openings_to_editor_features(
        proof, snapshot=snapshot, draft=draft, current_features=(),
    )
    assert trial.manufacturing_ready is False  # Editor != production release
    assert len(features) == 1
    hole = features[0]
    assert hole.source_type == "NFB_CSV_SOURCE"
    assert hole.layer == "CUTTING"
    assert hole.anchor.value == "absolute_finished_face"
    assert hole.points[1].x - hole.points[0].x == pytest.approx(57)
    assert hole.points[2].y - hole.points[1].y == pytest.approx(96)
    assert dict(hole.source_params)["model"] == "2P400"
    assert dict(hole.source_params)["part_id"] == panel.stable_id
    assert len(dict(hole.source_params)["csv_sha256"]) == 64
    assert _decode(_encode(features))[0] == hole


def test_csv_proof_rejects_new_draft_existing_holes_and_changed_physical_box():
    snap, _panel, trial, draft = _real_csv_door()
    proof = stage_csv_openings(
        trial, snapshot=snap, draft=draft, current_features=(),
    )
    changed_draft = deepcopy(draft)
    changed_draft["set_brand"] = "東元"
    with pytest.raises(ValueError, match="已變更"):
        csv_openings_to_editor_features(
            proof, snapshot=snap, draft=changed_draft, current_features=(),
        )
    with pytest.raises(ValueError, match="已變更"):
        csv_openings_to_editor_features(
            proof, snapshot=snap, draft=draft, current_features=("old-hole",),
        )
    resized = dict(snap, w=900)
    with pytest.raises(ValueError, match="已變更"):
        csv_openings_to_editor_features(
            proof, snapshot=resized, draft=draft, current_features=(),
        )


def test_csv_bytes_changed_rejects_old_opening(monkeypatch, tmp_path):
    import ae_engine.receiving_nfb_csv_editor_features as bridge
    snap, _panel, trial, draft = _real_csv_door()
    csv = tmp_path / "NFB數值規格.csv"
    csv.write_bytes(b"original-csv")
    monkeypatch.setattr(bridge, "brand_csv_path", lambda brand: csv)
    proof = stage_csv_openings(
        trial, snapshot=snap, draft=draft, current_features=(),
    )
    csv.write_bytes(b"new-csv")
    with pytest.raises(ValueError, match="CSV 已更新"):
        csv_openings_to_editor_features(
            proof, snapshot=snap, draft=draft, current_features=(),
        )

def test_multi_current_set_schema_without_legacy_switch_brand_uses_csv():
    from ae_engine.receiving_layout import project_receiving_bay_legacy_aliases
    from ae_engine.receiving_nfb_ui1b_runtime import preview_current_nfb_v5_ui_draft

    snap = fresh_receiving_mode("set_bay", {
        "w": 800, "h": 1600, "d": 350, "t": 2,
    })
    row = snap["receiving_layout"]["sets"][0]
    assert "switch_brand" not in row  # actual current Set schema
    model = numeric_model_ref("士林", "2P400")
    draft = new_nfb_ui1a_draft(
        set_brand="士林", layer_count=1, model_layers=[[model], []],
    )
    unit = draft["layers"][0]["slots"][0]["unit_id"]
    physical = project_receiving_bay_legacy_aliases(
        snap, set_index=0, bay_index=0, validate_common=False,
    )
    preview = preview_current_nfb_v5_ui_draft(
        draft, layout=snap["receiving_layout"],
        set_index=0, bay_index=0, version_id="inner-door-v1",
        projected_snapshot=physical, world_x_by_unit={unit: 0.0},
    )
    assert len(preview.patterns) == 1
    assert preview.patterns[0].model == "2P400"
    assert preview.patterns[0].opening_uv_mm is not None

