# -*- coding: utf-8 -*-
"""全域 GUI 文字縮放工具。

只調整文字與字型度量，不改 CAD 幾何、Canvas 座標或 DXF 尺寸。
"""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from typing import Any

from phase6_settings_center import normalize_ui_text_size, ui_text_size_factor


_NAMED_FONT_NAMES = (
    "TkDefaultFont", "TkTextFont", "TkFixedFont", "TkMenuFont",
    "TkHeadingFont", "TkCaptionFont", "TkSmallCaptionFont",
    "TkIconFont", "TkTooltipFont",
)


def _scaled_size(size: int | float, factor: float) -> int:
    size = int(round(float(size)))
    if size == 0:
        return 1
    sign = -1 if size < 0 else 1
    return sign * max(1, int(round(abs(size) * float(factor))))


def scaled_font_tuple(family: str, size: int | float, *styles: str, factor: float = 1.0):
    """建立依倍率縮放的 Tk font tuple。"""
    return (family, _scaled_size(size, factor), *styles)


class TextScaleController:
    """同一個 Tk interpreter 只需要一個文字縮放控制器。"""

    def __init__(self, root: tk.Misc):
        self.root = root
        self.size_key = "small"
        self.factor = 1.0
        self._named_font_base_sizes: dict[str, int] = {}
        self._capture_named_fonts()
        setattr(root, "_ui_text_scale_controller", self)
        root.bind_all("<Map>", self._on_widget_map, add="+")

    @classmethod
    def for_widget(cls, widget: tk.Misc) -> "TextScaleController":
        current: Any = widget
        while current is not None:
            existing = getattr(current, "_ui_text_scale_controller", None)
            if isinstance(existing, cls):
                return existing
            current = getattr(current, "master", None)
        return cls(widget)

    def _capture_named_fonts(self) -> None:
        for name in _NAMED_FONT_NAMES:
            try:
                font = tkfont.nametofont(name, root=self.root)
                self._named_font_base_sizes[name] = int(font.cget("size"))
            except Exception:
                continue

    def scaled_font(self, family: str, size: int | float, *styles: str):
        return scaled_font_tuple(family, size, *styles, factor=self.factor)

    def apply(self, value) -> str:
        key = normalize_ui_text_size(value)
        self.size_key = key
        self.factor = ui_text_size_factor(key)
        self._apply_named_fonts()
        self._apply_widget_tree(self.root)
        try:
            self.root.update_idletasks()
        except Exception:
            pass
        return key

    def _apply_named_fonts(self) -> None:
        for name, base_size in self._named_font_base_sizes.items():
            try:
                tkfont.nametofont(name, root=self.root).configure(
                    size=_scaled_size(base_size, self.factor)
                )
            except Exception:
                continue

    def _on_widget_map(self, event) -> None:
        try:
            self._apply_widget_tree(event.widget)
        except Exception:
            pass

    def _apply_widget_tree(self, widget: tk.Misc) -> None:
        self._apply_widget_font(widget)
        if isinstance(widget, tk.Canvas):
            self._install_canvas_wrapper(widget)
            self._rescale_existing_canvas_text(widget)
        try:
            children = widget.winfo_children()
        except Exception:
            children = ()
        for child in children:
            self._apply_widget_tree(child)

    def _font_descriptor(self, font_spec):
        try:
            font = tkfont.Font(root=self.root, font=font_spec)
            actual = font.actual()
        except Exception:
            return None
        size = int(actual.get("size", 0) or 0)
        if not size:
            return None
        styles = []
        if actual.get("weight") == "bold":
            styles.append("bold")
        if actual.get("slant") == "italic":
            styles.append("italic")
        if actual.get("underline"):
            styles.append("underline")
        if actual.get("overstrike"):
            styles.append("overstrike")
        return (actual.get("family") or "TkDefaultFont", size, *styles)

    @staticmethod
    def _is_named_font(font_spec) -> bool:
        text = str(font_spec or "").strip()
        return text in _NAMED_FONT_NAMES

    def _scale_descriptor(self, descriptor):
        if not descriptor:
            return descriptor
        family, size, *styles = descriptor
        return (family, _scaled_size(size, self.factor), *styles)

    def _apply_widget_font(self, widget: tk.Misc) -> None:
        try:
            keys = widget.keys()
        except Exception:
            return
        if "font" not in keys:
            return
        try:
            font_spec = widget.cget("font")
        except Exception:
            return
        if not font_spec or self._is_named_font(font_spec):
            return
        base = getattr(widget, "_ui_text_base_font", None)
        if base is None:
            base = self._font_descriptor(font_spec)
            if base is None:
                return
            setattr(widget, "_ui_text_base_font", base)
        try:
            widget.configure(font=self._scale_descriptor(base))
        except Exception:
            pass

    def _install_canvas_wrapper(self, canvas: tk.Canvas) -> None:
        if getattr(canvas, "_ui_text_create_wrapped", False):
            return
        original_create_text = canvas.create_text
        controller = self

        def create_text(*args, **kwargs):
            original_font = kwargs.get("font")
            base = None
            if original_font:
                base = controller._font_descriptor(original_font)
                if base:
                    kwargs["font"] = controller._scale_descriptor(base)
            item_id = original_create_text(*args, **kwargs)
            if base:
                fonts = getattr(canvas, "_ui_text_canvas_fonts", None)
                if fonts is None:
                    fonts = {}
                    setattr(canvas, "_ui_text_canvas_fonts", fonts)
                fonts[item_id] = base
            return item_id

        canvas.create_text = create_text
        setattr(canvas, "_ui_text_create_wrapped", True)

    def _rescale_existing_canvas_text(self, canvas: tk.Canvas) -> None:
        fonts = getattr(canvas, "_ui_text_canvas_fonts", None)
        if fonts is None:
            fonts = {}
            setattr(canvas, "_ui_text_canvas_fonts", fonts)
        try:
            item_ids = canvas.find_all()
        except Exception:
            return
        for item_id in item_ids:
            try:
                if canvas.type(item_id) != "text":
                    continue
                base = fonts.get(item_id)
                if base is None:
                    raw = canvas.itemcget(item_id, "font")
                    base = self._font_descriptor(raw)
                    if base is None:
                        continue
                    fonts[item_id] = base
                canvas.itemconfigure(item_id, font=self._scale_descriptor(base))
            except Exception:
                continue
