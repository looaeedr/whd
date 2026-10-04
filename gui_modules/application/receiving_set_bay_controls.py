# -*- coding: utf-8 -*-
"""View-only builder for Receiving layer/connection controls.

The legacy filename is retained for compatibility, but operator-facing terms are
層/連. Layer/connection state is projected from receiving_switch_layout; this module owns
Tk widgets only and never owns manufacturing geometry.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable


from ae_engine.receiving_switch_layout import RECEIVING_SWITCH_BRANDS


@dataclass(frozen=True)
class ReceivingSetBayControls:
    frame: object
    switch_brand_var: object
    switch_brand_selector: object
    layer_host: object
    add_layer_button: object


def build_receiving_set_bay_controls(
    parent,
    *,
    tk,
    ttk,
    on_switch_brand_selected: Callable[[str], object],
    on_add_layer: Callable[[], object],
) -> ReceivingSetBayControls:
    """Construct Receiving layer/connection shell without owning product state."""
    frame = ttk.Frame(parent)

    header = ttk.Frame(frame)
    header.pack(fill=tk.X, pady=(0, 4))
    ttk.Label(header, text="開關").pack(side=tk.LEFT, padx=(0, 6))
    switch_brand_var = tk.StringVar(master=header, value=RECEIVING_SWITCH_BRANDS[0])
    switch_brand_selector = ttk.Combobox(
        header,
        textvariable=switch_brand_var,
        values=RECEIVING_SWITCH_BRANDS,
        state="readonly",
        width=8,
    )
    switch_brand_selector.pack(side=tk.LEFT)
    switch_brand_selector.bind(
        "<<ComboboxSelected>>",
        lambda _event: on_switch_brand_selected(str(switch_brand_var.get())),
    )

    layer_host = ttk.Frame(frame)
    layer_host.pack(fill=tk.X)

    add_layer_button = ttk.Button(frame, text="＋層", command=on_add_layer)
    add_layer_button.pack(anchor=tk.W, pady=(2, 0))

    return ReceivingSetBayControls(
        frame=frame,
        switch_brand_var=switch_brand_var,
        switch_brand_selector=switch_brand_selector,
        layer_host=layer_host,
        add_layer_button=add_layer_button,
    )


def refresh_receiving_layer_rows(
    controls: ReceivingSetBayControls,
    *,
    tk,
    ttk,
    connection_counts: Iterable[int],
    on_resize_connections: Callable[[int, int], object],
    on_preview: Callable[[int], object],
) -> None:
    """Render exactly one operator row per layer."""
    host = controls.layer_host
    for child in tuple(host.winfo_children()):
        child.destroy()

    for layer_index, raw_count in enumerate(tuple(connection_counts)):
        connection_count = max(1, int(raw_count))
        row = ttk.Frame(host)
        row.pack(fill=tk.X, pady=(0, 3))
        ttk.Label(row, text=f"第{layer_index + 1}層", width=7, anchor=tk.W).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        ttk.Label(row, text=f"{connection_count}連", width=5, anchor=tk.W).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        ttk.Button(
            row,
            text="－連",
            width=5,
            command=lambda layer_index=layer_index: on_resize_connections(layer_index, -1),
        ).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(
            row,
            text="＋連",
            width=5,
            command=lambda layer_index=layer_index: on_resize_connections(layer_index, 1),
        ).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(
            row,
            text="預覽",
            width=6,
            command=lambda layer_index=layer_index: on_preview(layer_index),
        ).pack(side=tk.LEFT)
