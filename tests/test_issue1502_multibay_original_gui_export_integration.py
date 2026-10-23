# -*- coding: utf-8 -*-
"""#1502: real original GUI-selected export dispatch through TWO independent Bays.

Unlike the helper-only multi-Bay tests this invokes the existing
export_selected_dxf operator callback, including its checkbox inference,
current real Set/Bay preview adapter, namespace assembly-anchor conversion,
and outer atomic destination commit. The source physical geometry itself
is the exact per-Bay normal numeric CSV FinalScene used in other mandatory
tests. No separate CSV button or direct exporter call.
"""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine.receiving_layout import (
    project_receiving_bay_legacy_aliases,
    receiving_bay_assembly_offsets,
)
from phase6_final_scene_contracts import AssemblyScenePart
from gui_modules.project import export_actions as gui
from tests.test_issue1502_current_csv_multi_bay_once import _multi, _provider


class _Bool:
    def __init__(self, value=True):
        self.value=value
    def get(self):
        return self.value


def _native_callback_host(monkeypatch, snapshot, calls):
    import fold_designer_bridge as bridge
    provider, _seen = _provider(snapshot)

    class CanonicalComposition:
        def receiving_bay_preview_request(self, namespace, si, bi):
            assert namespace is bridge.__dict__, "use genuine Phase6 callback namespace"
            calls.append((si,bi))
            real=provider(si,bi)
            anchor=receiving_bay_assembly_offsets(
                snapshot["receiving_layout"],set_index=si,
            )[bi]
            return SimpleNamespace(render_data=SimpleNamespace(
                assembly_parts=tuple(AssemblyScenePart(
                    part_key=p.part_key,
                    render_data=p.render_data,
                    x_profile=p.x_profile,y_profile=p.y_profile,
                    placement=p.placement,
                    offset=tuple(a+b for a,b in zip(p.offset,anchor)),
                ) for p in real.parts)
            ))
    composition=CanonicalComposition()
    monkeypatch.setattr(
        bridge,"_phase6_composition",lambda _designer:composition,
    )
    class Designer:
        _phase6_input_snapshot=snapshot
        designer_workspace=None
        def _phase6_resolve_manufacturing_geometry(self):
            raise AssertionError(
                "multi-Bay normal DXF must resolve every Bay, never only active Bay"
            )
    designer=Designer()
    checks={
        "box_body": _Bool(),"head": _Bool(),"tail":_Bool(),
        "door":_Bool(),"base_plate":_Bool(),
        "indicator_box":_Bool(False),"indicator_door":_Bool(False),
    }
    host=SimpleNamespace(
        fold_designer_app=designer,
        _phase6_input_snapshot=snapshot,
        _phase6_nfb_partial_export_report=None,
        _flush_phase6_authoritative_state=lambda:None,
        _phase6_current_existing_parts=lambda:(
            "box_body","head","tail","door","base_plate"
        ),
        _phase6_logical_part_present=lambda _parts,key: key in {
            "door","base_plate",
        },
        _has_any_indicator_box=lambda:False,
        _validate_single_door_indicator_fit=lambda _val:None,
        get_float_values=lambda:{"w":snapshot["w"],"h":snapshot["h"],"d":snapshot["d"]},
        export_z_var=checks["box_body"],
        export_head_var=checks["head"],
        export_tail_var=checks["tail"],
        export_door_var=checks["door"],
        export_base_plate_var=checks["base_plate"],
        export_ib_var=checks["indicator_box"],
        export_ib_door_var=checks["indicator_door"],
        multi_door_enabled_var=_Bool(False),
        draw_stock_var=_Bool(False),
    )
    return host


def test_existing_operator_export_button_writes_both_live_bays_atomically(
    tmp_path,monkeypatch,
):
    snapshot=_multi()
    invoked=[]
    host=_native_callback_host(monkeypatch,snapshot,invoked)
    errors=[]
    infos=[]
    monkeypatch.setattr(gui.filedialog,"askdirectory",lambda **kw:str(tmp_path))
    monkeypatch.setattr(gui.messagebox,"showerror",
                        lambda title,msg:errors.append((title,msg)))
    monkeypatch.setattr(gui.messagebox,"showwarning",
                        lambda title,msg:errors.append((title,msg)))
    monkeypatch.setattr(gui.messagebox,"showinfo",
                        lambda title,msg:infos.append((title,msg)))
    monkeypatch.setattr(gui.messagebox,"askyesno",
                        lambda *a,**kw: pytest.fail(
                            "approved two-Bay numeric CSV must not ask to discard base"
                        ))
    gui.export_selected_dxf(host)
    assert not errors,errors
    assert len(infos)==1
    assert invoked==[(0,0),(0,1)]
    written=tuple(sorted(tmp_path.glob("*.dxf")))
    assert len(written)>=2
    assert all(ezdxf.readfile(str(p)).modelspace() is not None for p in written)
    names=[p.name for p in written]
    assert all("receiving_set" in name for name in names), names
    assert sum("fixing_plate" in name for name in names)==4, names
    assert sum("base_plate" in name and "fixing_plate" not in name
               for name in names)==2, names
    assert sum("inner_door" in name and "panel" in name
               for name in names)==2, names
    assert sum("left_side" in name for name in names)>=2, names
    assert sum("right_side" in name for name in names)>=2, names


def test_gui_multi_bay_second_source_missing_no_partial_output(
    tmp_path,monkeypatch,
):
    snapshot=_multi()
    calls=[]
    host=_native_callback_host(monkeypatch,snapshot,calls)
    # The second source is still submitted but its actual Bay geometry
    # cannot be satisfied: the source-owned physical plate has vanished.
    import fold_designer_bridge as bridge
    source_composition=bridge._phase6_composition(host.fold_designer_app)
    actual=source_composition.receiving_bay_preview_request
    def missing(namespace,si,bi):
        request=actual(namespace,si,bi)
        if bi==1:
            parts=tuple(p for p in request.render_data.assembly_parts
                        if p.part_key!="base_plate")
            request=SimpleNamespace(render_data=SimpleNamespace(
                assembly_parts=parts,
            ))
        return request
    source_composition.receiving_bay_preview_request=missing
    errors=[]
    monkeypatch.setattr(gui.filedialog,"askdirectory",lambda **kw:str(tmp_path))
    monkeypatch.setattr(gui.messagebox,"showerror",
                        lambda title,msg:errors.append((title,msg)))
    monkeypatch.setattr(gui.messagebox,"showwarning",
                        lambda title,msg:errors.append((title,msg)))
    monkeypatch.setattr(gui.messagebox,"showinfo",
                        lambda *_a:pytest.fail("must fail before success dialog"))
    monkeypatch.setattr(gui.messagebox,"askyesno",
                        lambda *_a,**_kw:pytest.fail("not a partial export"))
    gui.export_selected_dxf(host)
    assert errors and "BASE" in str(errors).upper()
    assert not list(tmp_path.glob("*.dxf"))
