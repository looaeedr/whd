from __future__ import annotations

import json
from pathlib import Path

from tools.phase6_skill_preflight import required_references_for


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / ".agents/skills/skill_registry.json"
DIMENSION_AUTHORITY = "個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md"
NAV_RULES = "個人AI檔案庫/第二層_專案與SOP/08_WHD截角資料與2D入口收斂規則.md"
DM7_AUTHORITY = "個人AI檔案庫/踩坑庫/dm7_part_navigation_pitfalls.md"
MANUFACTURING_AUTHORITY = "個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md"


def _registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _route(route_id: str) -> dict:
    for route in _registry()["routes"]:
        if route["id"] == route_id:
            return route
    raise AssertionError(f"missing route: {route_id}")


def test_dimension_route_requires_canonical_dimension_authority() -> None:
    route = _route("dimension-semantics-analysis")
    assert DIMENSION_AUTHORITY in route["required_references"]
    refs = required_references_for(task="尺寸語意分析：檢查 FW 包外與料尺寸是否混用")
    assert DIMENSION_AUTHORITY in refs


def test_dm7_navigation_has_dedicated_route_and_current_authority() -> None:
    route = _route("dm7-part-navigation")
    assert "截角資料入口收斂" in route["required_skills"]
    assert NAV_RULES in route["required_references"]
    assert DM7_AUTHORITY in route["required_references"]
    refs = required_references_for(task="Corner Data DM7 stale physical child navigation")
    assert NAV_RULES in refs
    assert DM7_AUTHORITY in refs


def test_manufacturing_dxf_route_keeps_current_manufacturing_authority() -> None:
    route = _route("part-dxf-acceptance")
    assert MANUFACTURING_AUTHORITY in route["required_references"]
    refs = required_references_for(task="驗全部DXF manufacturing Final Material")
    assert MANUFACTURING_AUTHORITY in refs


def test_domain_routes_do_not_use_generic_skill_policy_as_only_reference() -> None:
    generic = "個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md"
    for route_id, domain_refs in {
        "dimension-semantics-analysis": {DIMENSION_AUTHORITY},
        "dm7-part-navigation": {DM7_AUTHORITY},
        "part-dxf-acceptance": {MANUFACTURING_AUTHORITY},
    }.items():
        route = _route(route_id)
        refs = set(route.get("required_references", ()))
        assert refs & domain_refs, f"{route_id} lacks domain authority: {refs}"
        assert refs != {generic}, f"{route_id} is generic-only"
