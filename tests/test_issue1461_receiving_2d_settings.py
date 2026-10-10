"""GUI contract: item gating, 2D source geometry and overlay-only selection."""
from copy import deepcopy
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk
import pytest

from ae_engine.receiving_layout import new_receiving_layout, resize_receiving_bays
from ae_engine.manufacturing_render_data import PartRenderData
from ae_engine.sheetmetal_drawing import DrawingScene
from shapely.geometry import box
from phase6_final_scene_contracts import AssemblyScenePart, AssemblySceneRenderData, FinalSceneViewRequest
from gui_modules.application.receiving_set_bay_controls import open_receiving_layer_preview

def test_front_elevation_uses_assembled_world_offsets_and_hole_outline():
    from shapely.geometry import Point
    from gui_modules.application.receiving_settings_preview_2d import projected_assembly_parts
    hole_material = box(0, 0, 100, 70).difference(Point(45, 35).buffer(7, resolution=12))
    scene = DrawingScene()
    data = PartRenderData(scene=scene, material=hole_material)
    # Real formed mesh uses profile lengths; absent profiles are only a 1x1
    # compatibility fallback and cannot represent this 100x70 holed sheet.
    xp = ({"len": 100, "core": "W"},)
    yp = ({"len": 70, "core": "H"},)
    left = AssemblyScenePart("door:left", data, xp, yp, offset=(0, 0, 0))
    right = AssemblyScenePart("door:right", data, xp, yp, offset=(180, 0, 0))
    request = FinalSceneViewRequest(
        AssemblySceneRenderData((left, right)), (), (), "assembly",
        finished_dimensions=(300, 200, 80))
    parts = projected_assembly_parts(request)
    assert len(parts) == 2
    assert [role for role, _, _ in parts] == ["door", "door"]
    assert all(len(edges) > 4 for _, _, edges in parts), "holes need to remain in the projection"
    first_min = min(p[0] for edge in parts[0][2] for p in edge)
    second_min = min(p[0] for edge in parts[1][2] for p in edge)
    assert second_min - first_min == pytest.approx(180)
    assert hole_material.area < 100*70


def test_two_dimensional_preview_gates_selection_and_reuses_canonical_artists(monkeypatch):
    from phase6_final_scene_renderer import Phase6FinalSceneRenderer
    renders = []
    original = Phase6FinalSceneRenderer.render
    def observed(self, request):
        renders.append(request)
        return original(self, request)
    monkeypatch.setattr(Phase6FinalSceneRenderer, "render", observed)
    scene = DrawingScene()
    scene.add_polyline([(0,0),(800,0),(800,350),(0,350)], layer="CUTTING", closed=True)
    scene.add_circle((100,100), 4, layer="CUTTING")
    data = PartRenderData(scene=scene, material=box(0,0,800,350))
    part = AssemblyScenePart("head", data, (), ())
    request = FinalSceneViewRequest(AssemblySceneRenderData((part,)), (), (), "assembly", finished_dimensions=(800,1600,350))
    row = resize_receiving_bays(new_receiving_layout(width=800,height=1600,depth=350),set_index=0,bay_count=2)["sets"][0]
    selected, providers, commits = [], [], []
    ports = {"row":lambda:deepcopy(row), "select":selected.append,
             "change":lambda *args:commits.append(args), "share":lambda *args:None,
             "unlink":lambda *args:None, "dimensions":lambda *args,**kw:None,
             "alignment":lambda *args:commits.append(args), "brand":lambda *args:commits.append(args),
             "holes":lambda *args:None}
    root=tk.Tk()
    root.withdraw()
    try:
        assert open_receiving_layer_preview(root,tk=tk,ttk=ttk,layer_index=0,connection_count=2,
            brand="士林",render_request=request,bay_requests=(request,request),
            settings_ports=ports,bay_request_provider=lambda:providers.append(1) or (request,request))
        root.update()
        win=next(c for c in root.winfo_children() if hasattr(c,"_phase6_receiving_preview_canvas"))
        assert win._phase6_receiving_preview_canvas.figure.axes[0].name == "rectilinear"
        assert not renders
        panel=win._phase6_receiving_settings_panel
        def widget_labels(widget):
            result = [widget.cget("text")] if isinstance(widget, ttk.Label) else []
            for child in widget.winfo_children():
                result.extend(widget_labels(child))
            return result
        labels = " ".join(widget_labels(panel))
        assert "門第" not in labels and "由上到下高度" not in labels
        assert "門分割" not in labels, "Do not add a second Door Layout editor"
        before=deepcopy(row)
        panel._receiving_select_bay(1)
        assert selected == [] and not panel._receiving_pending and row == before
        panel._receiving_kind_var.set("封頭孔")
        panel._receiving_refresh()
        artists=tuple(win._phase6_receiving_preview_canvas.figure.axes[0].get_children())
        for _ in range(20):
            panel._receiving_select_bay(1)
            root.update_idletasks()
        assert providers == [] and commits == [] and not renders
        assert tuple(win._phase6_receiving_preview_canvas.figure.axes[0].get_children()) == artists
        assert scene.primitives[1].radius == 4
        view = win._phase6_receiving_preview_2d
        rect = view.tiles[0][3]
        event = SimpleNamespace(inaxes=view.ax, xdata=rect.get_x()+30,
                                ydata=rect.get_y()+30)
        for _ in range(20):
            view._motion(event)
            event.xdata += 1
        view.zoom(.8)
        view.reset_view()
        view.visibility["head"].set(False)
        view.update_visibility()
        assert view.geometry_draw_count == 1 and providers == []
        assert not renders and row == before
        def widgets(parent):
            for child in parent.winfo_children():
                yield child
                yield from widgets(child)
        brand = next(c for c in widgets(panel) if isinstance(c, ttk.Combobox)
                     and "士林" in c.cget("values"))
        brand.set("東元")
        brand.event_generate("<<ComboboxSelected>>")
        root.update_idletasks()
        assert commits == [], "未按套用品牌不得提交"
        # Closing discards pending dimensions/brand selections.
        win.destroy()
        assert row == before and commits == []
    finally:
        root.destroy()

def test_committed_scene_syncs_visibility_controls_and_preserves_hidden_parts():
    from gui_modules.application.receiving_settings_preview_2d import ReceivingSettingsPreview2D
    scene = DrawingScene()
    scene.add_polyline([(0,0),(100,0),(100,50),(0,50)],layer="CUTTING",closed=True)
    data = PartRenderData(scene=scene,material=box(0,0,100,50))
    def request(*keys):
        parts=tuple(AssemblyScenePart(key,data,(),()) for key in keys)
        return FinalSceneViewRequest(AssemblySceneRenderData(parts),(),(),"assembly")
    root=tk.Tk()
    try:
        view=ReceivingSettingsPreview2D(root,tk=tk,ttk=ttk,requests=(request("head"),))
        root.update()
        view.visibility["head"].set(False)
        view.update_visibility()
        view.draw_geometry((request("head","inner_door:layer1","inner_door:layer2"),))
        root.update()
        assert not view.visibility["head"].get()
        assert "inner_door" in view.visibility
        assert sum(role=="inner_door" for _,role,_,_,_ in view.tiles)==2
        assert all(not artist.get_visible() for _,role,_,_,artists in view.tiles
                   if role=="head" for artist in artists)
        assert view.geometry_draw_count==2
        from gui_modules.application.receiving_settings_preview_2d import refresh_committed_preview, CommittedPreviewError
        def failed_source():
            raise ValueError("資料來源不可製造")
        with pytest.raises(CommittedPreviewError, match="不可製造"):
            refresh_committed_preview(view, failed_source)
        root.update()
        assert not view.requests and not view.tiles
        assert "資料來源不可製造" in view.status.get()
        view.draw_geometry((request("head"),))
        root.update()
        assert view.status.get()=="" and len(view.tiles)==1
    finally:
        root.destroy()
