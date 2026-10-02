"""Focused T2 layout package; no committed domain-state ownership."""

from .main_window import build_main_layout
from .styles import configure_styles
from .toolbar import _project_toolbar_presentation

__all__ = [
    "_project_toolbar_presentation",
    "build_main_layout",
    "configure_styles",
]
