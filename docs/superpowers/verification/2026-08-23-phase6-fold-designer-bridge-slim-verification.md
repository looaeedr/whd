# Phase6 Fold Designer Bridge 瘦身驗證報告

## 變更範圍

- 新增 `phase6_endcap_semantics.py`。
- 新增 `phase6_fold_profiles.py`。
- `fold_designer_bridge.py` 移除上述 domain 規則實作，保留 compatibility import alias 與 Fold Designer adapter。
- `gui.py` 改直接依賴 owner module。
- 不改 `.p6fold` schema、UI 操作、renderer 幾何、Project/Settings/Workspace Controller。

## Ownership 驗證

- `gui.py` 從 `fold_designer_bridge` 只 import `Phase6FoldDesignerApp`。
- Bridge 不重新定義 assembly/FW/Fold Profile owner functions。
- Bridge compatibility export 與 owner module function 為同一 function object。
- `phase6_endcap_semantics.py` / `phase6_fold_profiles.py` 無 Tk、GUI、renderer dependency。
- `fold_designer_bridge.py`：5391 → 4685 行，減少 706 行；目的為 ownership/locality，不以行數本身作成功標準。

## TDD 與回歸

- 新增 ownership seam：`tests/test_phase6_bridge_domain_ownership.py`，`6 passed`。
- 關聯回歸（Bridge/assembly/linked profile/UI state/project/tail/3D/corner）：`160 passed, 2 skipped, 4 deselected, 0 failure`。
- 原始完整 suite：`299 passed, 2 skipped, 4 failed`。
- 4 個 failure 全部是既有測試硬編碼 `/mnt/data/自訂.p6fold`，目前交付環境無該外部 fixture。
- 明確排除上述 4 項後完整 suite：`299 passed, 2 skipped, 4 deselected, 0 failure`。
- Tk 測試使用真正 Xvfb；容器原本 `DISPLAY=:0` 為假 display，不能拿來判定 GUI failure。

## 組態

- `config.ini` 不在本輪修改範圍。
- 最終 SHA256 需與修改前 `5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d` 一致。

## 最終交付

- FULL：`PHASE6_FOLD_DESIGNER_BRIDGE_SLIM_FULL_20260823_133104.zip`
- UPDATE：`PHASE6_FOLD_DESIGNER_BRIDGE_SLIM_UPDATE_20260823_133104.zip`
- 共用 Asia/Taipei 時間戳：`20260823_133104`。
- UPDATE 不含 `config.ini`。
