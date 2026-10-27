# -*- coding: utf-8 -*-
"""#1490: real CSV Quantity original complete export cannot silently omit PAD."""
from pathlib import Path
import ezdxf
import pytest
from phase6_manufacturing_contracts import thaw_manufacturing_value
from ae_engine.receiving_nfb_pad_pair_manufacturing import (
    verified_pad_base_physical_sheets,
)
from tests.test_issue1502_quantity_current_csv_full_batch import (
    _batch, _export, _quantity,
)


def test_both_saved_versions_full_selection_include_genuine_pad_q_and_dxf(tmp_path):
    batch = _batch()
    demands = []
    for v, (_, _, request) in zip(batch.versions, batch.requests):
        records, parts = verified_pad_base_physical_sheets(
            thaw_manufacturing_value(request.input_snapshot),
            v.geometry.parts, allow_empty=True,
        )
        assert len(records) == 1
        assert records[0].physical_id in parts
        assert len(parts[records[0].physical_id].fold_guides) == 2
        demands.append(v.piece_count)
    assert demands == [3, 2]
    outputs = _export(batch, tmp_path)
    assert outputs
    actual_q = 0
    for path in outputs.values():
        assert Path(path).is_file()
        scene = ezdxf.readfile(path).modelspace()
        assert len(scene) > 0
        actual_q += int(_quantity(path)[1:])
    # Genuine per-version selected sheets + two EARs per box + one PAD per box.
    selected_q = sum(d.quantity for d in batch.demands)
    assert actual_q == selected_q + 2 * sum(demands) + sum(demands)


def test_quantity_second_version_pad_proof_failure_is_atomic(tmp_path, monkeypatch):
    import ae_engine.receiving_nfb_pad_pair_manufacturing as source
    real = source.verified_pad_base_physical_sheets
    calls = []

    def fail_second(*args, **kwargs):
        calls.append(True)
        if len(calls) == 2:
            raise ValueError("PAD_SOURCE_SECOND_VERSION_STALE")
        return real(*args, **kwargs)

    monkeypatch.setattr(source, "verified_pad_base_physical_sheets", fail_second)
    folder = tmp_path / "failed"
    with pytest.raises(ValueError, match="PAD_SOURCE_SECOND_VERSION_STALE"):
        _export(_batch(), folder)
    assert len(calls) == 2
    assert not folder.exists()


def test_quantity_partial_without_box_is_source_legal_no_pad_required(tmp_path, monkeypatch):
    import ae_engine.receiving_nfb_pad_pair_manufacturing as source
    def forbid(*args, **kwargs):
        raise AssertionError("PARTIAL_SELECTION_MUST_NOT_REQUIRE_PAD")
    monkeypatch.setattr(source, "verified_pad_base_physical_sheets", forbid)
    folder = tmp_path / "partial"
    paths = _export(_batch(), folder, box_body=False, head=False)
    assert paths and all(Path(p).exists() for p in paths.values())


def test_two_distinct_bays_complete_selection_contains_exact_two_pad_dxfs(tmp_path):
    from tests.test_issue1502_current_csv_multi_bay_once import _multi, _run
    source = _multi()
    results, selected_bays = _run(source, tmp_path)
    assert selected_bays == [(0, 0), (0, 1)]
    pad_files = [Path(p) for p in results.values() if "nfb_pad" in Path(p).name]
    assert len(pad_files) == 2
    assert len({f.name for f in pad_files}) == 2
    for file in pad_files:
        scene = ezdxf.readfile(file).modelspace()
        assert sum(x.dxf.layer == "BEND" for x in scene) == 2
        assert sum(x.dxf.layer == "CUTTING" for x in scene) == 5


def test_multibay_second_bay_pad_proof_stale_aborts_without_any_files(tmp_path, monkeypatch):
    import ae_engine.receiving_nfb_pad_pair_manufacturing as source
    from tests.test_issue1502_current_csv_multi_bay_once import _multi, _run
    real = source.verified_pad_base_physical_sheets
    calls = []

    def bad_second(*args, **kwargs):
        calls.append(True)
        if len(calls) == 2:
            raise ValueError("PAD_SECOND_BAY_SOURCE_STALE")
        return real(*args, **kwargs)

    monkeypatch.setattr(source, "verified_pad_base_physical_sheets", bad_second)
    out = tmp_path / "invalid"
    with pytest.raises(ValueError, match="PAD_SECOND_BAY_SOURCE_STALE"):
        _run(_multi(), out)
    assert len(calls) == 2
    assert not out.exists()


def test_multibay_partial_base_selection_never_claims_full_pad(tmp_path, monkeypatch):
    import ae_engine.receiving_nfb_pad_pair_manufacturing as source
    from tests.test_issue1502_current_csv_multi_bay_once import _multi, _run
    from tests.test_issue1502_single_button_full_csv_receiving_export import _flags

    def forbid(*args, **kwargs):
        raise AssertionError("MULTIBAY_PARTIAL_SELECTION_MUST_NOT_REQUIRE_PAD")

    monkeypatch.setattr(source, "verified_pad_base_physical_sheets", forbid)
    folder = tmp_path / "partial"
    outputs, selected_bays = _run(
        _multi(), folder, flags=_flags(box_body=False, head=False),
    )
    assert selected_bays == [(0, 0), (0, 1)]
    assert outputs and all(Path(p).exists() for p in outputs.values())
    assert not any("nfb_pad" in Path(p).name for p in outputs.values())
