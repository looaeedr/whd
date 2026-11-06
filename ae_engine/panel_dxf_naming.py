"""#2693: Engine-owned Vault DXF filename (not a geometry/approval gate)."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .panel_naming import normalize_panel_name

_TAIPEI = ZoneInfo("Asia/Taipei")


def vault_panel_dxf_filename(panel_name: str, *, at: datetime | None = None) -> str:
    """Stable cabinet label if supplied, otherwise real Asia/Taipei export time.

    The caller MUST still use the verified manufacturing exporter with its
    existing overwrite/collision checks. A timestamp is never permission to
    overwrite an earlier file or to manufacture an uncertified sheet.
    """
    name = normalize_panel_name(panel_name, allow_blank=True)
    if name:
        return f"{name}.dxf"
    if at is None:
        clock = datetime.now(_TAIPEI)
    elif isinstance(at, datetime) and at.tzinfo is not None and at.utcoffset() is not None:
        clock = at.astimezone(_TAIPEI)
    else:
        raise ValueError("VAULT_DXF_TIMESTAMP_REQUIRES_AWARE_DATETIME")
    return "金庫型_" + clock.strftime("%Y%m%d_%H%M%S") + ".dxf"
