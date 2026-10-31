# -*- coding: utf-8 -*-
"""Windows NTFS st_ino is an unsigned 64-bit identity, SQLite INTEGER signed."""
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest

from integration_cli.job_identity_ledger import (
    _directory_identity, _sqlite_filesystem_id,
)
from integration_cli.prepare_evidence import PrepareEvidenceError


@pytest.mark.parametrize(("raw", "expected"), (
    (1, 1),
    ((1 << 63) - 1, (1 << 63) - 1),
    (1 << 63, -(1 << 63)),
    ((1 << 64) - 1, -1),
))
def test_unsigned_filesystem_id_roundtrips_without_alias_or_sqlite_overflow(raw, expected):
    assert _sqlite_filesystem_id(raw) == expected
    assert raw == (expected & ((1 << 64) - 1))


@pytest.mark.parametrize("invalid", (0, -1, 1 << 64, True, 1.3))
def test_out_of_domain_file_id_fails_closed(invalid):
    with pytest.raises(PrepareEvidenceError, match="filesystem identity"):
        _sqlite_filesystem_id(invalid)


def test_sqlite_lease_with_high_bit_ntfs_inode_preserves_physical_alias_safety(
    tmp_path, monkeypatch,
):
    from integration_cli.job_identity_ledger import DurableJobIdentityLedger
    from integration_cli.request_canonical import compute_wire_request_digest
    from tests.test_issue2380_windows_path_aliases import _export

    store, out = tmp_path / "store", tmp_path / "customer"
    store.mkdir()
    out.mkdir()
    raw_lstat = Path.lstat
    actual = raw_lstat(out)

    def ntfs_high_bit_stat(path):
        item = raw_lstat(path)
        if path == out:
            return SimpleNamespace(
                st_mode=stat.S_IFDIR | 0o700,
                st_dev=int(item.st_dev) if int(item.st_dev) > 0 else 1,
                st_ino=(1 << 63) + 123,
            )
        return item

    monkeypatch.setattr(Path, "lstat", ntfs_high_bit_stat)
    ledger = DurableJobIdentityLedger(store)
    first, second = _export("first-ntfs"), _export("second-ntfs")
    assert ledger.claim(first).state == ledger.claim(second).state == "new"
    key, = ledger.reserve_output_directories(first, trusted_directories=[out])
    import sqlite3
    with sqlite3.connect(store / "job_identity.sqlite3") as db:
        row = db.execute(
            "SELECT inode_id FROM output_directory_identity WHERE directory_key=?",
            (key,),
        ).fetchone()
    assert row == (-(1 << 63) + 123,)
    with pytest.raises(PrepareEvidenceError) as blocked:
        ledger.reserve_output_directories(second, trusted_directories=[out])
    assert blocked.value.code == "WHD_OUTPUT_PATH_LOCKED"
    assert list(out.iterdir()) == []
