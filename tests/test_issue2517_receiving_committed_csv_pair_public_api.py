# -*- coding: utf-8 -*-
"""#2517: GUI must not own committed Receiving CSV/NFB physical-source roles."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from ae_engine import receiving_nfb_committed_final_scene as engine


@pytest.mark.parametrize(
    ("layer_count", "physical_sources", "expected"),
    [
        (1, {0: "base_plate"}, 1),
        (1, {0: "base_plate:nfb_layer:0"}, None),
        (1, {0: "base_plate", 1: "base_plate:nfb_layer:1"}, None),
        (2, {0: "base_plate:nfb_layer:0", 1: "base_plate:nfb_layer:1"}, 2),
        (2, {0: "base_plate", 1: "base_plate:nfb_layer:1"}, None),
        (2, {0: "base_plate:nfb_layer:0"}, None),
        (3, {0: "base_plate:nfb_layer:0"}, None),
    ],
)
def test_public_projection_requires_real_engine_source_role_owners(
    monkeypatch, layer_count, physical_sources, expected,
):
    snapshot = {"model": "受電箱", "nfb_config_submitted": True}
    holes = (SimpleNamespace(layer_count=layer_count),)
    observed = []

    def canonical_source(received):
        assert received is snapshot
        observed.append("csv")
        return ("inner_door:confirmed", holes)

    def original_specs(received, submitted_holes):
        assert received is snapshot
        assert submitted_holes is holes
        observed.append("base")
        return {
            index: SimpleNamespace(physical_id=part_id)
            for index, part_id in physical_sources.items()
        }

    monkeypatch.setattr(engine, "_submitted_csv_holes", canonical_source)
    monkeypatch.setattr(engine, "_existing_source_specs", original_specs)
    assert manufacturing_api.project_receiving_committed_csv_nfb_pair_layer_count(
        snapshot,
    ) == expected
    assert observed == ["csv", "base"]


def test_public_projection_legacy_source_skips_base_spec_resolution(monkeypatch):
    seen = []

    def legacy_source(snapshot):
        seen.append(snapshot)
        return ()

    monkeypatch.setattr(engine, "_submitted_csv_holes", legacy_source)
    monkeypatch.setattr(
        engine, "_existing_source_specs",
        lambda *_args: pytest.fail("legacy must not fabricate a CSV base source"),
    )
    snapshot = {"model": "受電箱"}
    assert manufacturing_api.project_receiving_committed_csv_nfb_pair_layer_count(
        snapshot,
    ) is None
    assert seen == [snapshot]


def test_public_projection_propagates_untrusted_committed_source_error():
    with pytest.raises(
        ValueError, match="NFB_COMMITTED_CSV_SUBMITTED_CONFIG_INVALID",
    ):
        manufacturing_api.project_receiving_committed_csv_nfb_pair_layer_count({
            "model": "受電箱",
            "nfb_config_submitted": True,
        })


def test_receiving_gui_uses_public_engine_only_for_csv_pair_source_roles():
    root = Path(__file__).resolve().parents[1]
    src = (
        root / "gui_modules/application/fold_designer_composition_receiving.py"
    ).read_text(encoding="utf-8")
    start = src.index("        def current_csv_pair_source(")
    end = src.index("        def state(set_index, bay_index,", start)
    source_and_export = src[start:end]
    assert source_and_export.count(
        "manufacturing_api.project_receiving_committed_csv_nfb_pair_layer_count("
    ) == 2
    assert "_submitted_csv_holes" not in source_and_export
    assert "_existing_source_specs" not in source_and_export
    assert "base_plate:nfb_layer:" not in source_and_export
    assert "from ae_engine.receiving_nfb_committed_final_scene import" not in src
    assert (
        manufacturing_api.project_receiving_committed_csv_nfb_pair_layer_count
        is engine.project_receiving_committed_csv_nfb_pair_layer_count
    )
