# -*- coding: utf-8 -*-
"""Tk-only presentation owner for Phase6 Registry diagnostics surfaces.

Certified Registry rules, promotion semantics, 3D validation, manufacturing geometry,
and AssemblyJoint mutation remain external owners and enter only through callbacks.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Mapping, Sequence

from whd_theme import WHD_THEME, configure_tk_menu


def build_registry_choice(
    parent,
    variable,
    choices,
    *,
    present_token: Callable[..., str],
    width=18,
    presentation_field="choice",
):
    """Build a localized Registry selector without owning raw enum semantics."""
    display_var = tk.StringVar(
        master=parent,
        value=present_token(
            variable.get(),
            presentation_field=presentation_field,
            source_adapter="registry_choice",
        ),
    )
    button = ttk.Menubutton(
        parent,
        textvariable=display_var,
        width=width,
        style="Selector.TMenubutton",
    )
    menu = configure_tk_menu(tk.Menu(button, tearoff=False))

    def choose(raw):
        variable.set(str(raw))
        display_var.set(
            present_token(
                raw,
                presentation_field=presentation_field,
                source_adapter="registry_choice",
            )
        )

    for choice in tuple(choices or ()):
        menu.add_command(
            label=present_token(
                choice,
                presentation_field=presentation_field,
                source_adapter="registry_choice",
            ),
            command=lambda v=str(choice): choose(v),
        )
    button.configure(menu=menu)

    def sync_display(*_args):
        value = present_token(
            variable.get(),
            presentation_field=presentation_field,
            source_adapter="registry_choice",
        )
        if display_var.get() != value:
            display_var.set(value)

    variable.trace_add("write", sync_display)
    button._phase6_display_var = display_var
    button._phase6_raw_var = variable
    button._phase6_presentation_field = presentation_field
    return button


class Phase6RegistryDiagnosticsPanel:
    """Own Registry editor and assembly-diagnostics Tk construction only."""

    def __init__(
        self,
        *,
        owner,
        present_token: Callable[..., str],
        formula_display: Callable[..., str],
        formula_raw: Callable[[str], str],
        preconditions_display: Callable[[str], str],
        preconditions_raw: Callable[[str], str],
        source_display: Callable[..., str],
        source_raw: Callable[[str], str],
        validate_formula: Callable[[], object],
        preview_payload: Callable[[], object],
        preview_assembly_3d: Callable[[], object],
        save_candidate: Callable[[], object],
        run_formula_matrix: Callable[[], object],
        promote_candidate: Callable[[], object],
        load_rule_rows: Callable[[], Sequence[Mapping[str, object]]],
        rule_record: Callable[[str], Mapping[str, object]],
        joint_rows: Callable[[], Sequence[Mapping[str, object]]],
        add_joint: Callable[[], object],
        delete_joint: Callable[[], object],
        on_diagnostic_changed: Callable[[], object],
        create_promotion_candidates: Callable[[], object],
        diagnostic_ids: Callable[[object], Sequence[str]],
    ) -> None:
        self.owner = owner
        self._present_token = present_token
        self._formula_display = formula_display
        self._formula_raw = formula_raw
        self._preconditions_display = preconditions_display
        self._preconditions_raw = preconditions_raw
        self._source_display = source_display
        self._source_raw = source_raw
        self._validate_formula = validate_formula
        self._preview_payload = preview_payload
        self._preview_assembly_3d = preview_assembly_3d
        self._save_candidate = save_candidate
        self._run_formula_matrix = run_formula_matrix
        self._promote_candidate = promote_candidate
        self._load_rule_rows = load_rule_rows
        self._rule_record = rule_record
        self._joint_rows = joint_rows
        self._add_joint = add_joint
        self._delete_joint = delete_joint
        self._on_diagnostic_changed = on_diagnostic_changed
        self._create_promotion_candidates = create_promotion_candidates
        self._diagnostic_ids = diagnostic_ids

        self.relief_registry_window = None
        self.relief_registry_notebook = None
        self.relief_registry_rule_tree = None
        self.relief_registry_preview_canvas = None
        self.relief_registry_save_candidate_button = None
        self.relief_registry_promote_button = None
        self.relief_joint_tree = None
        self.relief_joint_relation_choices = ()

        self.assembly_diagnostics_frame = None
        self.assembly_relief_clearance_entry = None
        self.assembly_relief_promotion_button = None

    def _publish(self, name: str, value):
        setattr(self, name, value)
        setattr(self.owner, name, value)
        return value

    @staticmethod
    def _bind_translated_var(raw_var, display_var, to_display, to_raw):
        busy = {"value": False}

        def raw_changed(*_args):
            if busy["value"]:
                return
            busy["value"] = True
            try:
                display_var.set(to_display(raw_var.get()))
            finally:
                busy["value"] = False

        def display_changed(*_args):
            if busy["value"]:
                return
            busy["value"] = True
            try:
                raw_var.set(to_raw(display_var.get()))
            finally:
                busy["value"] = False

        raw_var.trace_add("write", raw_changed)
        display_var.trace_add("write", display_changed)
        raw_changed()
        display_var._phase6_raw_var = raw_var
        return display_var

    @staticmethod
    def _configure_floating_surface(window, owner, *, modal=False):
        try:
            return_focus = owner.focus_get()
        except Exception:
            return_focus = None
        if return_focus is None:
            return_focus = owner
        window._phase6_return_focus = return_focus

        def close_surface(_event=None):
            try:
                window.grab_release()
            except Exception:
                pass
            try:
                window.destroy()
            finally:
                try:
                    if bool(return_focus.winfo_exists()):
                        return_focus.after_idle(return_focus.focus_set)
                except Exception:
                    pass
            return "break"

        window._phase6_close_surface = close_surface
        try:
            window.transient(owner)
        except Exception:
            pass
        try:
            window.configure(takefocus=True)
        except Exception:
            pass
        window._phase6_foreground_role = "floating_surface"
        try:
            window.bind("<Escape>", close_surface, add="+")
            window.protocol("WM_DELETE_WINDOW", close_surface)
            window.lift()
            window.after_idle(window.focus_set)
        except Exception:
            pass
        if modal:
            try:
                window.grab_set()
            except Exception:
                pass
        return window

    def _choice(self, parent, variable, choices, *, width=18, presentation_field="choice"):
        return build_registry_choice(
            parent,
            variable,
            choices,
            present_token=self._present_token,
            width=width,
            presentation_field=presentation_field,
        )

    def refresh_rule_rows(self, rows=None):
        tree = self.relief_registry_rule_tree
        if tree is None:
            return ()
        if rows is None:
            rows = self._load_rule_rows()
        rows = tuple(dict(row) for row in (rows or ()))
        for item in tree.get_children():
            tree.delete(item)
        for row in (item for item in rows if bool(item.get("active", True))):
            tree.insert(
                "",
                "end",
                iid=f"{row['rule_id']}@{row['revision']}",
                values=(
                    self._present_token(
                        row["rule_id"],
                        presentation_field="rule_id",
                        source_adapter="registry_rule_tree",
                    ),
                    row["revision"],
                    self._present_token(
                        row.get("trust_level", ""),
                        presentation_field="trust_level",
                        source_adapter="registry_rule_tree",
                    ),
                    self._present_token(
                        row.get("assembly_intent", ""),
                        presentation_field="assembly_intent",
                        source_adapter="registry_rule_tree",
                    ),
                    row.get("topology_levels", ""),
                ),
            )
        return rows

    def populate_rule_form(self, raw=None):
        tree = self.relief_registry_rule_tree
        if raw is None:
            if tree is None or not tree.selection():
                return None
            raw = self._rule_record(tree.selection()[0])
        raw = dict(raw or {})
        if not raw:
            return None

        formula = dict(raw.get("formula", {}) or {})
        self.relief_registry_rule_name_var.set(
            self._present_token(
                raw.get("rule_id", ""),
                presentation_field="rule_id",
                source_adapter="registry_rule_selection",
            )
        )
        setters = (
            (self.relief_registry_rule_id_var, raw.get("rule_id", "")),
            (self.relief_registry_family_var, raw.get("cabinet_family", "ANY")),
            (self.relief_registry_part_role_var, raw.get("part_role", "HEAD_OR_TAIL")),
            (self.relief_registry_joint_face_var, raw.get("joint_face", "TOP")),
            (self.relief_registry_intent_var, raw.get("assembly_intent", "INSERT_OVERLAY")),
            (self.relief_registry_topology_var, raw.get("topology_levels", 2)),
            (self.relief_registry_primary_u_var, formula.get("primary_u", "")),
            (self.relief_registry_primary_v_var, formula.get("primary_v", "")),
            (self.relief_registry_secondary_u_var, formula.get("secondary_u", "")),
            (
                self.relief_registry_secondary_depth_var,
                formula.get("secondary_depth", ""),
            ),
            (
                self.relief_registry_preconditions_var,
                ",".join(str(v) for v in (raw.get("preconditions", ()) or ())),
            ),
            (self.relief_registry_source_var, str(raw.get("source", ""))),
        )
        for var, value in setters:
            var.set(str(value))

        sig = list(raw.get("joint_signature", ()) or ())
        extra = sig[1].get("relation") if len(sig) > 1 else "NONE"
        self.relief_registry_extra_joint_var.set(str(extra))
        if len(sig) > 1:
            self.relief_registry_extra_target_role_var.set(
                str(sig[1].get("target_role", "REAR_PANEL"))
            )
        return raw

    def refresh_joint_rows(self, rows=None):
        tree = self.relief_joint_tree
        if tree is None:
            return ()
        if rows is None:
            rows = self._joint_rows()
        rows = tuple(dict(row) for row in (rows or ()))
        for item in tree.get_children():
            tree.delete(item)
        for row in rows:
            tree.insert(
                "",
                "end",
                iid=str(row["joint_id"]),
                values=(
                    self._present_token(
                        row.get("subject_part", ""),
                        presentation_field="subject_part",
                        source_adapter="joint_tree",
                    ),
                    self._present_token(
                        row.get("target_part", ""),
                        presentation_field="target_part",
                        source_adapter="joint_tree",
                    ),
                    self._present_token(
                        row.get("relation", ""),
                        presentation_field="relation",
                        source_adapter="joint_tree",
                    ),
                    self._present_token(
                        row.get("source", ""),
                        presentation_field="source",
                        source_adapter="joint_tree",
                    ),
                    self._present_token(
                        row.get("subject_region", ""),
                        presentation_field="subject_region",
                        source_adapter="joint_tree",
                    ),
                    self._present_token(
                        row.get("target_region", ""),
                        presentation_field="target_region",
                        source_adapter="joint_tree",
                    ),
                ),
            )
        return rows

    def draw_registry_preview(self, payload=None):
        if payload is None:
            payload = self._preview_payload()
        if isinstance(payload, Mapping):
            result = payload.get("result")
            geometry = payload.get("geometry")
        else:
            result, geometry = payload
        canvas = self.relief_registry_preview_canvas
        if canvas is None:
            return result
        canvas.delete("all")
        geometry = dict(geometry or {})
        outer = geometry.get("outer")
        if outer:
            canvas.create_rectangle(*outer, outline="#777")
        if not result:
            return None
        for rect in tuple(geometry.get("cuts") or ()):
            canvas.create_rectangle(*rect, outline="#222", width=2)
        return result

    def open_registry_editor(self):
        existing = self.relief_registry_window
        try:
            if existing is not None and existing.winfo_exists():
                existing.deiconify()
                existing.lift()
                return existing
        except Exception:
            pass

        root = self.owner.root
        win = tk.Toplevel(root)
        win.title("截角資料庫／組合接合")
        win.geometry("1120x720")
        self._configure_floating_surface(win, root, modal=False)
        self._publish("relief_registry_window", win)

        notebook = ttk.Notebook(win)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self._publish("relief_registry_notebook", notebook)

        rules_tab = ttk.Frame(notebook, padding=8)
        joints_tab = ttk.Frame(notebook, padding=8)
        notebook.add(rules_tab, text="截角公式")
        notebook.add(joints_tab, text="組合接合")

        left = ttk.Frame(rules_tab)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        cols = ("id", "rev", "trust", "intent", "topology")
        tree = ttk.Treeview(left, columns=cols, show="headings", height=24)
        widths = {"id": 280, "rev": 45, "trust": 105, "intent": 120, "topology": 55}
        labels = {
            "id": "規則名稱",
            "rev": "版次",
            "trust": "認證狀態",
            "intent": "組合方式",
            "topology": "級數",
        }
        for col in cols:
            tree.heading(col, text=labels[col])
            tree.column(col, width=widths[col], stretch=(col == "id"))
        tree.pack(fill=tk.BOTH, expand=True)
        tree.bind("<<TreeviewSelect>>", lambda _e: self.populate_rule_form())
        self._publish("relief_registry_rule_tree", tree)

        form = ttk.Frame(rules_tab)
        form.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vars_defaults = {
            "rule_id": "USER_RULE_001",
            "rule_name": "自訂截角規則",
            "family": "ANY",
            "part_role": "HEAD_OR_TAIL",
            "joint_face": "TOP",
            "intent": "INSERT_OVERLAY",
            "topology": "2",
            "target_role": "BOX_SIDE",
            "extra_joint": "NONE",
            "extra_target_role": "REAR_PANEL",
            "primary_u": "side_fold + FW",
            "primary_v": "ytop1 + FW - T",
            "secondary_u": "side_fold + 0.5*T",
            "secondary_depth": "2*T",
            "preconditions": "ytop1_present,x_folded",
            "symmetry": "MIRROR_IF_GEOMETRY_SYMMETRIC",
            "source": "",
            "sample_t": "2",
            "sample_fw": "25",
            "sample_side": "15",
            "sample_ytop": "16",
            "sample_mating": "50",
        }
        for name, default in vars_defaults.items():
            self._publish(
                f"relief_registry_{name}_var",
                tk.StringVar(master=form, value=default),
            )
        self._publish(
            "relief_registry_status_var",
            tk.StringVar(master=form, value="請先驗證公式"),
        )

        row = 0

        def entry(label, var, width=28):
            nonlocal row
            ttk.Label(form, text=label).grid(
                row=row, column=0, sticky="w", padx=3, pady=2
            )
            widget = ttk.Entry(form, textvariable=var, width=width)
            widget.grid(
                row=row,
                column=1,
                columnspan=3,
                sticky="ew",
                padx=3,
                pady=2,
            )
            row += 1
            return widget

        ttk.Label(form, text="規則名稱").grid(
            row=row, column=0, sticky="w", padx=3, pady=2
        )
        ttk.Entry(
            form,
            textvariable=self.relief_registry_rule_name_var,
            width=28,
            state="readonly",
        ).grid(
            row=row,
            column=1,
            columnspan=3,
            sticky="ew",
            padx=3,
            pady=2,
        )
        row += 1

        ttk.Label(form, text="盤體條件").grid(
            row=row, column=0, sticky="w", padx=3, pady=2
        )
        self._choice(
            form,
            self.relief_registry_family_var,
            ("ANY", "金庫型", "受電箱"),
            width=14,
        ).grid(row=row, column=1, sticky="w")
        ttk.Label(form, text="板件角色").grid(row=row, column=2, sticky="e")
        self._choice(
            form,
            self.relief_registry_part_role_var,
            ("HEAD_OR_TAIL", "HEAD", "TAIL"),
            width=18,
        ).grid(row=row, column=3, sticky="ew")
        row += 1

        ttk.Label(form, text="截角／接合位置").grid(row=row, column=0, sticky="w")
        self._choice(
            form,
            self.relief_registry_joint_face_var,
            ("TOP", "BOTTOM"),
            width=18,
        ).grid(row=row, column=1, sticky="ew")
        ttk.Label(form, text="組合方式").grid(row=row, column=2, sticky="e")
        self._choice(
            form,
            self.relief_registry_intent_var,
            ("INSERT", "OVERLAY", "INSERT_OVERLAY"),
            width=16,
        ).grid(row=row, column=3, sticky="ew")
        row += 1

        ttk.Label(form, text="截角級數").grid(row=row, column=0, sticky="w")
        self._choice(
            form, self.relief_registry_topology_var, ("1", "2"), width=8
        ).grid(row=row, column=1, sticky="w")
        ttk.Label(form, text="主要接合對象").grid(row=row, column=2, sticky="e")
        self._choice(
            form,
            self.relief_registry_target_role_var,
            ("BOX_SIDE", "REAR_PANEL"),
            width=18,
        ).grid(row=row, column=3, sticky="ew")
        row += 1

        ttk.Label(form, text="附加接合方式").grid(row=row, column=0, sticky="w")
        self._choice(
            form,
            self.relief_registry_extra_joint_var,
            ("NONE", "WRAP", "INSERT", "OVERLAY", "INSERT_OVERLAY"),
            width=16,
        ).grid(row=row, column=1, sticky="ew")
        ttk.Label(form, text="附加接合對象").grid(row=row, column=2, sticky="e")
        self._choice(
            form,
            self.relief_registry_extra_target_role_var,
            ("REAR_PANEL", "BOX_SIDE"),
            width=18,
        ).grid(row=row, column=3, sticky="ew")
        row += 1

        for raw_name in ("primary_u", "primary_v", "secondary_u", "secondary_depth"):
            raw_var = getattr(self, f"relief_registry_{raw_name}_var")
            display_var = tk.StringVar(master=form)
            self._bind_translated_var(
                raw_var,
                display_var,
                lambda value, field=raw_name: self._formula_display(
                    value, presentation_field=field
                ),
                self._formula_raw,
            )
            self._publish(f"relief_registry_{raw_name}_display_var", display_var)

        preconditions_display_var = tk.StringVar(master=form)
        self._bind_translated_var(
            self.relief_registry_preconditions_var,
            preconditions_display_var,
            self._preconditions_display,
            self._preconditions_raw,
        )
        self._publish(
            "relief_registry_preconditions_display_var",
            preconditions_display_var,
        )

        entry("第一級橫向公式", self.relief_registry_primary_u_display_var)
        entry("第一級縱向公式", self.relief_registry_primary_v_display_var)
        entry("第二級橫向公式", self.relief_registry_secondary_u_display_var)
        entry("第二級深度公式", self.relief_registry_secondary_depth_display_var)
        entry("適用條件", self.relief_registry_preconditions_display_var)

        source_display_var = tk.StringVar(master=form)
        self._bind_translated_var(
            self.relief_registry_source_var,
            source_display_var,
            lambda value: self._source_display(
                value, presentation_field="source"
            ),
            self._source_raw,
        )
        self._publish("relief_registry_source_display_var", source_display_var)
        entry("公式來源／備註", self.relief_registry_source_display_var)

        help_box = ttk.LabelFrame(form, text="公式變數說明", padding=6)
        help_box.grid(
            row=row, column=0, columnspan=4, sticky="ew", pady=(5, 3)
        )
        row += 1
        help_lines = (
            "板厚：目前板件厚度。",
            "名義框寬：封頭／封尾自身的框寬參數；不等於箱身成型後實際占位。",
            "側折：封頭／封尾橫向側邊折彎基底；貼外沒有橫向折彎時為 0。",
            "上折：封頭／封尾縱向第一折尺寸。",
            "成型接合寬：接合對象折好後真正需要避讓的寬度，例如貼外取箱身成型框寬。",
            "第一級橫向／縱向：主要截角的橫向／縱向切除量；第二級橫向／深度：二級截角的內側位置與深度。",
            "嵌入、貼外、嵌入貼外、外側包覆皆以同一接合語意資料層保存。",
        )
        for help_row, text in enumerate(help_lines):
            ttk.Label(
                help_box, text=text, wraplength=660, justify="left"
            ).grid(row=help_row, column=0, sticky="w", pady=1)

        sample = ttk.LabelFrame(form, text="即時公式預覽", padding=5)
        sample.grid(row=row, column=0, columnspan=4, sticky="ew", pady=5)
        row += 1
        sample_fields = (
            ("板厚", self.relief_registry_sample_t_var),
            ("名義框寬", self.relief_registry_sample_fw_var),
            ("側折", self.relief_registry_sample_side_var),
            ("上折", self.relief_registry_sample_ytop_var),
            ("成型接合寬", self.relief_registry_sample_mating_var),
        )
        for col, (label, var) in enumerate(sample_fields):
            ttk.Label(sample, text=label).grid(row=0, column=col * 2, sticky="e")
            ttk.Entry(sample, textvariable=var, width=7).grid(
                row=0,
                column=col * 2 + 1,
                sticky="w",
                padx=(2, 6),
            )

        canvas = tk.Canvas(
            form,
            width=245,
            height=160,
            background="white",
            highlightthickness=1,
            highlightbackground="#aaa",
        )
        canvas.grid(row=row, column=0, columnspan=4, sticky="w", pady=4)
        self._publish("relief_registry_preview_canvas", canvas)
        row += 1

        actions = ttk.Frame(form)
        actions.grid(row=row, column=0, columnspan=4, sticky="ew", pady=4)
        row += 1
        action_rows = (
            ("驗證公式", self._validate_formula),
            ("預覽平面", self.draw_registry_preview),
            ("預覽立體組合", self._preview_assembly_3d),
            ("儲存候選", self._save_candidate),
            ("執行回歸", self._run_formula_matrix),
        )
        buttons = {}
        for text, command in action_rows:
            button = ttk.Button(actions, text=text, command=command)
            button.pack(side=tk.LEFT, padx=2)
            buttons[text] = button
        self._publish(
            "relief_registry_save_candidate_button",
            buttons["儲存候選"],
        )
        promote = ttk.Button(
            actions,
            text="認證新版次",
            command=self._promote_candidate,
            style="Primary.TButton",
        )
        promote.pack(side=tk.LEFT, padx=2)
        self._publish("relief_registry_promote_button", promote)
        ttk.Label(
            form,
            textvariable=self.relief_registry_status_var,
            foreground=WHD_THEME["text"],
        ).grid(
            row=row,
            column=0,
            columnspan=4,
            sticky="w",
            pady=(4, 0),
        )
        for col in (1, 3):
            form.columnconfigure(col, weight=1)

        jcols = (
            "subject",
            "target",
            "relation",
            "source",
            "subject_region",
            "target_region",
        )
        jtree = ttk.Treeview(
            joints_tab, columns=jcols, show="headings", height=15
        )
        for col, label, width in (
            ("subject", "主動板件", 100),
            ("target", "接合板件", 100),
            ("relation", "接合關係", 130),
            ("source", "資料來源", 120),
            ("subject_region", "主動板件區域", 160),
            ("target_region", "接合板件區域", 160),
        ):
            jtree.heading(col, text=label)
            jtree.column(col, width=width)
        jtree.pack(fill=tk.X, pady=(0, 8))
        self._publish("relief_joint_tree", jtree)

        self._publish(
            "relief_joint_relation_choices",
            ("INSERT", "OVERLAY", "INSERT_OVERLAY", "WRAP"),
        )
        joint_defaults = {
            "relief_joint_subject_var": "head",
            "relief_joint_target_var": "box_body",
            "relief_joint_relation_var": "WRAP",
            "relief_joint_subject_region_var": "rear_edge",
            "relief_joint_target_region_var": "rear_mating",
            "relief_joint_clearance_var": "ZERO",
            "relief_joint_topology_var": "1",
            "relief_joint_status_var": "外側包覆：主動板件包覆接合板件",
        }
        for name, default in joint_defaults.items():
            self._publish(name, tk.StringVar(master=joints_tab, value=default))

        jf = ttk.LabelFrame(joints_tab, text="新增使用者接合規則", padding=6)
        jf.pack(fill=tk.X)
        fields = (
            ("主動板件", self.relief_joint_subject_var, ("head", "tail", "box_body")),
            ("接合板件", self.relief_joint_target_var, ("box_body", "head", "tail")),
            (
                "主動板件區域",
                self.relief_joint_subject_region_var,
                ("rear_edge", "TOP", "BOTTOM"),
            ),
            (
                "接合板件區域",
                self.relief_joint_target_region_var,
                ("rear_mating", "MATING_ZONE", "OUTER_SURFACE"),
            ),
            ("間隙條件", self.relief_joint_clearance_var, ("ZERO",)),
        )
        for i, (label, var, choices) in enumerate(fields):
            ttk.Label(jf, text=label).grid(
                row=i // 3 * 2,
                column=(i % 3) * 2,
                sticky="w",
                padx=3,
            )
            self._choice(jf, var, choices, width=18).grid(
                row=i // 3 * 2 + 1,
                column=(i % 3) * 2,
                sticky="ew",
                padx=3,
                pady=(0, 4),
            )
        ttk.Label(jf, text="接合關係").grid(
            row=0, column=5, sticky="w", padx=3
        )
        self._choice(
            jf,
            self.relief_joint_relation_var,
            self.relief_joint_relation_choices,
            width=16,
        ).grid(row=1, column=5, sticky="ew", padx=3)
        ttk.Label(jf, text="自動辨識級數").grid(
            row=2, column=4, sticky="w", padx=3
        )
        self._choice(
            jf, self.relief_joint_topology_var, ("1", "2"), width=8
        ).grid(row=3, column=4, sticky="w", padx=3)

        buttons = ttk.Frame(joints_tab)
        buttons.pack(fill=tk.X, pady=6)
        ttk.Button(
            buttons,
            text="新增接合",
            command=self._add_joint,
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            buttons,
            text="刪除使用者接合",
            command=self._delete_joint,
        ).pack(side=tk.LEFT, padx=2)
        ttk.Label(
            buttons, textvariable=self.relief_joint_status_var
        ).pack(side=tk.LEFT, padx=10)

        self.refresh_rule_rows()
        self.refresh_joint_rows()
        return win

    def build_assembly_diagnostics(self, parent):
        frame = self.assembly_diagnostics_frame
        try:
            if frame is not None and frame.winfo_exists():
                return frame
        except Exception:
            pass

        frame = ttk.LabelFrame(parent, text="組合體診斷", padding=6)
        self._publish("assembly_diagnostics_frame", frame)
        self._publish(
            "assembly_ignore_fixed_corner_var",
            tk.BooleanVar(master=frame, value=True),
        )
        self._publish(
            "assembly_show_interference_var",
            tk.BooleanVar(master=frame, value=True),
        )
        self._publish(
            "assembly_relief_clearance_var",
            tk.StringVar(master=frame, value="0"),
        )
        self._publish(
            "assembly_relief_size_var",
            tk.StringVar(master=frame, value="實際截角尺寸：等待計算"),
        )
        self._publish(
            "assembly_collision_status_var",
            tk.StringVar(master=frame, value="3D驗證：等待計算"),
        )

        ttk.Checkbutton(
            frame,
            text="未知組合允許3D求截角",
            variable=self.assembly_ignore_fixed_corner_var,
            command=self._on_diagnostic_changed,
        ).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(frame, text="淨空 A").pack(side=tk.LEFT, padx=(0, 4))
        entry = ttk.Entry(
            frame,
            textvariable=self.assembly_relief_clearance_var,
            width=7,
        )
        entry.pack(side=tk.LEFT, padx=(0, 10))
        entry.bind("<Return>", lambda _event: self._on_diagnostic_changed())
        entry.bind("<FocusOut>", lambda _event: self._on_diagnostic_changed())
        self._publish("assembly_relief_clearance_entry", entry)

        ttk.Checkbutton(
            frame,
            text="顯示干涉碰撞區",
            variable=self.assembly_show_interference_var,
            command=self._on_diagnostic_changed,
        ).pack(side=tk.LEFT, padx=(0, 10))
        promotion = ttk.Button(
            frame,
            text="建立認證候選",
            command=self._create_promotion_candidates,
        )
        promotion.pack(side=tk.LEFT, padx=(0, 10))
        self._publish("assembly_relief_promotion_button", promotion)

        ttk.Label(
            frame, textvariable=self.assembly_relief_size_var
        ).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(
            frame, textvariable=self.assembly_collision_status_var
        ).pack(side=tk.LEFT)
        frame.pack_forget()
        return frame

    def set_diagnostic_status(self, size_text: str, status_text: str) -> None:
        size_var = getattr(self, "assembly_relief_size_var", None)
        status_var = getattr(self, "assembly_collision_status_var", None)
        if size_var is not None:
            size_var.set(str(size_text))
        if status_var is not None:
            status_var.set(str(status_text))

    def refresh_joint_diagnostic_menu(self, resolved=None):
        var = getattr(self.owner, "assembly_joint_diag_var", None)
        button = getattr(self.owner, "assembly_joint_diag_button", None)
        if var is None or button is None:
            return ()
        menu = getattr(self.owner, "assembly_joint_diag_menu", None)
        if menu is None:
            menu_name = str(button.cget("menu") or "")
            if not menu_name:
                return ()
            try:
                menu = button.nametowidget(menu_name)
            except Exception:
                return ()
        menu.delete(0, "end")
        ids = tuple(str(value) for value in self._diagnostic_ids(resolved) if str(value))
        current = str(var.get() or "")
        if current not in ids:
            current = ids[0] if ids else ""
            var.set(current)
        labels = {
            joint_id: f"接合 {index + 1}"
            for index, joint_id in enumerate(ids)
        }
        for joint_id in ids:
            menu.add_radiobutton(
                label=labels[joint_id],
                value=joint_id,
                variable=var,
                command=self._on_diagnostic_changed,
            )
        button.configure(text=labels.get(current, "接合"))
        return ids
