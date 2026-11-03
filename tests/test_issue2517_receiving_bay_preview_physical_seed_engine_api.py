"""#2517: Receiving Bay physical Fold/Joint/structure previews consume Engine."""
from copy import deepcopy
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.receiving_bay_preview_source import (
    ReceivingBayPreviewPhysicalSeed,
    project_receiving_bay_preview_physical_seed as owner,
)
from ae_engine.receiving_layout import (
    new_receiving_layout, resize_receiving_bays, update_receiving_bay,
    receiving_bay_joint_face_features,
)


def _snapshot():
    layout = resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=4,
    )
    layout = update_receiving_bay(
        layout, set_index=0, bay_index=1, width=900, height=1700, depth=400,
    )
    return {"model": "受電箱", "active_mode": "set_bay", "t": 2, "fw": 29,
            "receiving_layout": layout,
            "box_body_structure": {"active_type": "integral"}}


@pytest.mark.parametrize("bay", [0, 1, 2, 3])
def test_real_four_bay_profiles_and_joint_faces_match_canonical_engine(bay):
    source = _snapshot()
    original = deepcopy(source)
    inputs = api.project_receiving_bay_preview_operator_inputs(
        source, {"t": 2, "fw": 29}, set_index=0, bay_index=bay,
    )
    selected = inputs.snapshot
    saved = api.build_box_body_fold_profile(selected)
    before = deepcopy(saved)
    projection = api.project_receiving_bay_preview_physical_seed(
        selected, set_index=0, bay_index=bay,
        existing_box_body_profile=saved, existing_box_body_faces={},
    )
    assert isinstance(projection, ReceivingBayPreviewPhysicalSeed)
    assert projection == owner(
        selected, set_index=0, bay_index=bay,
        existing_box_body_profile=saved, existing_box_body_faces={},
    )
    assert projection.box_body_profile == api.merge_box_body_fold_profile(saved, selected)
    assert projection.endcap_profiles == {
        key: api.build_endcap_xy_fold_profiles(selected, part_key=key)
        for key in ("head", "tail")
    }
    assert projection.box_body_joint_faces == receiving_bay_joint_face_features(
        selected["receiving_layout"], set_index=0, bay_index=bay,
        thickness=2., frame_width=29., existing={},
    )
    assert source == original and saved == before


def test_box_body_structure_workspace_authority_wins_saved_root():
    snapshot = api.project_receiving_bay_preview_operator_inputs(
        _snapshot(), {"t": 2, "fw": 29}, set_index=0, bay_index=0,
    ).snapshot
    snapshot["workspace"] = {
        "box_body_structure": {"active_type": "three_piece_side_back_split"}
    }
    projection = api.project_receiving_bay_preview_physical_seed(
        snapshot, set_index=0, bay_index=0,
    )
    assert projection.box_body_structure_state == {
        "active_type": "three_piece_side_back_split",
    }


@pytest.mark.parametrize("model,mode", [
    ("金庫型", "set_bay"), ("unsupported", "set_bay"),
    ("受電箱", "quantity"), ("RECEIVING", "quantity"),
])
def test_unrelated_family_or_non_bay_mode_cannot_get_a_receiving_seed(model, mode):
    snapshot = {**_snapshot(), "model": model, "active_mode": mode}
    with pytest.raises(ValueError, match="RECEIVING_BAY_PREVIEW_"):
        api.project_receiving_bay_preview_physical_seed(
            snapshot, set_index=0, bay_index=0,
        )


def test_invalid_bay_must_not_receive_joint_face_features():
    inputs = api.project_receiving_bay_preview_operator_inputs(
        _snapshot(), {"t": 2, "fw": 29}, set_index=0, bay_index=0,
    )
    with pytest.raises(IndexError):
        api.project_receiving_bay_preview_physical_seed(
            inputs.snapshot, set_index=0, bay_index=9,
        )


def test_gui_has_no_duplicate_receiving_fold_joint_or_structure_authority():
    root = Path(__file__).resolve().parents[1]
    text = (root /
            "gui_modules/application/fold_designer_composition_receiving.py"
    ).read_text(encoding="utf-8")
    body = text.split("def receiving_bay_preview_request(", 1)[1].split(
        "def receiving_layer_preview_payload(", 1,
    )[0]
    assert "manufacturing_api.project_receiving_bay_preview_physical_seed(" in body
    for forbidden in (
        "merge_box_body_profile(", "build_endcap_xy_profiles(",
        "receiving_bay_joint_face_features(",
        'snapshot.get("workspace", {}).get("box_body_structure"',
        'thickness=float(snapshot.get("t", 2)), frame_width=float(snapshot.get("fw", 29))',
    ):
        assert forbidden not in body
    engine = (root / "ae_engine/receiving_bay_preview_source.py").read_text(
        encoding="utf-8",
    )
    assert "from phase6_" not in engine and "from gui_modules" not in engine
