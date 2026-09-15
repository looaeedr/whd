"""Application update routing extracted from gui.py.

This module owns scheduling/routing only; calculation/state authority remains on
the application owner and its existing controllers/services.
"""

class _Phase6UpdateScheduler:
    """Coalesce GUI work behind the single calculation-executor seam."""

    DEFAULT_DEBOUNCE_MS = 75
    MIN_DEBOUNCE_MS = 50
    MAX_DEBOUNCE_MS = 100
    _DISPLAY_ONLY_REASONS = frozenset({"display", "annotation", "camera"})
    _FULL_REASONS = frozenset({"geometry", "assembly", "baseline"})

    def __init__(self, owner):
        self.owner = owner
        self.depth = 0
        self.dirty = set()
        self._flushing = False
        self._after_job = None
        self._metrics = {
            "flushes": 0,
            "calculation_flushes": 0,
            "display_flushes": 0,
        }

    def begin(self):
        self.depth += 1

    def end(self):
        if self.depth <= 0:
            self.depth = 0
            return
        self.depth -= 1
        if self.depth == 0:
            self.request_flush()

    def mark_dirty(self, reason="geometry"):
        self.dirty.add(str(reason or "geometry"))
        if self.depth == 0:
            self.request_flush()

    @classmethod
    def _normalize_debounce_ms(cls, debounce_ms):
        if debounce_ms is None:
            return cls.DEFAULT_DEBOUNCE_MS
        value = int(debounce_ms)
        if value <= 0:
            return 0
        return max(cls.MIN_DEBOUNCE_MS, min(cls.MAX_DEBOUNCE_MS, value))

    @classmethod
    def _requires_calculation(cls, reasons):
        for reason in reasons:
            text = str(reason or "geometry")
            if text in cls._DISPLAY_ONLY_REASONS:
                continue
            if text in cls._FULL_REASONS:
                return True
            # setting:*, legacy "settings", designer snapshots, and unknown
            # mutation reasons fail closed to a full authoritative calculation.
            return True
        return False

    def request_flush(self, *, debounce_ms=None):
        if self.depth > 0 or self._flushing or not self.dirty:
            return
        delay = self._normalize_debounce_ms(debounce_ms)
        root = getattr(self.owner, "root", None)
        if delay and root is not None and hasattr(root, "after"):
            if self._after_job is not None:
                try:
                    root.after_cancel(self._after_job)
                except Exception:
                    pass
            self._after_job = root.after(delay, self.flush_now)
            return
        self.flush_now()

    def flush_now(self):
        if self.depth > 0 or self._flushing or not self.dirty:
            return False
        if self._after_job is not None:
            root = getattr(self.owner, "root", None)
            try:
                if root is not None:
                    root.after_cancel(self._after_job)
            except Exception:
                pass
            self._after_job = None
        reasons = set(self.dirty)
        self.dirty.clear()
        self._flushing = True
        try:
            self._metrics["flushes"] += 1
            if self._requires_calculation(reasons):
                self._metrics["calculation_flushes"] += 1
                self.owner.update_calculations()
            else:
                self._metrics["display_flushes"] += 1
                render = getattr(self.owner, "draw_preview", None)
                if callable(render):
                    render()
        finally:
            self._flushing = False
        return bool(reasons)

    def metrics_snapshot(self):
        return dict(self._metrics)

def _request_phase6_update(self, reason="geometry", *, immediate=False, debounce_ms=None):
    """Route a GUI mutation through the one authoritative update scheduler."""
    owner = getattr(self, "_derived_cache_owner", None)
    if owner is not None:
        owner.invalidate(reason)
    scheduler = getattr(self, "_phase6_update_scheduler", None)
    if scheduler is None:
        scheduler = self._phase6_update_scheduler = _Phase6UpdateScheduler(self)
    scheduler.mark_dirty(reason)
    if immediate:
        return scheduler.flush_now()
    if debounce_ms is not None:
        scheduler.request_flush(debounce_ms=debounce_ms)
    return True

def _flush_phase6_authoritative_state(self):
    """Commit pending GUI mutations before persistence/manufacturing boundaries."""
    scheduler = getattr(self, "_phase6_update_scheduler", None)
    if scheduler is None:
        return False
    return scheduler.flush_now()

def bind_live_updates(self):
    # W/H 同時是 Door layout 的總尺寸；變更時要重算自動餘數。
    self.w_var.trace_add("write", lambda *args: self._on_total_door_dimension_changed())
    self.h_var.trace_add("write", lambda *args: self._on_total_door_dimension_changed())

    # 主 GUI 中仍存在的設定欄位與 3D 設定中心雙向連動。
    for key, var in self._setting_var_map().items():
        var.trace_add("write", lambda *_args, k=key, v=var: self._on_main_setting_var_changed(k, v))

    # 非 SettingsService 擁有的輸入也只送 dirty event；完整重算只能由 Scheduler 執行。
    for var in [self.base_plate_all_same_var, self.base_plate_shrink_same_var,
                self.indicator_g_var, self.indicator_l_var] + self.indicator_layer_g_vars:
        var.trace_add(
            "write",
            lambda *_args: self._on_main_geometry_var_changed("legacy_input"),
        )

