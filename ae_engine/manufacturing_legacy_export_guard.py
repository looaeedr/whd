"""Source-owned safety guard for legacy DXF exports with saved NFB data.

Headless: accepts persisted project/quantity snapshots and operator part
intent; never reads GUI widgets or silently drops submitted NFB holes.
"""
from collections.abc import Mapping


def has_submitted_nfb_in_current_snapshot(payload):
    """Read NFB submission facts recursively from the saved project source."""
    seen = set()

    def walk(node, depth):
        if depth > 32:
            raise ValueError("NFB project export nesting exceeds safe bound")
        if isinstance(node, Mapping):
            if id(node) in seen:
                return False
            seen.add(id(node))
            if "nfb_config_submitted" in node:
                fact = node["nfb_config_submitted"]
                if type(fact) is not bool:
                    raise ValueError("NFB saved submission flag must be boolean")
                if fact:
                    return True
            return any(walk(value, depth + 1) for value in node.values())
        if isinstance(node, (list, tuple)):
            if id(node) in seen:
                return False
            seen.add(id(node))
            return any(walk(value, depth + 1) for value in node)
        return False

    return walk(payload, 0)


def assert_legacy_nfb_export_scope_safe(flags, saved_sources):
    """Never publish legacy door/base/body DXF when NFB was already submitted.

    Other independent selected parts are not blocked by unrelated NFB source.
    Actual verified manufacturing still uses existing Engine export gates.
    """
    affected = ("door", "base_plate", "box_body")
    if not any(bool(flags.get(key)) for key in affected):
        return
    if any(has_submitted_nfb_in_current_snapshot(source) for source in saved_sources):
        raise ValueError(
            "已提交 NFB：舊式內門／箱身／底板 DXF 無法證明 NFB 孔位，"
            "不得忽略 NFB 配置直接完整出圖；須使用逐板件來源驗證"
        )
