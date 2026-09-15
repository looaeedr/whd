# Phase6 ProjectSession Deletion / Reuse Evidence

- 日期：2026-09-04（Asia/Taipei）
- 對應規格：`2026-09-04-phase6-deep-module-ownership-consolidation-design.md` Workstream C
- 判定：**ProjectSession 保留為 Controller internal state-machine implementation；Phase6ProjectController 是唯一 production project-transaction public boundary。**

## Production caller audit

執行：

```bash
rg -n 'from phase6_project_session import ProjectSession|ProjectSession\(' \
  --glob '*.py' --glob '!tests/**' --glob '!BACKUP/**' --glob '!logs/**' .
```

結果只有：

```text
phase6_project_controller.py:9:from phase6_project_session import ProjectSession
phase6_project_controller.py:...:self._session = ProjectSession()
```

沒有第二個不經 `Phase6ProjectController` 的 production caller，也沒有其他 application controller 的替換／重用需求。

## Deletion test ruling

若移除獨立 public `ProjectSession` boundary，begin/cancel/confirm/save/load 的交易 invariant 只需由 `Phase6ProjectController` 吸收，不會散回 GUI 或 persistence adapter。因此採規格判定 A：

- `phase6_project_session.py` 物理檔保留，作為 Controller internal state-machine implementation。
- `Phase6ProjectController` 不再公開 `.session`。
- `Phase6ProjectController.__init__` 不再公開 `session=` 注入 seam。
- GUI 不再保存 `project_session` compatibility alias。
- Controller 提供 defensive `committed_snapshot()`、`loaded_baseline_snapshot()`、`draft_snapshot()` projection，供 integration verification 使用。
- `ProjectSession` 的 unit tests保留，定位為 internal state-machine evidence，不再代表第二個 production public API。

## 保護 invariant

本次 public-surface 收斂不改：

- loaded baseline 不被 committed recapture 覆寫。
- committed 只代表 Main canonical state。
- draft 仍隔離；Save during active draft 只讀 committed。
- Cancel 丟棄 draft。
- Confirm 接受 Main re-compose 後的 canonical snapshot。
- 所有 snapshot 維持 defensive copy。
- `.p6fold` schema 不變。

## 驗證證據

- Pure Headless project/session/controller/ownership：`23 passed / 9 skipped`。
- Controller/session core：`13 passed`。
- Fresh direct-Xvfb project GUI transaction：`28 passed`。
- Xvfb 第一輪曾揭露 T1 Workspace compatibility adapter 仍讀舊 `_available_parts/_part_profiles` 私有欄位；已改為直接委派 `Phase6DesignerWorkspace` public owner API，並新增 fail-closed static guard。這是 Workspace ownership regression 修復，非 ProjectSession 語意修改。
