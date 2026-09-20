# -*- coding: utf-8 -*-
from __future__ import annotations

import tkinter as tk

import pytest


@pytest.fixture
def tk_root():
    root = tk.Tk()
    root.withdraw()
    try:
        yield root
    finally:
        try:
            root.update_idletasks()
        except Exception:
            pass
        root.destroy()
