"""Scrollable left-panel presentation shell."""

import tkinter as tk


def build_scroll_shell(host, left_container):
    # 控制面板卡片
    ctrl_card = tk.Frame(left_container, bg=host.COLOR_PANEL, bd=0)
    ctrl_card.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # 內距包裝框（使用 Canvas + Scrollbar 支援捲動）
    scroll_canvas = tk.Canvas(ctrl_card, bg=host.COLOR_PANEL, highlightthickness=0)
    scrollbar = tk.Scrollbar(ctrl_card, orient=tk.VERTICAL, command=scroll_canvas.yview)
    scroll_canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    ctrl_pad_frame = tk.Frame(scroll_canvas, bg=host.COLOR_PANEL)
    scroll_win = scroll_canvas.create_window((0, 0), window=ctrl_pad_frame, anchor=tk.NW)

    def on_frame_configure(event):
        scroll_canvas.configure(scrollregion=scroll_canvas.bbox('all'))
    def on_canvas_resize(event):
        scroll_canvas.itemconfig(scroll_win, width=event.width)
    def on_mousewheel(event):
        scroll_canvas.yview_scroll(int(-1*(event.delta/120)), 'units')
    ctrl_pad_frame.bind('<Configure>', on_frame_configure)
    scroll_canvas.bind('<Configure>', on_canvas_resize)
    scroll_canvas.bind('<MouseWheel>', on_mousewheel)
    ctrl_pad_frame.bind('<MouseWheel>', on_mousewheel)
    return ctrl_pad_frame
