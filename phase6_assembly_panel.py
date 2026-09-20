# -*- coding: utf-8 -*-
"""Tk owner for the Phase 5 Assembly Parts presentation panel.

The panel owns widgets and ephemeral presentation state only. Physical topology,
live manufacturing visibility authority, geometry solving, persistence, and
Final Scene orchestration remain outside this module.
"""
from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk
from typing import Callable

from whd_theme import WHD_THEME

from phase6_assembly_presentation import (
    AssemblyPresentationModel,
    AssemblyPresentationRow,
    AssemblySyntheticGroup,
    project_box_body_piece_rows,
)


@dataclass(frozen=True)
class AssemblyPanelActions:
    on_visibility_changed: Callable[[], None]


class Phase6AssemblyPanel:
    """Own Assembly Parts widgets and rebuild-safe Tk registries."""

    def __init__(self, parent, *, actions: AssemblyPanelActions):
        if not isinstance(actions, AssemblyPanelActions):
            raise TypeError("actions must be AssemblyPanelActions")
        self.actions = actions

        self.host = ttk.Frame(parent, padding=6)
        scroll_host = ttk.Frame(self.host)
        scroll_host.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(
            scroll_host,
            height=1,
            background=WHD_THEME["panel"],
            highlightthickness=0,
            borderwidth=0,
            takefocus=False,
        )
        self.scrollbar = ttk.Scrollbar(
            scroll_host,
            orient=tk.VERTICAL,
            command=self.canvas.yview,
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.content = ttk.Frame(self.canvas)
        self.window_id = self.canvas.create_window(
            (0, 0),
            window=self.content,
            anchor="nw",
        )
        self.content.bind("<Configure>", self._on_content_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # These dict objects are intentionally long-lived. Legacy Bridge aliases
        # point at them, so render/refresh mutate them in place instead of
        # replacing their identity.
        self.visible_vars: dict[str, tk.BooleanVar] = {}
        self.corner_vars: dict[str, tk.StringVar] = {}
        self.formed_vars: dict[str, tk.StringVar] = {}
        self.blank_vars: dict[str, tk.StringVar] = {}
        self.checkbuttons: dict[str, ttk.Checkbutton] = {}
        self.sections: dict[str, ttk.Frame] = {}
        self.detail_frames: dict[str, ttk.Frame] = {}
        self.detail_buttons: dict[str, ttk.Button] = {}

        self.group_sections: dict[str, ttk.Frame] = {}
        self.group_detail_frames: dict[str, ttk.Frame] = {}
        self.group_detail_buttons: dict[str, ttk.Button] = {}

        self.detail_open_stash: dict[str, bool] = {}
        self.group_open_stash: dict[str, bool] = {}

        self.box_body_piece_host: ttk.Frame | None = None
        self.box_piece_labels: dict[str, str] = {}
        self.box_piece_sections: dict[str, ttk.Frame] = {}
        self.box_piece_visible_vars: dict[str, tk.BooleanVar] = {}
        self.box_piece_checkbuttons: dict[str, ttk.Checkbutton] = {}
        self.box_piece_detail_frames: dict[str, ttk.Frame] = {}
        self.box_piece_detail_buttons: dict[str, ttk.Button] = {}
        self.box_piece_formed_vars: dict[str, tk.StringVar] = {}
        self.box_piece_blank_vars: dict[str, tk.StringVar] = {}
        self.box_piece_corner_vars: dict[str, tk.StringVar] = {}
        self.box_piece_visibility_stash: dict[str, bool] = {}
        self.box_piece_detail_open_stash: dict[str, bool] = {}

        self.bind_scroll(self.canvas)
        self.bind_scroll(self.content)

    def _on_content_configure(self, _event=None) -> None:
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            # #440 remediation: this panel no longer sits inside a fixed-height
            # outer wrapper. Let the Assembly surface itself request the height
            # its current content actually needs; the existing left workspace
            # scroll owner handles any overflow at the page level.
            requested = max(1, int(self.content.winfo_reqheight()))
            if int(float(self.canvas.cget("height"))) != requested:
                self.canvas.configure(height=requested)
        except Exception:
            pass

    def _on_canvas_configure(self, event) -> None:
        try:
            self.canvas.itemconfigure(self.window_id, width=max(1, int(event.width)))
        except Exception:
            pass

    @staticmethod
    def _event_int(value) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def scroll(self, event):
        delta = self._event_int(getattr(event, "delta", 0))
        number = self._event_int(getattr(event, "num", 0))
        if number == 4:
            steps = -1
        elif number == 5:
            steps = 1
        elif delta:
            steps = -1 if delta > 0 else 1
        else:
            return "break"
        try:
            self.canvas.yview_scroll(steps, "units")
        except Exception:
            pass
        return "break"

    def bind_scroll(self, widget) -> None:
        try:
            widget.bind("<MouseWheel>", self.scroll)
            widget.bind("<Button-4>", self.scroll)
            widget.bind("<Button-5>", self.scroll)
        except Exception:
            pass
        for child in tuple(getattr(widget, "winfo_children", lambda: ())()):
            self.bind_scroll(child)

    @staticmethod
    def _text_seed(value: str | None, fallback: str) -> str:
        return str(value) if value is not None else fallback

    def _snapshot_state(self):
        visible = {key: bool(var.get()) for key, var in self.visible_vars.items()}
        corner = {key: str(var.get()) for key, var in self.corner_vars.items()}
        formed = {key: str(var.get()) for key, var in self.formed_vars.items()}
        blank = {key: str(var.get()) for key, var in self.blank_vars.items()}

        detail_open = dict(self.detail_open_stash)
        detail_open.update(
            {key: bool(frame.winfo_manager()) for key, frame in self.detail_frames.items()}
        )
        group_open = dict(self.group_open_stash)
        group_open.update(
            {
                key: bool(frame.winfo_manager())
                for key, frame in self.group_detail_frames.items()
            }
        )
        return visible, corner, formed, blank, detail_open, group_open

    def _snapshot_box_piece_state(self) -> None:
        self.box_piece_visibility_stash.update(
            {
                key: bool(var.get())
                for key, var in self.box_piece_visible_vars.items()
            }
        )
        self.box_piece_detail_open_stash.update(
            {
                key: bool(frame.winfo_manager())
                for key, frame in self.box_piece_detail_frames.items()
            }
        )

    def _clear_box_piece_registries(self) -> None:
        for registry in (
            self.box_piece_labels,
            self.box_piece_sections,
            self.box_piece_visible_vars,
            self.box_piece_checkbuttons,
            self.box_piece_detail_frames,
            self.box_piece_detail_buttons,
            self.box_piece_formed_vars,
            self.box_piece_blank_vars,
            self.box_piece_corner_vars,
        ):
            registry.clear()

    def _clear_widget_registries(self) -> None:
        for child in tuple(self.content.winfo_children()):
            child.destroy()
        for registry in (
            self.visible_vars,
            self.corner_vars,
            self.formed_vars,
            self.blank_vars,
            self.checkbuttons,
            self.sections,
            self.detail_frames,
            self.detail_buttons,
            self.group_sections,
            self.group_detail_frames,
            self.group_detail_buttons,
        ):
            registry.clear()
        self._clear_box_piece_registries()
        self.box_body_piece_host = None

    def _build_part_row(
        self,
        parent,
        row_data: AssemblyPresentationRow,
        *,
        nested: bool,
        old_visible: dict[str, bool],
        old_corner: dict[str, str],
        old_formed: dict[str, str],
        old_blank: dict[str, str],
        old_open: dict[str, bool],
    ) -> None:
        key = str(row_data.part_key)
        row = ttk.Frame(parent)
        row.pack(
            fill=tk.X,
            padx=((18, 0) if nested else (0, 0)),
            pady=(0, 4),
        )

        visible = tk.BooleanVar(
            master=row,
            value=old_visible.get(key, bool(row_data.visible_seed)),
        )
        formed = tk.StringVar(
            master=row,
            value=old_formed.get(
                key,
                self._text_seed(row_data.formed_text_seed, "成形尺寸：等待3D"),
            ),
        )
        blank = tk.StringVar(
            master=row,
            value=old_blank.get(
                key,
                self._text_seed(row_data.blank_text_seed, "展開料：等待3D"),
            ),
        )
        corner = tk.StringVar(
            master=row,
            value=old_corner.get(
                key,
                self._text_seed(row_data.corner_text_seed, "截角尺寸：等待3D"),
            ),
        )

        header = ttk.Frame(row)
        header.pack(fill=tk.X)
        check = ttk.Checkbutton(
            header,
            text=str(row_data.label),
            variable=visible,
            command=self.actions.on_visibility_changed,
        )
        check.pack(side=tk.LEFT, anchor=tk.W, fill=tk.X, expand=True)

        details = ttk.Frame(row)
        details_open = bool(old_open.get(key, False))
        button = ttk.Button(
            header,
            text=("▾" if details_open else "▸"),
            width=2,
            command=lambda k=key: self.toggle_part_details(k),
            takefocus=True,
        )
        button.pack(side=tk.RIGHT)

        ttk.Label(
            details,
            textvariable=formed,
            justify=tk.LEFT,
            wraplength=300,
        ).pack(fill=tk.X, padx=(20, 0))
        ttk.Label(
            details,
            textvariable=blank,
            justify=tk.LEFT,
            wraplength=300,
        ).pack(fill=tk.X, padx=(20, 0))
        ttk.Label(
            details,
            textvariable=corner,
            justify=tk.LEFT,
            wraplength=300,
        ).pack(fill=tk.X, padx=(20, 0))

        if row_data.has_piece_host:
            self.box_body_piece_host = ttk.Frame(details)
            self.box_body_piece_host.pack(fill=tk.X)

        if details_open:
            details.pack(fill=tk.X)

        self.visible_vars[key] = visible
        self.corner_vars[key] = corner
        self.formed_vars[key] = formed
        self.blank_vars[key] = blank
        self.checkbuttons[key] = check
        self.sections[key] = row
        self.detail_frames[key] = details
        self.detail_buttons[key] = button
        self.bind_scroll(row)

    def _build_group(
        self,
        group_data: AssemblySyntheticGroup,
        *,
        old_visible: dict[str, bool],
        old_corner: dict[str, str],
        old_formed: dict[str, str],
        old_blank: dict[str, str],
        old_open: dict[str, bool],
        old_group_open: dict[str, bool],
    ) -> None:
        key = str(group_data.presentation_key)
        group = ttk.Frame(self.content)
        group.pack(fill=tk.X, pady=(0, 4))
        header = ttk.Frame(group)
        header.pack(fill=tk.X)
        ttk.Label(
            header,
            text=str(group_data.label),
            anchor=tk.W,
        ).pack(side=tk.LEFT, anchor=tk.W, fill=tk.X, expand=True)

        details = ttk.Frame(group)
        is_open = bool(old_group_open.get(key, False))
        button = ttk.Button(
            header,
            text=("▾" if is_open else "▸"),
            width=2,
            command=lambda k=key: self.toggle_group(k),
            takefocus=True,
        )
        button.pack(side=tk.RIGHT)
        if is_open:
            details.pack(fill=tk.X)

        self.group_sections[key] = group
        self.group_detail_frames[key] = details
        self.group_detail_buttons[key] = button

        for child in group_data.children:
            self._build_part_row(
                details,
                child,
                nested=True,
                old_visible=old_visible,
                old_corner=old_corner,
                old_formed=old_formed,
                old_blank=old_blank,
                old_open=old_open,
            )
        self.bind_scroll(group)

    def render(self, model: AssemblyPresentationModel) -> None:
        if not isinstance(model, AssemblyPresentationModel):
            raise TypeError("model must be AssemblyPresentationModel")

        (
            old_visible,
            old_corner,
            old_formed,
            old_blank,
            old_open,
            old_group_open,
        ) = self._snapshot_state()
        self._snapshot_box_piece_state()
        self._clear_widget_registries()

        live_part_keys: list[str] = []
        live_group_keys: list[str] = []
        for entry in model.entries:
            if isinstance(entry, AssemblySyntheticGroup):
                live_group_keys.append(str(entry.presentation_key))
                live_part_keys.extend(str(child.part_key) for child in entry.children)
                self._build_group(
                    entry,
                    old_visible=old_visible,
                    old_corner=old_corner,
                    old_formed=old_formed,
                    old_blank=old_blank,
                    old_open=old_open,
                    old_group_open=old_group_open,
                )
            else:
                live_part_keys.append(str(entry.part_key))
                self._build_part_row(
                    self.content,
                    entry,
                    nested=False,
                    old_visible=old_visible,
                    old_corner=old_corner,
                    old_formed=old_formed,
                    old_blank=old_blank,
                    old_open=old_open,
                )

        self.detail_open_stash.clear()
        self.detail_open_stash.update(
            {key: bool(old_open.get(key, False)) for key in live_part_keys}
        )
        self.group_open_stash.clear()
        self.group_open_stash.update(
            {key: bool(old_group_open.get(key, False)) for key in live_group_keys}
        )

        self.bind_scroll(self.content)
        self._on_content_configure()

    def refresh_box_body_piece_info(
        self,
        render_data,
        *,
        label_for: Callable[[str], str],
        number_text: Callable[[object], str],
        corner_text_for_render_data: Callable[[object], str],
    ):
        """Refresh render-time BoxBody piece rows without changing source timing."""
        host = self.box_body_piece_host
        if host is None:
            return ()

        projections = project_box_body_piece_rows(render_data, label_for=label_for)
        wanted = tuple(row.part_key for row in projections)
        current = tuple(self.box_piece_formed_vars)

        self._snapshot_box_piece_state()
        previous_visible = dict(self.box_piece_visibility_stash)
        previous_open = dict(self.box_piece_detail_open_stash)

        if current != wanted:
            for child in tuple(host.winfo_children()):
                child.destroy()
            self._clear_box_piece_registries()

            for projection in projections:
                key = str(projection.part_key)
                sub = ttk.Frame(host, padding=4)
                sub._phase6_part_key = key
                sub.pack(fill=tk.X, padx=(18, 0), pady=(2, 4))

                visible = tk.BooleanVar(
                    master=sub,
                    value=previous_visible.get(key, True),
                )
                header = ttk.Frame(sub)
                header.pack(fill=tk.X)
                check = ttk.Checkbutton(
                    header,
                    text=str(projection.label),
                    variable=visible,
                    command=self.actions.on_visibility_changed,
                )
                check.pack(
                    side=tk.LEFT,
                    anchor=tk.W,
                    fill=tk.X,
                    expand=True,
                )

                details = ttk.Frame(sub)
                details_open = bool(previous_open.get(key, False))
                button = ttk.Button(
                    header,
                    text=("▾" if details_open else "▸"),
                    width=2,
                    command=lambda k=key: self.toggle_box_piece_details(k),
                    takefocus=True,
                )
                button.pack(side=tk.RIGHT)

                formed = tk.StringVar(master=sub)
                blank = tk.StringVar(master=sub)
                corner = tk.StringVar(master=sub)
                ttk.Label(
                    details,
                    textvariable=formed,
                    justify=tk.LEFT,
                    wraplength=280,
                ).pack(fill=tk.X, padx=(18, 0))
                ttk.Label(
                    details,
                    textvariable=blank,
                    justify=tk.LEFT,
                    wraplength=280,
                ).pack(fill=tk.X, padx=(18, 0))
                ttk.Label(
                    details,
                    textvariable=corner,
                    justify=tk.LEFT,
                    wraplength=280,
                ).pack(fill=tk.X, padx=(18, 0))
                if details_open:
                    details.pack(fill=tk.X)

                self.box_piece_labels[key] = str(projection.label)
                self.box_piece_sections[key] = sub
                self.box_piece_visible_vars[key] = visible
                self.box_piece_checkbuttons[key] = check
                self.box_piece_detail_frames[key] = details
                self.box_piece_detail_buttons[key] = button
                self.box_piece_formed_vars[key] = formed
                self.box_piece_blank_vars[key] = blank
                self.box_piece_corner_vars[key] = corner
                self.bind_scroll(sub)

        piece_by_role = {
            str(getattr(piece, "role", "") or ""): piece
            for piece in tuple(getattr(render_data, "pieces", ()) or ())
        }
        for projection in projections:
            key = str(projection.part_key)
            self.box_piece_formed_vars[key].set(
                "成形尺寸："
                f"{number_text(projection.formed_width)} × "
                f"{number_text(projection.formed_height)} mm"
            )
            self.box_piece_blank_vars[key].set(
                "展開料："
                f"{number_text(projection.blank_width)} × "
                f"{number_text(projection.blank_height)} mm"
            )
            role = key.split(":", 1)[-1]
            piece = piece_by_role.get(role)
            corner_text = (
                corner_text_for_render_data(piece.render_data)
                if piece is not None
                else "截角尺寸：無"
            )
            self.box_piece_corner_vars[key].set(corner_text)

        self.box_piece_visibility_stash.clear()
        self.box_piece_visibility_stash.update(
            {
                key: bool(var.get())
                for key, var in self.box_piece_visible_vars.items()
            }
        )
        self.box_piece_detail_open_stash.clear()
        self.box_piece_detail_open_stash.update(
            {
                key: bool(frame.winfo_manager())
                for key, frame in self.box_piece_detail_frames.items()
            }
        )

        if projections:
            logical_formed = self.formed_vars.get("box_body")
            logical_blank = self.blank_vars.get("box_body")
            logical_corner = self.corner_vars.get("box_body")
            if logical_formed is not None:
                logical_formed.set("成形尺寸：見下方各片")
            if logical_blank is not None:
                logical_blank.set("展開料：見下方各片")
            if logical_corner is not None:
                logical_corner.set("截角尺寸：見下方各片")

        self._on_content_configure()
        return projections

    def set_corner_texts(self, values) -> None:
        """Apply Final Scene corner presentation text to existing logical rows."""
        normalized = {
            str(key): str(value)
            for key, value in dict(values or {}).items()
        }
        for key, value in normalized.items():
            var = self.corner_vars.get(key)
            if var is not None and callable(getattr(var, "set", None)):
                var.set(value)

    def set_part_text(self, kind, part_key, value) -> None:
        """Apply one lossy Final Scene formed/blank text sink update."""
        mapping = self.formed_vars if str(kind) == "formed" else self.blank_vars
        var = mapping.get(str(part_key))
        if var is not None and callable(getattr(var, "set", None)):
            var.set(value)

    @staticmethod
    def _resolve_visibility_with_vars(parts, visible_vars, piece_vars):
        """Resolve fixed-root Assembly visibility from Tk-var-like mappings."""
        parts = tuple(parts or ())
        visible_parts = [
            part
            for part in parts
            if bool(
                getattr(
                    visible_vars.get(part.part_key),
                    "get",
                    lambda: True,
                )()
            )
        ]
        if not visible_parts and parts:
            fallback = next(
                (part for part in parts if part.part_key == "box_body"),
                parts[0],
            )
            visible_parts = [fallback]
            var = visible_vars.get(fallback.part_key)
            if var is not None and callable(getattr(var, "set", None)):
                var.set(True)

        visible_keys = {part.part_key for part in visible_parts}
        box_part = next(
            (part for part in parts if part.part_key == "box_body"),
            None,
        )
        box_piece_keys = tuple(
            f"box_body:{str(getattr(piece, 'role', '') or '').strip()}"
            for piece in tuple(
                getattr(
                    getattr(box_part, "render_data", None),
                    "pieces",
                    (),
                )
                or ()
            )
            if str(getattr(piece, "role", "") or "").strip()
        )

        visible_box_body_piece_keys = None
        if box_piece_keys:
            if "box_body" not in visible_keys:
                visible_box_body_piece_keys = ()
            else:
                visible_box_body_piece_keys = tuple(
                    key
                    for key in box_piece_keys
                    if bool(
                        getattr(
                            piece_vars.get(key),
                            "get",
                            lambda: True,
                        )()
                    )
                )
                if (
                    not visible_box_body_piece_keys
                    and visible_keys == {"box_body"}
                ):
                    first = box_piece_keys[0]
                    var = piece_vars.get(first)
                    if var is not None and callable(getattr(var, "set", None)):
                        var.set(True)
                    visible_box_body_piece_keys = (first,)

        return (
            tuple(part.part_key for part in visible_parts),
            visible_box_body_piece_keys,
        )

    def resolve_visibility(self, parts):
        """Resolve Final Scene visibility from the panel-owned Tk vars."""
        return self._resolve_visibility_with_vars(
            parts,
            self.visible_vars,
            self.box_piece_visible_vars,
        )

    def visibility_var(self, key, *, is_box_piece=False):
        """Return the exact panel Tk visibility var for Structure Tree use."""
        key = str(key or "")
        if bool(is_box_piece):
            return self.box_piece_visible_vars.get(key)
        return self.visible_vars.get(key)

    def notify_visibility_changed(self) -> None:
        """Emit the sole panel action; the target owns render-mode policy."""
        self.actions.on_visibility_changed()

    def set_part_details_open(self, key, is_open):
        key = str(key)
        details = self.detail_frames.get(key)
        button = self.detail_buttons.get(key)
        if details is None:
            return False
        is_open = bool(is_open)
        if is_open:
            if not details.winfo_manager():
                details.pack(fill=tk.X)
        elif details.winfo_manager():
            details.pack_forget()
        if button is not None:
            try:
                button.configure(text=("▾" if is_open else "▸"))
            except Exception:
                pass
        self.detail_open_stash[key] = is_open
        self._on_content_configure()
        return is_open

    def toggle_part_details(self, key):
        key = str(key)
        details = self.detail_frames.get(key)
        if details is None:
            return False
        return self.set_part_details_open(key, not bool(details.winfo_manager()))

    def set_group_open(self, key, is_open):
        key = str(key)
        details = self.group_detail_frames.get(key)
        button = self.group_detail_buttons.get(key)
        if details is None:
            return False
        is_open = bool(is_open)
        if is_open:
            if not details.winfo_manager():
                details.pack(fill=tk.X)
        elif details.winfo_manager():
            details.pack_forget()
        if button is not None:
            try:
                button.configure(text=("▾" if is_open else "▸"))
            except Exception:
                pass
        self.group_open_stash[key] = is_open
        self._on_content_configure()
        return is_open

    def toggle_group(self, key):
        key = str(key)
        details = self.group_detail_frames.get(key)
        if details is None:
            return False
        return self.set_group_open(key, not bool(details.winfo_manager()))

    def set_box_piece_details_open(self, key, is_open):
        key = str(key)
        details = self.box_piece_detail_frames.get(key)
        button = self.box_piece_detail_buttons.get(key)
        if details is None:
            return False
        is_open = bool(is_open)
        if is_open:
            if not details.winfo_manager():
                details.pack(fill=tk.X)
        elif details.winfo_manager():
            details.pack_forget()
        if button is not None:
            try:
                button.configure(text=("▾" if is_open else "▸"))
            except Exception:
                pass
        self.box_piece_detail_open_stash[key] = is_open
        self._on_content_configure()
        return is_open

    def toggle_box_piece_details(self, key):
        key = str(key)
        details = self.box_piece_detail_frames.get(key)
        if details is None:
            return False
        return self.set_box_piece_details_open(
            key,
            not bool(details.winfo_manager()),
        )
