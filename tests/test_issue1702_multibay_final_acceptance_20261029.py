# -*- coding: utf-8 -*-
"""#1702 stage 2: actual multi-Bay acceptance after the single cabinet CI passed.

Do not confuse one/two inner-door tiers with the Set/Bay cabinet count.
Use existing source-confirmed NFB CSV and the real namespaced physical DXF
exporter; never manufacture a second copy of a Bay 1 scene.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import ezdxf
import pytest

from ae_engine.cabinet_types.policy import derive_inner_door_panels
from ae_engine.receiving_layout import (
    project_receiving_bay_legacy_aliases,
    resize_receiving_bays,
    update_receiving_bay,
)
from phase6_project_file import PROJECT_SCHEMA_V2, read_project, write_project
from phase6_receiving_modes import fresh_receiving_mode
from tests.test_issue1502_current_csv_multi_bay_once import _multi, _run


def _find_one(names, text):
    found = tuple(name for name in names if text in name)
    assert len(found) == 1, (text, found)
    return found[0]


def test_each_current_bay_exports_own_inner_panel_and_both_side_marks_without_cross_borrowing(tmp_path: Path):
    source = _multi()
    original = deepcopy(source)
    out = tmp_path / "all-physical-bays"
    exported, calls = _run(source, out)
    assert calls == [(0, 0), (0, 1)]
    names = tuple(Path(filename).name for filename in exported.values())
    assert len(names) == len(set(names)) == len(list(out.glob("*.dxf")))
    assert source == original, "The DXF batch must not mutate persisted Set/Bay authority"
    assert len(source["receiving_layout"]["sets"]) == 1
    assert len(source["receiving_layout"]["sets"][0]["bays"]) == 2
    first, second = source["receiving_layout"]["sets"][0]["bays"]
    assert first["stable_id"] != second["stable_id"]
    assert first["nfb_config"] != second["nfb_config"], "Source must genuinely differ between Bays"

    for number in (1, 2):
        scoped = tuple(name for name in names if f"receiving_set_1_bay_{number}" in name)
        assert scoped, (number, names)
        panel = _find_one(scoped, "inner_door_upper_panel")
        panel_entities = tuple(ezdxf.readfile(out / panel).modelspace())
        assert any(entity.dxf.layer == "CUTTING" for entity in panel_entities)
        assert any(entity.dxf.layer == "BEND" for entity in panel_entities)

        for side in ("left_side", "right_side"):
            filename = _find_one(scoped, side)
            drawing = ezdxf.readfile(out / filename)
            marks = tuple(
                entity for entity in drawing.modelspace()
                if entity.dxftype() == "LINE"
                and str(entity.dxf.layer).upper() == "MARKING"
            )
            # Side carries real locator contact and committed EAR position,
            # not a placeholder, viewport overlay, or Bay 1 shared file.
            assert len(marks) >= 2, (number, side, len(marks))
            assert any(entity.dxf.layer == "CUTTING" for entity in drawing.modelspace())
        assert sum("base_plate" in filename and "fixing_plate" not in filename
                   and "nfb_pad" not in filename for filename in scoped) == 1
    assert sum("inner_door" in name and "panel" in name for name in names) == 2


def test_distinct_multibay_dimensions_and_real_inner_panels_survive_project_save_reload(tmp_path: Path):
    source = fresh_receiving_mode(
        "set_bay", {"w": 800.0, "h": 1600.0, "d": 350.0}
    )
    layout = resize_receiving_bays(
        source["receiving_layout"], set_index=0, bay_count=2,
    )
    layout = update_receiving_bay(
        layout, set_index=0, bay_index=1,
        width=900.0, height=1700.0, depth=400.0,
    )
    source["receiving_layout"] = layout
    original = deepcopy(source)
    project = write_project(
        tmp_path / "two-physical-bays.p6fold",
        {"schema": PROJECT_SCHEMA_V2, "snapshot": source},
    )
    assert source == original
    reloaded = read_project(project)["snapshot"]
    layout_after = reloaded["receiving_layout"]
    assert len(layout_after["sets"]) == 1
    assert len(layout_after["sets"][0]["bays"]) == 2
    assert len(layout_after["sets"][0]["joints"]) == 1
    ids = [b["stable_id"] for b in layout_after["sets"][0]["bays"]]
    assert ids == ["receiving:set:1:bay:1", "receiving:set:1:bay:2"]
    assert [
        (float(b["width"]), float(b["height"]), float(b["depth"]))
        for b in layout_after["sets"][0]["bays"]
    ] == [(800.0, 1600.0, 350.0), (900.0, 1700.0, 400.0)]
    for bi, (w, h, d) in enumerate(((800.0, 1600.0, 350.0), (900.0, 1700.0, 400.0))):
        bay = project_receiving_bay_legacy_aliases(
            reloaded, set_index=0, bay_index=bi,
        )
        assert (bay["w"], bay["h"], bay["d"]) == (w, h, d)
        assert bay["_receiving_runtime_selection"]["bay_id"] == ids[bi]
        assert [p.stable_id for p in derive_inner_door_panels(bay)] == [
            "inner_door:upper:panel"
        ]
    assert reloaded.get("final_geometry", {}) == {}


def test_unconfigured_bay_selected_missing_base_never_exports_partial_dxfs(tmp_path: Path):
    """The operator's checked Base cannot vanish from an otherwise successful batch."""
    from ae_engine.receiving_layout import normalize_receiving_layout
    from tests.test_issue1502_single_button_full_csv_receiving_export import _flags
    from tests.test_issue1502_quantity_current_csv_full_batch import _geometry
    from tests.test_issue1050_receiving_mother_plate_marking import _full_receiving_geometry

    source = _multi()
    layout = deepcopy(source["receiving_layout"])
    unconfigured = layout["sets"][0]["bays"][1]
    unconfigured.pop("nfb_config", None)
    unconfigured.pop("nfb_config_submitted", None)
    source["receiving_layout"] = normalize_receiving_layout(layout)
    saved = write_project(
        tmp_path / "one-unconfigured.p6fold",
        {"schema": PROJECT_SCHEMA_V2, "snapshot": source},
    )
    reloaded = read_project(saved)["snapshot"]
    assert len(reloaded["receiving_layout"]["sets"][0]["bays"]) == 2

    def physical_bay_source(si, bi):
        projected = project_receiving_bay_legacy_aliases(
            reloaded, set_index=si, bay_index=bi,
        )
        # Bay 1 has real CSV Base; Bay 2's unconfigured live scene does NOT
        # contain a Base. A full operator selection must refuse every DXF.
        return _geometry(projected) if bi == 0 else _full_receiving_geometry(projected)

    blocked = tmp_path / "no-partial-cabinet"
    with pytest.raises(
        ValueError,
        match="RECEIVING_MULTIBAY_SELECTED_BASE_PLATE_PHYSICAL_SOURCE_MISSING",
    ):
        _run(reloaded, blocked, provider=physical_bay_source)
    assert not list(blocked.glob("*.dxf"))

    # Independent, existing physical HEAD sheets are genuinely exportable
    # even if the unselected NFB Base is not yet configured.
    heads = tmp_path / "independent-heads"
    exports, _ = _run(
        reloaded, heads, provider=physical_bay_source,
        flags=_flags(box_body=False, base_plate=False, door=False, head=True, tail=False),
    )
    assert len(exports) == len(list(heads.glob("*.dxf"))) == 2
    for path in exports.values():
        assert any(row.dxf.layer == "CUTTING" for row in ezdxf.readfile(path).modelspace())
