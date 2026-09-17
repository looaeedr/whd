from pathlib import Path

ORCH = Path("gui_modules/editors/hole_editor.py")
GUI = Path("gui.py")

orch = ORCH.read_text(encoding="utf-8")
if "class HoleEditorLiveContext:" not in orch:
    anchor = "class HoleEditorFeatureFactory:"
    if orch.count(anchor) != 1:
        raise SystemExit(f"orchestration anchor mismatch: {orch.count(anchor)}")
    classes = '''class HoleEditorLiveContext:
    """Transient live CAD context shared by editor handlers; never committed state."""

    def __init__(
        self, *, feature_list, surface, width, height, reference_guide,
        baseline_scene, part_key,
    ):
        self.feature_list = feature_list
        self.surface = surface
        self.width = float(width)
        self.height = float(height)
        self.reference_guide = reference_guide
        self.baseline_scene = baseline_scene
        self.part_key = part_key

    def apply(self, context):
        self.feature_list = context["feature_list"]
        self.surface = context["surface"]
        self.width = float(context["width"])
        self.height = float(context["height"])
        self.reference_guide = context["reference_guide"]
        self.baseline_scene = context.get("baseline_scene")
        if context.get("part_key") is not None:
            self.part_key = context["part_key"]

    def as_dict(self):
        return {
            "feature_list": self.feature_list,
            "surface": self.surface,
            "width": self.width,
            "height": self.height,
            "reference_guide": self.reference_guide,
            "baseline_scene": self.baseline_scene,
            "part_key": self.part_key,
        }


class HoleEditorContextSwitcher:
    """Switch transient editor projection while reusing the existing session."""

    def __init__(
        self, *, live_context, hole_session, door_context, indicator_contexts,
        cancel_active_edit, insert_mode, insert_button, active_part_key,
        position_authority, baseline_status_var, baseline_status_label,
        baseline_status_color, refresh_created, refresh_reference_fields, redraw,
    ):
        self.live_context = live_context
        self.hole_session = hole_session
        self.door_context = door_context
        self.indicator_contexts = indicator_contexts
        self.cancel_active_edit = cancel_active_edit
        self.insert_mode = insert_mode
        self.insert_button = insert_button
        self.active_part_key = active_part_key
        self.position_authority = position_authority
        self.baseline_status_var = baseline_status_var
        self.baseline_status_label = baseline_status_label
        self.baseline_status_color = baseline_status_color
        self.refresh_created = refresh_created
        self.refresh_reference_fields = refresh_reference_fields
        self.redraw = redraw

    def switch(self, context_key):
        if self.hole_session.has_active_edit:
            self.cancel_active_edit()
        if self.insert_mode[0]:
            self.insert_mode[0] = False
            self.insert_button.configure(text="插入", bg="#30d158")
        context = (
            self.door_context
            if context_key == "door"
            else self.indicator_contexts.get(context_key)
        )
        if not context:
            return False
        self.live_context.apply(context)
        part_key = context.get("part_key", context_key)
        self.live_context.part_key = part_key
        self.active_part_key[0] = part_key
        self.hole_session.activate_context(context_key, self.live_context.feature_list)
        self.live_context.feature_list = self.hole_session.active_features
        self.position_authority[0] = None
        status_text = str(context.get("baseline_status_text") or "")
        self.baseline_status_var.set(status_text)
        if self.baseline_status_label is not None:
            self.baseline_status_label.configure(
                fg=self.baseline_status_color(status_text)
            )
        self.refresh_created()
        self.refresh_reference_fields()
        self.redraw()
        return True


'''
    ORCH.write_text(orch.replace(anchor, classes + anchor, 1), encoding="utf-8")

text = GUI.read_text(encoding="utf-8")
import_anchor = "from gui_modules.editors.hole_editor import (\n"
imports = (
    "    HoleEditorContextSwitcher as _HoleEditorContextSwitcher,\n"
    "    HoleEditorLiveContext as _HoleEditorLiveContext,\n"
)
if "HoleEditorLiveContext as _HoleEditorLiveContext" not in text:
    if text.count(import_anchor) != 1:
        raise SystemExit(f"GUI import anchor mismatch: {text.count(import_anchor)}")
    text = text.replace(import_anchor, import_anchor + imports, 1)

live_anchor = "        indicator_component_contexts = {}\n"
if "        live_context = _HoleEditorLiveContext(" not in text:
    if text.count(live_anchor) != 1:
        raise SystemExit(f"live context anchor mismatch: {text.count(live_anchor)}")
    live = '''        live_context = _HoleEditorLiveContext(
            feature_list=feature_list,
            surface=surface,
            width=width,
            height=height,
            reference_guide=reference_guide,
            baseline_scene=baseline_scene,
            part_key=part_key,
        )
'''
    text = text.replace(live_anchor, live_anchor + live, 1)

method_start = text.index("    def _open_unified_hole_editor(")
tail_start = text.index("        created_list_presentation = _HoleEditorCreatedListPresentation(", method_start)
tail_end = text.index("    def open_hole_editor(self, key):", tail_start)
tail = text[tail_start:tail_end]

replacements = {
    "feature_list_provider=lambda: feature_list": "feature_list_provider=lambda: live_context.feature_list",
    "selection_provider=lambda: (hole_session.selected_index, feature_list)": "selection_provider=lambda: (hole_session.selected_index, live_context.feature_list)",
    '"reference_guide": reference_guide,': '"reference_guide": live_context.reference_guide,',
    '"surface": surface,': '"surface": live_context.surface,',
    '"width": width,': '"width": live_context.width,',
    '"height": height,': '"height": live_context.height,',
    '"feature_list": feature_list,': '"feature_list": live_context.feature_list,',
    '"baseline_scene": baseline_scene,': '"baseline_scene": live_context.baseline_scene,',
    'context_provider=lambda: {"width": width, "height": height},': 'context_provider=lambda: {"width": live_context.width, "height": live_context.height},',
    'has_selected_feature=lambda: 0 <= hole_session.selected_index < len(feature_list)': 'has_selected_feature=lambda: 0 <= hole_session.selected_index < len(live_context.feature_list)',
}
for old, new in replacements.items():
    tail = tail.replace(old, new)

switch_start = tail.find("        def _switch_editor_context(context_key):\n")
if switch_start != -1:
    next_anchor = "        indicator_context_refresh_controller = _HoleEditorIndicatorContextRefresh(\n"
    switch_end = tail.index(next_anchor, switch_start)
    wiring = '''        context_switcher = _HoleEditorContextSwitcher(
            live_context=live_context,
            hole_session=hole_session,
            door_context=door_editor_context,
            indicator_contexts=indicator_component_contexts,
            cancel_active_edit=cancel_active_edit,
            insert_mode=insert_mode,
            insert_button=insert_btn,
            active_part_key=active_part_key,
            position_authority=position_authority,
            baseline_status_var=baseline_status_var,
            baseline_status_label=baseline_status_label,
            baseline_status_color=_HoleEditorIndicatorContextRefresh.baseline_status_color,
            refresh_created=refresh_created,
            refresh_reference_fields=refresh_reference_fields,
            redraw=redraw,
        )
        switch_editor_context = context_switcher.switch

'''
    tail = tail[:switch_start] + wiring + tail[switch_end:]

tail = tail.replace("switch_editor_context=_switch_editor_context", "switch_editor_context=switch_editor_context")
text = text[:tail_start] + tail + text[tail_end:]
GUI.write_text(text, encoding="utf-8")
