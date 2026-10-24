"""R6 baseline DXF parse errors: LKG is PREVIEW-only, never certified truth."""
import os

import ezdxf
import pytest

from ae_engine.baseline_source import (
    BASELINE_SOURCE_UNVERIFIED,
    BASELINE_SOURCE_VERIFIED,
    _BASELINE_DXF_LAST_GOOD,
    _BASELINE_DXF_SOURCE_CACHE,
    baseline_source_fingerprint,
    load_baseline_dxf_source_with_status,
)


def test_r6_corrupt_dxf_with_last_good_falls_back_only_for_unverified_preview(tmp_path):
    path = tmp_path / "damaged-source.dxf"
    path.write_text("NOT A VALID DXF\n0\nINVALID\n", encoding="utf-8")
    normalized = os.path.abspath(str(path))
    last_good = object()
    assert normalized not in _BASELINE_DXF_LAST_GOOD
    _BASELINE_DXF_LAST_GOOD[normalized] = last_good
    try:
        current_key = baseline_source_fingerprint(str(path))
        parsed, status = load_baseline_dxf_source_with_status(
            str(path), allow_unverified_source=True
        )
        assert parsed is last_good
        assert status == BASELINE_SOURCE_UNVERIFIED
        assert current_key not in _BASELINE_DXF_SOURCE_CACHE

        with pytest.raises(ezdxf.DXFError):
            load_baseline_dxf_source_with_status(
                str(path), allow_unverified_source=False
            )

        # Repaired on-disk truth supersedes the old preview cache.
        ezdxf.new().saveas(str(path))
        verified, verified_status = load_baseline_dxf_source_with_status(
            str(path), allow_unverified_source=True
        )
        assert verified_status == BASELINE_SOURCE_VERIFIED
        assert verified is not last_good
        assert _BASELINE_DXF_LAST_GOOD[normalized] is verified
    finally:
        _BASELINE_DXF_LAST_GOOD.pop(normalized, None)


def test_r6_corrupt_dxf_without_last_good_does_not_invent_a_preview(tmp_path):
    path = tmp_path / "no-source.dxf"
    path.write_text("NOT A VALID DXF\n0\nINVALID\n", encoding="utf-8")
    with pytest.raises(ezdxf.DXFError):
        load_baseline_dxf_source_with_status(
            str(path), allow_unverified_source=True
        )
