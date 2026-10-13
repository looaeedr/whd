"""Scrollable Receiving content without global mousewheel hooks or nested grabs.

Both Windows <MouseWheel> and Linux button 4/5 are scoped to the hovered
container. Native Listbox/Text/Combobox and embedded diagram canvases retain
their own wheel behavior. The content frame survives dynamic widget rebuilds.
"""
from __future__ import annotations


def make_scrollable_frame(parent, *, tk, ttk, width=520, height=340):
    holder = ttk.Frame(parent)
    holder.columnconfigure(0, weight=1)
    holder.rowconfigure(0, weight=1)
    viewport = tk.Canvas(
        holder, width=width, height=height, highlightthickness=0,
        borderwidth=0, takefocus=0,
    )
    vertical = ttk.Scrollbar(holder, orient="vertical", command=viewport.yview)
    horizontal = ttk.Scrollbar(holder, orient="horizontal", command=viewport.xview)
    viewport.grid(row=0, column=0, sticky="nsew")
    vertical.grid(row=0, column=1, sticky="ns")
    horizontal.grid(row=1, column=0, sticky="ew")
    viewport.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
    content = ttk.Frame(viewport)
    window_item = viewport.create_window((0, 0), window=content, anchor="nw")
    pending = {"value": False}
    attached = set()

    def wheel(event):
        if not holder.winfo_exists():
            return
        number = getattr(event, "num", 0)
        delta = getattr(event, "delta", 0)
        units = -1 if delta > 0 or number == 4 else 1
        if getattr(event, "state", 0) & 1:
            if viewport.xview() != (0.0, 1.0):
                viewport.xview_scroll(units, "units")
                return "break"
        elif viewport.yview() != (0.0, 1.0):
            viewport.yview_scroll(units, "units")
            return "break"
        return None

    def bind_tree(node):
        # Do not intercept native scrollable controls or nested diagrams.
        for widget in node.winfo_children():
            widget_key = (str(widget), widget.winfo_id())
            if widget_key not in attached:
                attached.add(widget_key)
                if widget.winfo_class() not in (
                    "Listbox", "Text", "Treeview", "TCombobox", "Canvas",
                    "TScrollbar", "Scrollbar",
                ):
                    for event in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                        widget.bind(event, wheel, add="+")
            if widget.winfo_class() not in ("Canvas", "Listbox", "Text"):
                bind_tree(widget)

    def update():
        pending["value"] = False
        if not holder.winfo_exists():
            return
        natural = max(1, content.winfo_reqwidth())
        usable = max(1, viewport.winfo_width())
        desired = max(natural, usable)
        if float(viewport.itemcget(window_item, "width") or 0) != float(desired):
            viewport.itemconfigure(window_item, width=desired)
        viewport.configure(scrollregion=viewport.bbox("all"))
        bind_tree(content)

    def request(_event=None):
        if not pending["value"] and holder.winfo_exists():
            pending["value"] = True
            holder.after_idle(update)

    content.bind("<Configure>", request)
    viewport.bind("<Configure>", request)
    for event in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        viewport.bind(event, wheel)
        content.bind(event, wheel, add="+")
    holder._receiving_scroll_content = content
    holder._receiving_scroll_viewport = viewport
    holder._receiving_scroll_update = request
    request()
    return holder, content, viewport
