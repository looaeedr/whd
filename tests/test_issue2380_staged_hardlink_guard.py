# -*- coding: utf-8 -*-
"""#2380: previously attested stage cannot become a customer-facing hardlink."""
from __future__ import annotations

import os

import pytest

from integration_cli.batch_commit_journal import _proof_equals_expected
from integration_cli.prepare_evidence import PrepareEvidenceError
from test_issue2378_request_canonical import _w06_committing_context


@pytest.mark.parametrize("link_after_arm", [False, True])
@pytest.mark.parametrize("physical_index", [0, 1])
def test_attested_stage_cannot_gain_hardlink_before_customer_replace(
    tmp_path, link_after_arm, physical_index,
):
    store, output, old, first, second, request, ledger, journal, before = (
        _w06_committing_context(tmp_path)
    )
    if link_after_arm:
        plan = journal.arm(request)
    stage = (first, second)[physical_index]
    # Introduce an alias AFTER the immutable snapshot. Content, size,
    # path and mtime all remain unchanged, so hash-only rechecks pass.
    alias = tmp_path / "untrusted-hardlink.dxf"
    try:
        os.link(stage, alias)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"filesystem has no usable hardlink support: {exc}")
    assert stage.stat().st_nlink >= 2
    if link_after_arm:
        proof = plan["items"][physical_index]["staged"]
        assert not _proof_equals_expected(stage, proof, require_single_link=True)
    with pytest.raises(PrepareEvidenceError) as caught:
        (journal.apply(request) if link_after_arm else journal.arm(request))
    assert caught.value.code in {"WHD_JOB_STAGING_STALE", "WHD_JOB_RECOVERY_REQUIRED"}
    assert (old.read_bytes(), old.stat().st_mtime_ns) == before
    assert not (output / "part-two.dxf").exists()
    assert first.exists() and second.exists()
    assert alias.exists()
    if link_after_arm:
        assert journal._read(request)[0] == "armed"
