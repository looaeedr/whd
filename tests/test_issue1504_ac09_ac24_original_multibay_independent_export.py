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
    with pytest.raises(ValueError,match="INDEPENDENT_PHYSICAL_SOURCE_MISSING"):
        export_current_receiving_multibay_dxf(
            source,physical_bay_geometry_provider=missing_head,
            flags=_flags(box_body=False,head=True,tail=False,door=False,
                         base_plate=False,indicator_box=False,indicator_door=False),
            output_dir=root,
        )
    assert not list(root.glob("*.dxf"))


def test_ac09_original_gui_selected_head_uses_isolated_current_bay_preview(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import fold_designer_bridge as bridge
    from gui_modules.project import export_actions as actions
    from phase6_final_scene_contracts import AssemblyScenePart
    from ae_engine.receiving_layout import receiving_bay_assembly_offsets
    from tests.test_issue1502_multibay_original_gui_export_integration import (
        _native_callback_host,
    )
    snapshot=_source_with_missing_second_model()
    original=deepcopy(snapshot)
    host=_native_callback_host(monkeypatch,snapshot,[])
    calls=[]
    class SourcePhysicalComposition:
        def receiving_bay_preview_request(self,namespace,si,bi,*,preview_layout=None):
            assert namespace is bridge.__dict__
            assert preview_layout is not None
            bay=preview_layout["sets"][si]["bays"][bi]
            assert bay["nfb_config_submitted"] is False
            assert snapshot["receiving_layout"]["sets"][si]["bays"][bi][
                "nfb_config_submitted"] is True
            physical=project_receiving_bay_legacy_aliases({
                **snapshot,"receiving_layout":preview_layout,
            },set_index=si,bay_index=bi)
            actual=_full_receiving_geometry(physical)
            shift=receiving_bay_assembly_offsets(
                snapshot["receiving_layout"],set_index=si,
            )[bi]
            calls.append((si,bi))
            return SimpleNamespace(render_data=SimpleNamespace(
                assembly_parts=tuple(AssemblyScenePart(
                    part_key=p.part_key,render_data=p.render_data,
                    x_profile=p.x_profile,y_profile=p.y_profile,
                    placement=p.placement,
                    offset=tuple(a+b for a,b in zip(p.offset,shift)),
                ) for p in actual.parts)
            ))
    monkeypatch.setattr(
        bridge,"_phase6_composition",lambda designer:SourcePhysicalComposition(),
    )
    names,errors=actions._export_selected_resolved_parts(
        host,str(tmp_path),
        _flags(box_body=False,head=True,tail=False,door=False,
               base_plate=False,indicator_box=False,indicator_door=False),
    )
    assert not errors
    assert calls==[(0,0),(0,1)]
    assert len(names)==2 and all("head" in name for name in names)
    assert all(ezdxf.readfile(str(path)).modelspace() is not None
               for path in tmp_path.glob("*.dxf"))
    assert snapshot==original


def test_ac24_original_gui_nfb_dependent_selection_does_not_mask_current_bay(tmp_path,monkeypatch):
    import fold_designer_bridge as bridge
    from gui_modules.project import export_actions as actions
    from tests.test_issue1502_multibay_original_gui_export_integration import (
        _native_callback_host,
    )
    snapshot=_source_with_missing_second_model()
    host=_native_callback_host(monkeypatch,snapshot,[])
    visited=[]
    class MustUseActualNfb:
        def receiving_bay_preview_request(self,namespace,si,bi,*,preview_layout=None):
            visited.append((si,bi,preview_layout))
            assert preview_layout is None
            if bi==1:
                raise ValueError("CURRENT_CSV_NFB_SOURCE_INVALID")
            return __import__("types").SimpleNamespace(render_data=__import__(
                "types").SimpleNamespace(assembly_parts=()))
    monkeypatch.setattr(bridge,"_phase6_composition",lambda _:MustUseActualNfb())
    with pytest.raises(ValueError,match="CURRENT_CSV_NFB_SOURCE_INVALID|FINALSCENE"):
        actions._export_selected_resolved_parts(
            host,str(tmp_path),
            _flags(box_body=True,head=True,tail=False,door=False,
                   base_plate=True,indicator_box=False,indicator_door=False),
        )
    assert visited and all(item[2] is None for item in visited)
    assert not list(tmp_path.glob("*.dxf"))
