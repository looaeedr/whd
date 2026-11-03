"""#2517 public Engine owns all Receiving physical 2D render source choices."""
from types import SimpleNamespace
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
from tests.test_issue1502_source_derived_center_base import _source_snapshot
from tests.test_receiving_nfb_pad_delivery import installed_pair


def test_committed_one_tier_source_resolves_real_cached_or_lazy_render_without_inventing():
    snapshot = _source_snapshot(shallow="2P400")
    material = SimpleNamespace(unfolded_topology=object())
    geometry = SimpleNamespace(parts=(
        SimpleNamespace(part_key="base_plate", render_data=material),
    ))
    calls = []
    def resolver():
        calls.append("solve")
        return geometry
    direct = api.resolve_operator_receiving_base_2d_source(
        "base_plate", {}, snapshot,
        cached_geometry=geometry, resolve_geometry=resolver,
    )
    assert direct is material and not calls
    assert api.resolve_operator_receiving_base_2d_source(
        "base_plate", {}, snapshot, resolve_geometry=resolver,
    ) is material
    assert calls == ["solve"]
    snapshot["model"] = "receiving"
    assert api.resolve_operator_receiving_base_2d_source(
        "base_plate", {}, snapshot, cached_geometry=geometry,
    ) is material
    assert api.resolve_operator_receiving_base_2d_source(
        "base_plate", {"_use_committed_relief": False},
        snapshot, cached_geometry=geometry,
    ) is None


def test_nfb_tier_must_be_real_submitted_receiving_physical_part():
    material = SimpleNamespace(unfolded_topology=object())
    scene = SimpleNamespace(parts=(
        SimpleNamespace(part_key="base_plate:nfb_layer:1", render_data=material),
    ))
    current = {"model": "受電箱", "nfb_config_submitted": True}
    assert api.resolve_operator_receiving_base_2d_source(
        "base_plate:nfb_layer:1", {}, current, cached_geometry=scene,
    ) is material
    with pytest.raises(ValueError, match="PART_ID_INVALID"):
        api.resolve_operator_receiving_base_2d_source(
            "base_plate:nfb_layer:5", {}, current, cached_geometry=scene,
        )
    with pytest.raises(ValueError, match="NOT_SUBMITTED"):
        api.resolve_operator_receiving_base_2d_source(
            "base_plate:nfb_layer:1", {}, {**current,"model":"金庫型"},
            cached_geometry=scene,
        )
    with pytest.raises(ValueError, match="SOURCE_UNAVAILABLE"):
        api.resolve_operator_receiving_base_2d_source(
            "base_plate:nfb_layer:0", {}, current, cached_geometry=scene,
        )
    with pytest.raises(ValueError, match="PHYSICAL_PART_MISSING"):
        api.resolve_operator_receiving_base_2d_source(
            "base_plate:nfb_layer:0", {}, current, cached_geometry=scene,
            resolve_geometry=lambda: scene,
        )


def test_committed_v5_pad_keeps_original_nonproduction_render_source():
    snapshot, _ = installed_pair()
    from ae_engine.receiving_nfb_pad_operator_parts import committed_nfb_pad_draft_parts
    pad, = committed_nfb_pad_draft_parts(snapshot)
    assert api.resolve_operator_receiving_pad_2d_source(
        pad.part_id, snapshot,
    ) is not None
    assert api.resolve_operator_receiving_pad_2d_source(
        pad.part_id, snapshot,
    ).metadata["nfb_deferred_manufacturing_role"] == "PAD"
    with pytest.raises(ValueError, match="STALE_OR_UNAUTHORIZED"):
        api.resolve_operator_receiving_pad_2d_source("nfb_pad:fake", snapshot)
    with pytest.raises(ValueError, match="SNAPSHOT_UNAVAILABLE"):
        api.resolve_operator_receiving_pad_2d_source("nfb_pad:fake", None)


def test_fixing_cross_bay_ownership_and_unconfigured_family_fail_closed():
    from ae_engine.receiving_layout import (
        new_receiving_layout, resize_receiving_bays,
        project_receiving_bay_legacy_aliases,
    )
    layout = resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=2,
    )
    source = project_receiving_bay_legacy_aliases(
        {"model":"受電箱","t":2,"receiving_layout":layout},
        set_index=0, bay_index=1,
    )
    malformed = {**source, "w": source["w"] + 1}
    with pytest.raises(ValueError, match="BASE_FIXING_PLATE_BAY_SOURCE_DRIFT:w"):
        api.resolve_operator_receiving_fixing_2d_source(
            "base_plate:fixing_plate:left", malformed,
        )
    with pytest.raises(ValueError, match="NOT_AUTHORIZED"):
        api.resolve_operator_receiving_fixing_2d_source(
            "base_plate:fixing_plate:left",
            {"model":"金庫型", "w":800,"t":2},
        )


def test_gui_uses_public_sources_not_internal_nfb_owner_or_part_identity_rules():
    source = (Path(__file__).resolve().parents[1] /
              "gui_modules/application/fold_designer_manufacturing_projection.py").read_text(encoding="utf-8")
    start = source.index("def _query_receiving_resolved_base_render_data(")
    # The original inline part-key conditional was replaced by Engine-owned
    # plan_operator_manufacturing_part_source routing. Cover the entire current
    # public 2D source dispatch instead of relying on a retired source marker.
    end = source.index("def _payload_topology_context(", start)
    excerpt = source[start:end]
    for api_name in (
        "resolve_operator_receiving_base_2d_source",
        "resolve_operator_receiving_pad_2d_source",
        "resolve_operator_receiving_fixing_2d_source",
    ):
        assert "manufacturing_api." + api_name in excerpt
    assert "from ae_engine.receiving_base_plate_config import" not in excerpt
    assert "from ae_engine.receiving_base_fixing_plate import" not in excerpt
    assert "from ae_engine.receiving_nfb_pad_operator_parts import" not in excerpt
    assert "BASE_FIXING_PLATE_BAY_SOURCE_DRIFT:" not in excerpt
    assert "re.fullmatch(" not in excerpt
    engine = (Path(__file__).resolve().parents[1] /
              "ae_engine/operator_receiving_physical_2d.py").read_text(encoding="utf-8")
    assert "from gui_modules" not in engine
    assert "from phase6_" not in engine
