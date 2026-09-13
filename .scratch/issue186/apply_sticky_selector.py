from pathlib import Path

path = Path("fold_designer_bridge.py")
text = path.read_text(encoding="utf-8")

anchor = '''def _phase6_build_persistent_top_area(self):\n    """Operator layout: top commands, scrollable left inputs, right controls/canvas."""\n'''
helper = '''def _phase6_refresh_sticky_structure_tree(self):\n    """Keep the one #124 Structure Tree on-screen while lower left inputs scroll.\n\n    This is presentation-only.  The existing Treeview remains the single\n    navigation surface and continues to consume DM7 stable identities/callbacks.\n    A spacer owns its normal layout slot; ``place`` only offsets that same widget\n    against the left Canvas viewport.\n    """\n    canvas = getattr(self, "left_scroll_canvas", None)\n    host = getattr(self, "structure_tree_host", None)\n    spacer = getattr(self, "structure_tree_spacer", None)\n    if canvas is None or host is None or spacer is None:\n        return\n    try:\n        requested_height = max(1, int(host.winfo_reqheight()))\n        current_height = int(float(spacer.cget("height") or 0))\n        if current_height != requested_height:\n            spacer.configure(height=requested_height)\n        base_y = float(spacer.winfo_y())\n        scroll_y = float(canvas.canvasy(0))\n        host.place_configure(\n            x=0, y=int(round(max(base_y, scroll_y))),\n            relwidth=1.0, height=requested_height,\n        )\n        host.lift()\n    except Exception:\n        # Presentation refresh must never block manufacturing/navigation state.\n        return\n\n\n'''+anchor
if anchor not in text:
    raise SystemExit("persistent-top anchor not found")
text = text.replace(anchor, helper, 1)

old_scroll = '''    self.left_scrollbar = original.ttk.Scrollbar(\n        self.root,\n        orient=original.tk.VERTICAL,\n        command=self.left_scroll_canvas.yview,\n    )\n    self.left_scroll_canvas.configure(yscrollcommand=self.left_scrollbar.set)\n'''
new_scroll = '''    def _left_scroll_command(*args):\n        self.left_scroll_canvas.yview(*args)\n        _phase6_refresh_sticky_structure_tree(self)\n\n    def _left_yview_changed(first, last):\n        self.left_scrollbar.set(first, last)\n        _phase6_refresh_sticky_structure_tree(self)\n\n    self.left_scrollbar = original.ttk.Scrollbar(\n        self.root,\n        orient=original.tk.VERTICAL,\n        command=_left_scroll_command,\n    )\n    self.left_scroll_canvas.configure(yscrollcommand=_left_yview_changed)\n'''
if old_scroll not in text:
    raise SystemExit("left-scroll block not found")
text = text.replace(old_scroll, new_scroll, 1)

old_sync = '''            if bbox is not None:\n                self.left_scroll_canvas.configure(scrollregion=bbox)\n        except Exception:\n            pass\n'''
new_sync = '''            if bbox is not None:\n                self.left_scroll_canvas.configure(scrollregion=bbox)\n            _phase6_refresh_sticky_structure_tree(self)\n        except Exception:\n            pass\n'''
if old_sync not in text:
    raise SystemExit("left-scrollregion sync block not found")
text = text.replace(old_sync, new_sync, 1)

old_host = '''    self.structure_tree_host = original.ttk.Frame(self.left)\n    self.structure_tree_host.pack(fill=original.tk.X, pady=(0, 6))\n    self.structure_tree = original.ttk.Treeview(\n'''
new_host = '''    # #186: reserve the Tree's normal flow slot, but render that same single\n    # Structure Tree as a sticky navigation surface.  Only lower inputs scroll.\n    self.structure_tree_spacer = original.ttk.Frame(self.left, height=1)\n    self.structure_tree_spacer.pack(fill=original.tk.X, pady=(0, 6))\n    self.structure_tree_spacer.pack_propagate(False)\n    self.structure_tree_host = original.ttk.Frame(self.left)\n    self.structure_tree_host.place(x=0, y=0, relwidth=1.0)\n    self.structure_tree = original.ttk.Treeview(\n'''
if old_host not in text:
    raise SystemExit("structure-tree host block not found")
text = text.replace(old_host, new_host, 1)

old_tree_pack = '''    self.structure_tree_scrollbar.pack(side=original.tk.RIGHT, fill=original.tk.Y)\n    self.structure_tree.pack(side=original.tk.LEFT, fill=original.tk.BOTH, expand=True)\n    self.structure_tree.tag_configure("hidden", foreground="#777777")\n'''
new_tree_pack = '''    self.structure_tree_scrollbar.pack(side=original.tk.RIGHT, fill=original.tk.Y)\n    self.structure_tree.pack(side=original.tk.LEFT, fill=original.tk.BOTH, expand=True)\n    self.structure_tree_spacer.configure(\n        height=max(1, int(self.structure_tree_host.winfo_reqheight()))\n    )\n    self.root.after_idle(lambda: _phase6_refresh_sticky_structure_tree(self))\n    self.structure_tree.tag_configure("hidden", foreground="#777777")\n'''
if old_tree_pack not in text:
    raise SystemExit("structure-tree pack block not found")
text = text.replace(old_tree_pack, new_tree_pack, 1)

path.write_text(text, encoding="utf-8")
