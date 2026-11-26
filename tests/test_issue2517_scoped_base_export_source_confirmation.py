"""Exercise saved Bay confirmation through the public batch DXF entry point."""
from copy import deepcopy

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_drawing import LinePrimitive
from ae_engine.sheetmetal_geometry import Vec2
from tests.test_issue1502_current_csv_multi_bay_once import _provider
from tests.test_issue3414_scoped_marking_proto import _ids, _raw_write, _real_source
from phase6_project_file import read_project


def test_revoked_marked_base_source_rejects_even_if_provider_still_has_confirmed_scene(tmp_path):
    confirmed = _real_source()
    donor = api.open_physical_sheet_marking("base_plate", snapshot=confirmed, selection=(0, 1))
    guide = next(p for p in donor.context.render_data.scene.primitives
                 if isinstance(p, LinePrimitive) and p.layer == "BEND")
    mark = api.create_physical_sheet_mark(
        donor, (), tool="line", length=12, angle_deg=90,
        midpoint=Vec2((guide.p1.x + guide.p2.x) / 2, (guide.p1.y + guide.p2.y) / 2),
    )
    ledger_key = api.SCOPED_BASE_PLATE_MARKS
    confirmed[ledger_key] = api.commit_physical_sheet_marking(donor, donor, (mark,)).scoped_store
    revoked = deepcopy(confirmed)
    revoked["receiving_layout"]["sets"][0]["bays"][1]["nfb_config_submitted"] = False
    path = _raw_write(tmp_path / "revoked.p6fold", revoked)
    saved = read_project(path)["snapshot"]
    before = path.read_bytes()
    stale_provider, calls = _provider(confirmed)
    destination = tmp_path / "new-export"
    with pytest.raises(ValueError, match="SCOPED_MARK_BASE_PLATE_NOT_SOURCE_VERIFIED"):
        api.export_current_receiving_multibay_dxf(
            saved, flags={"base_plate": True}, output_dir=destination,
            physical_bay_geometry_provider=stale_provider, pre_commit_guard=lambda: None,
        )
    assert calls == []
    assert not destination.exists()
    assert saved[ledger_key][_ids(confirmed)[1]]["features"] == [mark]
    assert path.read_bytes() == before
