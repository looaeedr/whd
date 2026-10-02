# -*- coding: utf-8 -*-
"""Baseline resource/path resolution owner.

This module decides where editable baseline resources live and how shared
indicator-box baseline files are resolved. It owns no manufacturing geometry
and performs no DXF parsing or serialization.
"""
from __future__ import annotations

import os


def baseline_root_path(resource_path):
    return resource_path("基準檔")


def get_baseline_list(resource_path):
    base_dir = baseline_root_path(resource_path)
    if not os.path.exists(base_dir):
        return []
    models = []
    try:
        for item in os.listdir(base_dir):
            folder = os.path.join(base_dir, item)
            if os.path.isdir(folder) and os.path.exists(os.path.join(folder, "封頭尾.dxf")):
                models.append(item)
    except Exception:
        pass
    return models

def baseline_expected_path(resource_path, model_name, filename):
    model = str(model_name or "").strip()
    if not model:
        return None
    return os.path.join(baseline_root_path(resource_path), model, str(filename))


def baseline_part_path(resource_path, model_name, filename):
    path = baseline_expected_path(resource_path, model_name, filename)
    return path if path and os.path.isfile(path) else None


def baseline_hole_catalog_root_path(resource_path):
    return os.path.join(baseline_root_path(resource_path), "開孔")


def indicator_shared_baseline_model_name(config, resource_path):
    configured = config.get(
        "INDICATOR_BOX", "shared_baseline_model", fallback=""
    ).strip()
    if configured:
        return configured

    root = baseline_root_path(resource_path)
    required = ("盒子.dxf", "小門.dxf")
    candidates = []
    if os.path.isdir(root):
        for name in sorted(os.listdir(root)):
            folder = os.path.join(root, name)
            if os.path.isdir(folder) and all(
                os.path.isfile(os.path.join(folder, part)) for part in required
            ):
                candidates.append(name)

    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise FileNotFoundError(
            "找不到全域指示燈盒基準；請設定 [INDICATOR_BOX] shared_baseline_model，"
            "或讓基準檔根目錄中只有一個資料夾同時包含 盒子.dxf 與 小門.dxf"
        )
    raise RuntimeError(
        "找到多個全域指示燈盒基準候選：" + ", ".join(candidates)
        + "；請用 [INDICATOR_BOX] shared_baseline_model 明確指定"
    )


def indicator_shared_baseline_part_path(
    config, resource_path, filename, require_exists=True
):
    model = indicator_shared_baseline_model_name(config, resource_path)
    path = baseline_expected_path(resource_path, model, filename)
    if require_exists and (not path or not os.path.isfile(path)):
        return None
    return path

def indicator_shared_baseline_source_label(config, resource_path, filename):
    try:
        model = indicator_shared_baseline_model_name(config, resource_path)
    except Exception as exc:
        return f"共用基準檔解析失敗：{exc}"
    path = baseline_expected_path(resource_path, model, filename)
    if path and os.path.isfile(path):
        return f"基準檔：{model}/{filename}"
    return f"共用基準檔缺少：{model}/{filename}"


def has_baseline_part(resource_path, model_name, filename):
    return baseline_part_path(resource_path, model_name, filename) is not None


def baseline_source_label(resource_path, model_name, filename):
    model = str(model_name or "").strip()
    if model and has_baseline_part(resource_path, model, filename):
        return f"基準檔：{model}/{filename}"
    return "未使用基準檔（程式計算生成）"
