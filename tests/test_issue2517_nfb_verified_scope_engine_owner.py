# -*- coding: utf-8 -*-
"""#2517 Engine owns Receiving CSV-V5 physical scope and historic proof."""
from dataclasses import FrozenInstanceError
from pathlib import Path
import inspect

import pytest

from ae_engine import manufacturing_api
import ae_engine.receiving_nfb_verified_scope as owner
from gui_modules.application import receiving_nfb_verified_scope_display as adapter
from gui_modules.application.receiving_nfb_pair_partial_export_action import (
    _verified_csv_v5_export_scope, NfbCsvPairedPartOnlyDxf,
)
from tests.test_issue1502_current_csv_original_pair_dxf import _current, _scene, _export


def test_real_csv_v5_pair_receipt_proof_public_engine_and_gui_delegate(tmp_path):
    snapshot = _current()
    receipt = _export(snapshot, _scene(snapshot), tmp_path)
    assert type(receipt) is NfbCsvPairedPartOnlyDxf
    assert type(receipt.verified_v5_scope) is manufacturing_api.NfbCsvVerifiedExportScope
    from ae_engine.receiving_nfb_committed_final_scene import _submitted_csv_holes
    assert receipt.verified_v5_scope == manufacturing_api.resolve_verified_csv_v5_export_scope(
        snapshot, *_submitted_csv_holes(snapshot)
    )
    proof = adapter.capture_verified_v5_pair_display(snapshot, receipt)
    assert type(proof) is manufacturing_api.NfbCsvVerifiedSelectorProof
    assert proof.scope == receipt.verified_v5_scope
    assert proof.generated_output_shas and len(proof.generated_output_shas) == 2
    label = manufacturing_api.verified_csv_v5_operator_label(
        proof, snapshot, "士林", receipt.verified_v5_scope.sites[0].model_ref
    )
    assert label and "僅本次真實出圖已驗證" in label
    assert adapter.verified_v5_model_operator_label(
        proof, snapshot, "士林", receipt.verified_v5_scope.sites[0].model_ref,
    ) == label
    with pytest.raises(FrozenInstanceError):
        proof.snapshot_sha256 = "forged"


def test_untested_project_or_output_cannot_create_reusable_label(tmp_path):
    snapshot = _current()
    receipt = _export(snapshot, _scene(snapshot), tmp_path)
    paths = (receipt.inner_door_path, receipt.base_plate_path)
    assert manufacturing_api.capture_verified_csv_v5_pair_display_proof(
        snapshot, receipt.verified_v5_scope, paths, ("unrelated-physical-hole",),
    ) is None
    assert manufacturing_api.capture_verified_csv_v5_pair_display_proof(
        snapshot, receipt.verified_v5_scope, (paths[0], paths[0]), receipt.source_hole_ids,
    ) is None
    assert adapter.capture_verified_v5_pair_display(snapshot, object()) is None
    assert owner.verified_csv_v5_operator_label(
        object(), snapshot, "士林", receipt.verified_v5_scope.sites[0].model_ref,
    ) is None
    proof = adapter.capture_verified_v5_pair_display(snapshot, receipt)
    assert proof is not None
    changed = dict(snapshot, w=750.)
    assert manufacturing_api.verified_csv_v5_operator_label(
        proof, changed, "士林", receipt.verified_v5_scope.sites[0].model_ref,
    ) is None
    base = Path(receipt.base_plate_path)
    base.write_bytes(base.read_bytes()+b"\n# changed output")
    assert manufacturing_api.verified_csv_v5_operator_label(
        proof, snapshot, "士林", receipt.verified_v5_scope.sites[0].model_ref,
    ) is None


def test_gui_adapter_never_parses_csv_or_sha_and_engine_has_no_gui_reverse_import():
    source = inspect.getsource(adapter)
    assert "manufacturing_api.capture_verified_csv_v5_pair_display_proof(" in source
    assert "manufacturing_api.verified_csv_v5_operator_label(" in source
    for forbidden in ("sha256(", "json.dumps(", "_submitted_csv_holes(",
                      "brand_csv_path(", "_verified_csv_v5_export_scope("):
        assert forbidden not in source
    engine = inspect.getsource(owner)
    assert "gui_modules" not in engine
    assert "phase6_" not in engine
