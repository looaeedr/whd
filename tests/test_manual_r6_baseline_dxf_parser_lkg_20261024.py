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

        with pytest.raises(OSError):
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
    with pytest.raises(OSError):
        load_baseline_dxf_source_with_status(
            str(path), allow_unverified_source=True
        )


@pytest.mark.parametrize("allow_preview", [False, True])
def test_r6_structurally_invalid_dxf_parser_error_stays_source_scoped(
    tmp_path, monkeypatch, allow_preview
):
    # A text file rejected at ezdxf's DXF signature preflight raises OSError.
    # Exercise the distinct DXF parser failure explicitly: a valid file path
    # which fails later inside its DXF structure reader.
    path = tmp_path / "parser-failure.dxf"
    ezdxf.new().saveas(str(path))
    normalized = os.path.abspath(str(path))
    previous = object()
    _BASELINE_DXF_LAST_GOOD[normalized] = previous
    current_key = baseline_source_fingerprint(str(path))

    def fail_parser(_path):
        assert os.path.abspath(_path) == normalized
        raise ezdxf.DXFStructureError("corrupt group-code structure")

    monkeypatch.setattr(ezdxf, "readfile", fail_parser)
    try:
        if allow_preview:
            source, status = load_baseline_dxf_source_with_status(
                str(path), allow_unverified_source=True
            )
            assert source is previous
            assert status == BASELINE_SOURCE_UNVERIFIED
            assert current_key not in _BASELINE_DXF_SOURCE_CACHE
        else:
            with pytest.raises(ezdxf.DXFStructureError, match="corrupt group-code structure"):
                load_baseline_dxf_source_with_status(
                    str(path), allow_unverified_source=False
                )
    finally:
        _BASELINE_DXF_LAST_GOOD.pop(normalized, None)


def test_r6_parser_failure_without_lkg_keeps_failing(tmp_path, monkeypatch):
    path = tmp_path / "unrecoverable-parser.dxf"
    ezdxf.new().saveas(str(path))

    def fail_parser(_path):
        raise ezdxf.DXFStructureError("missing structural group")

    monkeypatch.setattr(ezdxf, "readfile", fail_parser)
    with pytest.raises(ezdxf.DXFStructureError, match="missing structural group"):
        load_baseline_dxf_source_with_status(
            str(path), allow_unverified_source=True
        )
