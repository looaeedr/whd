# -*- coding: utf-8 -*-
"""Shared WHD engineering-workbench presentation tokens and adapters.

This module is presentation-only.  It owns colors and widget/render styling,
not application state, project truth, topology, geometry, or output semantics.
"""
from __future__ import annotations

from types import MappingProxyType
from tkinter import ttk


WHD_THEME = MappingProxyType({
    "background": "#121214",
    "panel": "#1e1e24",
    "input": "#151518",
    "text": "#e0e0e6",
    "muted_text": "#8e8e93",
    "action": "#0067c5",
    "action_hover": "#0070d9",
    "action_pressed": "#005bbf",
    "canvas": "#0d0d0f",
    "corner_data_canvas": "#000000",
})

# Semantic accents remain role-specific; they are deliberately not flattened
# into the generic action color.
WHD_SEMANTIC_COLORS = MappingProxyType({
    "success": "#30d158",
    "warning": "#ffd60a",
    "error": "#ff453a",
    "marking": "#ff9f0a",
    "datum": "#bf5af2",
})


MPL_CJK_FONT_FAMILIES = (
    "Microsoft JhengHei",
    "Noto Sans CJK TC",
    "Noto Sans CJK SC",
    "PingFang TC",
    "Arial Unicode MS",
    "DejaVu Sans",
    "sans-serif",
)


def _scaled_px(value: int, text_scale: float) -> int:
    try:
        factor = max(1.0, float(text_scale))
    except (TypeError, ValueError):
        factor = 1.0
    return max(1, int(round(value * factor)))


def apply_ttk_dark_theme(root, *, text_scale: float = 1.0, style=None):
    """Apply the shared dark contract to one Tk root and its ttk styles."""
    colors = WHD_THEME
    root.configure(background=colors["background"])
    style = style or ttk.Style(root)
    try:
        style.theme_use("default")
    except Exception:
        pass

    rowheight = _scaled_px(24, text_scale)
    padding_y = _scaled_px(4, text_scale)

    style.configure("TFrame", background=colors["panel"])
    style.configure("TLabel", background=colors["panel"], foreground=colors["text"])
    style.configure(
        "TButton",
        background=colors["panel"], foreground=colors["text"],
        padding=(8, padding_y), borderwidth=1, relief="raised",
    )
    style.map(
        "TButton",
        background=[("disabled", colors["background"]), ("pressed", colors["background"]), ("active", colors["input"])],
        foreground=[("disabled", colors["muted_text"]), ("active", colors["text"])],
    )
    style.configure(
        "Secondary.TButton",
        background=colors["panel"], foreground=colors["text"],
        padding=(8, padding_y), borderwidth=1, relief="raised",
    )
    style.map(
        "Secondary.TButton",
        background=[("disabled", colors["background"]), ("pressed", colors["background"]), ("active", colors["input"])],
        foreground=[("disabled", colors["muted_text"]), ("active", colors["text"])],
        bordercolor=[("focus", colors["action"])],
    )
    style.configure(
        "Primary.TButton",
        background=colors["action"], foreground="#ffffff",
        padding=(10, padding_y), borderwidth=1, relief="raised",
    )
    style.map(
        "Primary.TButton",
        background=[("disabled", colors["panel"]), ("pressed", colors["action_pressed"]), ("active", colors["action_hover"])],
        foreground=[("disabled", colors["muted_text"]), ("pressed", "#ffffff"), ("active", "#ffffff")],
        bordercolor=[("focus", colors["action"])],
    )
    for widget_style in ("TCheckbutton", "TRadiobutton"):
        style.configure(widget_style, background=colors["panel"], foreground=colors["text"])
        style.map(
            widget_style,
            background=[("active", colors["panel"])],
            foreground=[("disabled", colors["muted_text"]), ("active", colors["text"])],
        )

    style.configure(
        "TEntry",
        fieldbackground=colors["input"],
        foreground=colors["text"],
        background=colors["input"],
        insertcolor=colors["text"],
        borderwidth=1,
        relief="sunken",
    )
    style.map(
        "TEntry",
        fieldbackground=[("readonly", colors["panel"]), ("disabled", colors["background"])],
        foreground=[("disabled", colors["muted_text"]), ("readonly", colors["text"])],
        bordercolor=[("focus", colors["action"])],
    )
    style.configure("Editable.TEntry",
        fieldbackground=colors["input"], foreground=colors["text"],
        background=colors["input"], insertcolor=colors["text"],
        borderwidth=1, relief="sunken",
    )
    style.map(
        "Editable.TEntry",
        fieldbackground=[("disabled", colors["background"])],
        foreground=[("disabled", colors["muted_text"])],
        bordercolor=[("focus", colors["action"])],
    )
    style.configure("Readonly.TEntry",
        fieldbackground=colors["panel"], foreground=colors["text"],
        background=colors["panel"], borderwidth=1, relief="flat",
    )
    style.map(
        "Readonly.TEntry",
        foreground=[("disabled", colors["muted_text"])],
        bordercolor=[("focus", colors["action"])],
    )
    style.configure(
        "TCombobox",
        fieldbackground=colors["input"],
        background=colors["input"],
        foreground=colors["text"],
        arrowcolor=colors["text"],
        selectbackground=colors["action"],
        selectforeground="#ffffff",
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", colors["panel"]), ("disabled", colors["background"])],
        foreground=[("disabled", colors["muted_text"]), ("readonly", colors["text"])],
        arrowcolor=[("disabled", colors["muted_text"])],
    )
    style.configure(
        "TMenubutton",
        background=colors["panel"],
        foreground=colors["text"],
        arrowcolor=colors["text"],
        padding=(8, padding_y),
        borderwidth=1,
        relief="raised",
    )
    style.map(
        "TMenubutton",
        background=[("disabled", colors["background"]), ("pressed", colors["background"]), ("active", colors["input"])],
        foreground=[("disabled", colors["muted_text"])],
        arrowcolor=[("disabled", colors["muted_text"])],
    )
    style.configure(
        "Secondary.TMenubutton",
        background=colors["panel"], foreground=colors["text"],
        arrowcolor=colors["text"], padding=(8, padding_y),
        borderwidth=1, relief="raised",
    )
    style.map(
        "Secondary.TMenubutton",
        background=[("disabled", colors["background"]), ("pressed", colors["background"]), ("active", colors["input"])],
        foreground=[("disabled", colors["muted_text"])],
        arrowcolor=[("disabled", colors["muted_text"])],
    )
    style.configure(
        "Selector.TMenubutton",
        background=colors["input"], foreground=colors["text"],
        arrowcolor=colors["action"], padding=(8, padding_y),
        borderwidth=1, relief="sunken",
    )
    style.map(
        "Selector.TMenubutton",
        background=[("disabled", colors["panel"]), ("pressed", colors["background"]), ("active", colors["panel"])],
        foreground=[("disabled", colors["muted_text"])],
        arrowcolor=[("disabled", colors["muted_text"]), ("active", colors["action"])],
        bordercolor=[("focus", colors["action"])],
    )

    style.configure(
        "Treeview",
        background=colors["input"],
        fieldbackground=colors["input"],
        foreground=colors["text"],
        rowheight=rowheight,
        borderwidth=0,
    )
    style.map(
        "Treeview",
        background=[("selected", colors["action"])],
        foreground=[("selected", "#ffffff"), ("disabled", colors["muted_text"])],
    )
    style.configure(
        "Treeview.Heading",
        background=colors["panel"],
        foreground=colors["text"],
        relief="flat",
    )
    style.map("Treeview.Heading", background=[("active", colors["input"])])

    style.configure("TNotebook", background=colors["background"], borderwidth=0)
    style.configure("TNotebook.Tab", background=colors["panel"], foreground=colors["text"], padding=(10, padding_y))
    style.map(
        "TNotebook.Tab",
        background=[("selected", colors["input"]), ("active", colors["input"])],
        foreground=[("selected", colors["text"]), ("disabled", colors["muted_text"])],
    )
    style.configure(
        "TScrollbar",
        background=colors["panel"],
        troughcolor=colors["background"],
        arrowcolor=colors["text"],
        bordercolor=colors["background"],
    )
    style.map("TScrollbar", background=[("active", colors["input"])])
    style.configure("TSeparator", background=colors["muted_text"])
    return style


def configure_tk_menu(menu):
    """Apply readable normal/active/disabled colors to a classic Tk Menu."""
    colors = WHD_THEME
    menu.configure(
        background=colors["panel"],
        foreground=colors["text"],
        activebackground=colors["action"],
        activeforeground="#ffffff",
        disabledforeground=colors["muted_text"],
        selectcolor=colors["action"],
        borderwidth=1,
        relief="solid",
    )
    return menu


def apply_mpl_dark_theme(figure, axes):
    """Apply dark canvas/readability styling after Matplotlib axes are cleared."""
    colors = WHD_THEME
    try:
        import matplotlib
        matplotlib.rcParams["font.family"] = "sans-serif"
        matplotlib.rcParams["font.sans-serif"] = list(MPL_CJK_FONT_FAMILIES[:-1])
        matplotlib.rcParams["axes.unicode_minus"] = False
    except Exception:
        pass
    if figure is not None and getattr(figure, "patch", None) is not None:
        figure.patch.set_facecolor(colors["canvas"])

    if axes is None:
        return axes
    if isinstance(axes, (list, tuple, set)):
        targets = tuple(axes)
    else:
        targets = (axes,)

    for ax in targets:
        if ax is None:
            continue
        set_facecolor = getattr(ax, "set_facecolor", None)
        if callable(set_facecolor):
            set_facecolor(colors["canvas"])
        tick_params = getattr(ax, "tick_params", None)
        if callable(tick_params):
            try:
                tick_params(colors=colors["muted_text"], labelcolor=colors["text"])
            except TypeError:
                tick_params(colors=colors["muted_text"])
        for getter in ("xaxis", "yaxis", "zaxis"):
            axis = getattr(ax, getter, None)
            if axis is None:
                continue
            label = getattr(axis, "label", None)
            if label is not None and callable(getattr(label, "set_color", None)):
                label.set_color(colors["text"])
            pane = getattr(axis, "pane", None)
            if pane is not None:
                try:
                    pane.set_facecolor(colors["panel"])
                    pane.set_edgecolor(colors["muted_text"])
                    pane.set_alpha(0.35)
                except Exception:
                    pass
        title = getattr(ax, "title", None)
        if title is not None and callable(getattr(title, "set_color", None)):
            title.set_color(colors["text"])
        grid = getattr(ax, "grid", None)
        if callable(grid):
            try:
                grid(True, color=colors["muted_text"], alpha=0.18)
            except TypeError:
                grid(True)
    return axes
