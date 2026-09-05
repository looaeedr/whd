# 2026-09-03 派工與 checkpoint gate evidence

## Task

補強派工技能必須實際執行與 checkpoint 落盤 gate。

## Knowledge preflight evidence

- READ_SKILL: phase6-release-packaging
- READ_SKILL: dispatching
- READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
- READ_REFERENCE: release_required_artifacts.json

## Verification intent

本輪只修改 SOP 文件，不修改 production code。新增規則要求總控不得接受只有「已派工」口頭聲明的回報；必須看到派工技能的角色轉移標記、實作者角色標記、checkpoint path、journal/state 路徑與下一步 resume command，否則視為派工技能未實際執行。
