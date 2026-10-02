# -*- coding: utf-8 -*-
"""View-only builder for the Receiving Set/Bay selector controls.

This module owns Tk widget construction only. Canonical topology and selection
behavior remain in ReceivingSetBayAdapter and Bridge callbacks.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ReceivingSetBayControls:
    frame: object
    set_var: object
    bay_var: object
    set_selector: object
    bay_selector: object
    remove_set_button: object


def build_receiving_set_bay_controls(
    parent,
    *,
    tk,
    ttk,
    on_set_selected: Callable[[], object],
    on_bay_selected: Callable[[], object],
    on_resize_bays: Callable[[int], object],
    on_remove_set: Callable[[], object],
) -> ReceivingSetBayControls:
    """Construct the Set/Bay UI without owning Receiving product state."""
    frame = ttk.Frame(parent)
    set_var = tk.StringVar(master=frame, value="Set 1")
    bay_var = tk.StringVar(master=frame, value="Bay 1")

    ttk.Label(frame, text="受電箱").pack(side=tk.LEFT, padx=(0, 6))

    set_selector = ttk.Combobox(
        frame,
        textvariable=set_var,
        state="readonly",
        width=7,
    )
    set_selector.pack(side=tk.LEFT, padx=(0, 4))
    set_selector.bind("<<ComboboxSelected>>", lambda _event: on_set_selected())

    bay_selector = ttk.Combobox(
        frame,
        textvariable=bay_var,
        state="readonly",
        width=7,
    )
    bay_selector.pack(side=tk.LEFT, padx=(0, 4))
    bay_selector.bind("<<ComboboxSelected>>", lambda _event: on_bay_selected())

    ttk.Button(
        frame,
        text="−Bay",
        width=5,
        command=lambda: on_resize_bays(-1),
    ).pack(side=tk.LEFT, padx=(0, 2))
    ttk.Button(
        frame,
        text="+Bay",
        width=5,
        command=lambda: on_resize_bays(1),
    ).pack(side=tk.LEFT, padx=(0, 2))

    remove_set_button = ttk.Button(
        frame,
        text="刪Set",
        width=5,
        command=on_remove_set,
    )
    remove_set_button.pack(side=tk.LEFT)

    return ReceivingSetBayControls(
        frame=frame,
        set_var=set_var,
        bay_var=bay_var,
        set_selector=set_selector,
        bay_selector=bay_selector,
        remove_set_button=remove_set_button,
    )
