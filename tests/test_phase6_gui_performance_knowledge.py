# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / '.agents' / 'skills' / 'skill_registry.json'
GUI_SKILL = ROOT / '.agents' / 'skills' / 'engineering' / 'phase6-gui-performance-integrity' / 'SKILL.md'
RELEASE_SKILL = ROOT / '.agents' / 'skills' / 'engineering' / 'phase6-release-packaging' / 'SKILL.md'
PITFALLS = ROOT / '個人AI檔案庫' / '第二層_專案與SOP' / '06_踩坑記錄與防錯經驗庫.md'


def _routes():
    return json.loads(REGISTRY.read_text(encoding='utf-8'))['routes']


def test_registry_routes_gui_performance_work_to_dedicated_skill():
    routes = {route['id']: route for route in _routes()}
    route = routes['phase6-gui-performance']
    assert 'phase6-gui-performance-integrity' in route['required_skills']
    for keyword in ('GUI 效能', 'live-sync', '重算', 'DXF cache', 'debounce'):
        assert keyword in route['keywords']
    assert 'tests/test_phase6_gui_*performance*.py' in route['file_globs']
    assert 'tests/test_phase6_*live_sync*.py' in route['file_globs']

    from tools.phase6_skill_preflight import required_skills_for
    assert 'phase6-gui-performance-integrity' in required_skills_for(
        task='GUI 效能 live-sync 重算 DXF cache debounce', changed_files=('gui.py',)
    )
    assert 'phase6-gui-performance-integrity' not in required_skills_for(
        task='組合 bug 修正', changed_files=('fold_designer_bridge.py',)
    )


def test_gui_performance_skill_locks_the_today_rules():
    text = GUI_SKILL.read_text(encoding='utf-8')
    for required in (
        'Scheduler 是唯一 calculation executor',
        'origin + revision + transaction_id',
        'set_var_if_changed',
        'SOURCE_UNVERIFIED',
        'Save / Export / DXF / NC 前',
        'durable checkpoint',
        '真 GUI 壓力',
        'recalculation',
        'DXF disk read',
        'render',
    ):
        assert required in text


def test_release_skill_records_durable_and_pristine_release_rules():
    text = RELEASE_SKILL.read_text(encoding='utf-8')
    for required in (
        'durable checkpoint',
        '父程序先退出',
        'process group',
        'pristine',
        '__pycache__',
        '.pytest_cache',
        'UPDATE overlay',
    ):
        assert required in text


def test_global_pitfall_library_contains_today_gui_performance_lessons():
    text = PITFALLS.read_text(encoding='utf-8')
    for required in (
        '### 77.',
        'GUI ↔ 3D live-sync echo',
        '### 78.',
        'DXF source cache',
        '### 79.',
        '3D initialization',
        '### 80.',
        'durable checkpoint',
        '### 81.',
        '__pycache__/.pytest_cache',
        '### 82.',
        '真 GUI 壓力',
        '### 83.',
        '父程序先退出',
    ):
        assert required in text


def test_global_pitfall_library_contains_targeted_gate_and_checkpoint_provenance_lessons():
    text = PITFALLS.read_text(encoding='utf-8')
    for required in (
        '### 87.',
        'Tk/Xvfb targeted gate',
        '完整 PASS summary',
        '### 88.',
        'execution tree',
        'checkpoint provenance',
        '混合狀態',
    ):
        assert required in text
