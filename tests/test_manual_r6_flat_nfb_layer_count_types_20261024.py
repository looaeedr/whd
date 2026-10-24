"""R6 real flat NFB depth source rejects saved boolean tier counts."""
import pytest

from ae_engine.receiving_nfb_depth_surface_policy import (
    committed_receiving_flat_nfb_depth_mm,
)


def _snapshot(count, hole_count=1, slot_index=0):
    config = {
        "layer_count": count,
        "holes": [{
            "physical_hole_id": "hole-1",
            "model_filename": "legacy-or-v5-ref-required",
            "layer_count": hole_count,
            "slot_index": slot_index,
        }],
    }
    return {
        "receiving_layout": {
            "sets": [{"stable_id": "set-1", "bays": [{
                "stable_id": "bay-1",
                "nfb_config_submitted": True,
                "nfb_config": config,
            }]}]
        },
    }


@pytest.mark.parametrize("bad", [True, False, 1.0, "1", None])
def test_r6_flat_base_rejects_non_integer_top_level_layer_count(bad):
    with pytest.raises(ValueError, match="RECEIVING_FLAT_NFB_MULTIPLE_ROWS"):
        committed_receiving_flat_nfb_depth_mm(_snapshot(bad))


@pytest.mark.parametrize("bad", [True, False, 1.0, "1", None])
def test_r6_flat_base_rejects_non_integer_per_hole_layer_count(bad):
    with pytest.raises(ValueError, match="RECEIVING_FLAT_NFB_MULTIPLE_ROWS"):
        committed_receiving_flat_nfb_depth_mm(_snapshot(1, bad))


def test_r6_flat_base_rejects_boolean_slot_index():
    with pytest.raises(ValueError, match="RECEIVING_FLAT_NFB_MULTIPLE_ROWS"):
        committed_receiving_flat_nfb_depth_mm(_snapshot(1, 1, True))


def test_r6_integer_layer_and_slot_reach_next_explicit_model_gate():
    # This is intentionally *not* a made-up CSV identity. It proves valid
    # count data reaches the existing source-identity hard gate unchanged.
    snap = _snapshot(1, 1, 0)
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]["holes"][0][
        "model_filename"
    ] = ""
    with pytest.raises(ValueError, match="RECEIVING_FLAT_NFB_DIFFERENT_MODELS"):
        committed_receiving_flat_nfb_depth_mm(snap)
