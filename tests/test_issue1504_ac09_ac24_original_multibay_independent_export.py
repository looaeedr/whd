# -*- coding: utf-8 -*-
"""#1504 AC09/24 genuine unrelated sheet export isolation in two real Bays."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import ezdxf
import pytest

from ae_engine.receiving_layout import project_receiving_bay_legacy_aliases
from ae_engine.receiving_csv_multibay_manufacturing import export_current_receiving_multibay_dxf
from tests.test_issue1502_current_csv_multi_bay_once import _multi, _provider
from tests.test_issue1502_single_button_full_csv_receiving_export import _flags
from tests.test_issue1050_receiving_mother_plate_marking import _full_receiving_geometry


def _source_with_missing_second_model():
    snapshot=_multi()
    second=snapshot["receiving_layout"]["sets"][0]["bays"][1]
    second["nfb_config"]["holes"][0]["model_filename"]="nfbv5:士林:MISSING-NFB-CSV-ROW"
    return snapshot


def _fresh_unrelated_geometry(source, si, bi):
    # Genuine source-based HEAD, TAIL, outer DOOR and BoxBody geometry for
    # THIS Bay, not a stale NFB-containing first Bay or fabricated part ID.
    physical=project_receiving_bay_legacy_aliases(
        source,set_index=si,bay_index=bi,
    )
    return _full_receiving_geometry(physical)


def test_ac09_original_multibay_dxf_only_real_head_not_blocked_by_unselected_bad_nfb(tmp_path):
    snapshot=_source_with_missing_second_model()
    invoked=[]
    def live(si,bi):
        invoked.append((si,bi))
        return _fresh_unrelated_geometry(snapshot,si,bi)
    out=tmp_path/"head-only"
    result=export_current_receiving_multibay_dxf(
        snapshot,physical_bay_geometry_provider=live,
        flags=_flags(box_body=False,head=True,tail=False,door=False,
                     base_plate=False,indicator_box=False,indicator_door=False),
        output_dir=out,
    )
    assert invoked==[(0,0),(0,1)]
    assert len(result)==2
    assert len(list(out.glob("*.dxf")))==2
    assert all("head" in key for key in result)
    assert all(ezdxf.readfile(Path(path)).modelspace() is not None
               for path in result.values())
    assert not list(out.glob("*base_plate*.dxf"))


def test_ac24_requested_nfb_or_side_sheet_still_cannot_bypass_missing_source(tmp_path):
    snapshot=_source_with_missing_second_model()
    for selected in (
        _flags(box_body=False,head=True,tail=False,door=False,
               base_plate=True,indicator_box=False,indicator_door=False),
        _flags(box_body=True,head=True,tail=False,door=False,
               base_plate=False,indicator_box=False,indicator_door=False),
    ):
        out=tmp_path/("base-selected" if selected["base_plate"] else "side-selected")
        with pytest.raises(ValueError,match="CSV|SOURCE|CURRENT"):
            export_current_receiving_multibay_dxf(
                snapshot,
                physical_bay_geometry_provider=lambda si,bi:
                    _fresh_unrelated_geometry(snapshot,si,bi),
                flags=selected,output_dir=out,
            )
        assert not list(out.glob("*.dxf"))


def test_ac24_actual_head_is_not_inferred_from_unrendered_nfb_part(tmp_path):
    source=_source_with_missing_second_model()
    def missing_head(si,bi):
        geom=_fresh_unrelated_geometry(source,si,bi)
        if bi==1:
            return replace(geom,parts=tuple(p for p in geom.parts
                                           if p.part_key!="head"))
        return geom
    root=tmp_path/"unverified-head"
    with pytest.raises(ValueError,match="CSV|SOURCE|NO_SELECTED|NO_SELECTED_PHYSICAL"):
        export_current_receiving_multibay_dxf(
            source,physical_bay_geometry_provider=missing_head,
            flags=_flags(box_body=False,head=True,tail=False,door=False,
                         base_plate=False,indicator_box=False,indicator_door=False),
            output_dir=root,
        )
    assert not list(root.glob("*.dxf"))
