"""#2517: PAD trial CI must consume real current CSV models, never fictitious suffixes."""
from __future__ import annotations

from pathlib import Path

import ezdxf

from ae_engine.receiving_nfb_model_identity import parse_numeric_model_ref
from ae_engine.receiving_nfb_numeric_catalog import model_spec
from ae_engine.receiving_nfb_committed_final_scene import (
    apply_committed_csv_v5_to_canonical_parts,
)
from ae_engine.receiving_nfb_pad_delivery import export_pad_trial_bundle
from tests.test_issue1502_csv_is_only_normal_finalscene_source import _make
from tools.receiving_pad_delivery_receipt import _source_proven_trial_snapshot


def test_pad_trial_uses_registered_source_complete_csv_models():
    snap = _source_proven_trial_snapshot()
    holes = snap["nfb_config"]["holes"]
    assert [h["model_filename"] for h in holes] == [
        "nfbv5:士林:3P400", "nfbv5:士林:100HN-s",
    ]
    for hole in holes:
        identity = parse_numeric_model_ref(hole["model_filename"])
        assert identity is not None and hole["source_brand"] == identity[0]
        spec = model_spec(*identity)
        assert spec is not None and spec.dimensionally_complete
    assert (snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]
            == snap["nfb_config"])


def test_pad_trial_actual_base_and_pad_dxf_reopen_without_mfg_claim(tmp_path):
    snapshot = _source_proven_trial_snapshot()
    installed = apply_committed_csv_v5_to_canonical_parts(
        snapshot, (_make(snapshot),),
    )
    destination = tmp_path / "unreleased-source-joined-trial"
    proof = export_pad_trial_bundle(
        snapshot, installed, destination, piece_count=3,
    )
    assert proof["manufacturing_ready"] is False
    assert proof["do_not_use_for_production"] is True
    assert proof["parts"]
    assert all(part["quantity"] == 3 for part in proof["parts"])
    assert proof["dxf"]
    assert (destination / "BOM_AND_VERIFICATION_NOT_FOR_PRODUCTION.json").is_file()
    for dxf in proof["dxf"]:
        path = destination / dxf["filename"]
        assert path.is_file() and path.suffix == ".dxf"
        assert path.name.startswith("UNRELEASED_")
        assert any(e.dxf.layer == "CUTTING" for e in ezdxf.readfile(path).modelspace())
