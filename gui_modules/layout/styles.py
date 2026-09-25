"""T2-owned ttk/theme presentation setup."""

from tkinter import ttk

from whd_theme import apply_ttk_dark_theme


def configure_styles(host):
    host.style = apply_ttk_dark_theme(host.root, text_scale=1.0, style=ttk.Style(host.root))

    # Notebook 樣式
    host.style.configure('TNotebook', background=host.COLOR_BG, borderwidth=0)
    host.style.configure('TNotebook.Tab', 
                         background=host.COLOR_PANEL, 
                         foreground=host.COLOR_TEXT, 
                         padding=[15, 6], 
                         font=host._ui_text_controller.scaled_font('Microsoft JhengHei', 10, 'bold'),
                         borderwidth=0)
    host.style.map('TNotebook.Tab', 
                   background=[('selected', host.COLOR_ACCENT)], 
                   foreground=[('selected', '#ffffff')])

    # ComboBox 樣式
    host.style.configure('TCombobox', 
                         fieldbackground=host.COLOR_INPUT_BG, 
                         background=host.COLOR_PANEL, 
                         foreground=host.COLOR_TEXT,
                         arrowcolor=host.COLOR_TEXT)

    # Label 樣式
    host.style.configure('TLabel', background=host.COLOR_PANEL, foreground=host.COLOR_TEXT, font=host._ui_text_controller.scaled_font('Microsoft JhengHei', 10))
    host.style.configure('Title.TLabel', background=host.COLOR_PANEL, foreground=host.COLOR_ACCENT, font=host._ui_text_controller.scaled_font('Microsoft JhengHei', 12, 'bold'))
    host.style.configure('Header.TLabel', background=host.COLOR_BG, foreground=host.COLOR_TEXT, font=host._ui_text_controller.scaled_font('Microsoft JhengHei', 14, 'bold'))
