"""Right workspace notice and compatibility-only presentation hosts."""

import tkinter as tk


def build_workspace(host, main_paned):
    # 右側：舊 2D 入口已收斂至 Fold Designer「截角資料」
    # ==========================================
    right_container = tk.Frame(main_paned, bg=host.COLOR_BG)
    main_paned.add(right_container, stretch="always")

    notice = tk.Frame(right_container, bg=host.COLOR_PANEL, bd=0)
    notice.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    tk.Label(
        notice,
        text="展開圖已移至折彎 / 3D 設計的「截角資料」",
        bg=host.COLOR_PANEL, fg=host.COLOR_TEXT,
        font=('Microsoft JhengHei', 14, 'bold'),
    ).pack(pady=(80, 12))
    tk.Label(
        notice,
        text="板件、2D 展開與 3D 共用同一 authoritative workspace；請由截角資料選擇實際板件。",
        bg=host.COLOR_PANEL, fg=host.COLOR_TEXT_MUTED,
        font=('Microsoft JhengHei', 10),
    ).pack(pady=(0, 18))
    tk.Button(
        notice, text="開啟折彎 / 3D 設計",
        command=host.open_original_fold_designer,
        font=('Microsoft JhengHei', 10, 'bold'),
        bg=host.COLOR_ACCENT, fg="#ffffff",
        activebackground=host.COLOR_ACCENT,
        activeforeground="#ffffff", bd=0, cursor="hand2",
        padx=16, pady=8,
    ).pack()

    # Compatibility-only widget state for callbacks that have not yet
    # been split from the legacy setup helpers. This host is never
    # packed and is not a navigation surface or a 2D geometry owner.
    host._legacy_2d_compat_host = tk.Frame(right_container, bg=host.COLOR_BG)
    host.tab_z = tk.Frame(host._legacy_2d_compat_host, bg=host.COLOR_BG)
    host.setup_tab_z_ui()
    host.tab_head = tk.Frame(host._legacy_2d_compat_host, bg=host.COLOR_BG)
    host.setup_tab_endcap_ui(host.tab_head, 'head')
    host.tab_tail = tk.Frame(host._legacy_2d_compat_host, bg=host.COLOR_BG)
    host.setup_tab_endcap_ui(host.tab_tail, 'tail')
    host.tab_door = tk.Frame(host._legacy_2d_compat_host, bg=host.COLOR_BG)
    host.setup_tab_door_ui()
    host.tab_base_plate = tk.Frame(host._legacy_2d_compat_host, bg=host.COLOR_BG)
    host.setup_tab_base_plate_ui()
    host.tab_indicator_box = tk.Frame(host._legacy_2d_compat_host, bg=host.COLOR_BG)
    host.setup_tab_indicator_box_ui()
    host.tab_indicator_door = tk.Frame(host._legacy_2d_compat_host, bg=host.COLOR_BG)
    host.setup_tab_indicator_door_ui()

    host.base_plate_shrink_same_var.trace_add("write", lambda *args: host.sync_base_plate_shrink())
    host.on_base_plate_same_toggle()
    host._phase6_refresh_presence_ui()
