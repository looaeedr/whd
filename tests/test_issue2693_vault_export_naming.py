"""#2693 portable filename ownership and Taiwan-local export instant."""
from datetime import datetime, timezone, timedelta

import pytest

from ae_engine import manufacturing_api


def test_named_vault_uses_canonical_label_not_current_time():
    assert manufacturing_api.vault_panel_dxf_filename(" A01 ") == "A01.dxf"
    assert manufacturing_api.vault_panel_dxf_filename("門控箱") == "門控箱.dxf"


def test_blank_vault_uses_asia_taipei_instant():
    at = datetime(2026, 11, 1, 6, 5, 4, tzinfo=timezone.utc)
    assert (manufacturing_api.vault_panel_dxf_filename("", at=at)
            == "金庫型_20261101_140504.dxf")
    offset = timezone(timedelta(hours=-5))
    at = datetime(2026, 11, 1, 1, 5, 4, tzinfo=offset)
    assert (manufacturing_api.vault_panel_dxf_filename("  ", at=at)
            == "金庫型_20261101_140504.dxf")


@pytest.mark.parametrize("name", ["A/B", "CON", "A?", "..", "NUL.txt"])
def test_unsafe_name_refused_for_manufacturing_path(name):
    with pytest.raises(ValueError, match="盤名"):
        manufacturing_api.vault_panel_dxf_filename(name)


def test_naive_fake_timestamp_does_not_silently_use_host_timezone():
    with pytest.raises(ValueError, match="AWARE_DATETIME"):
        manufacturing_api.vault_panel_dxf_filename(
            "", at=datetime(2026, 11, 1, 14, 5, 4),
        )
