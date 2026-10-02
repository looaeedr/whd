# 2026-09-05 測試策略調整紀錄

### [22:00:00] 變更紀錄
- **變更檔案**：`.agents/skills/engineering/phase6-release-packaging/SKILL.md`
- **Git 備份點**：`backup/20260905-2200-test-levels`
- **Git Commit**：`1f878401dcf403e42d91e8ea6e141f67db7b2505`
- **修改摘要**：將每次小修改都執行完整回歸，調整為分級測試：小修改先做快速／對應測試並累積測試債；達到 5 個小修改、涉及 3 個以上相關 production 檔案／模組，或總控判定有明顯跨模組影響時，才執行完整 Headless + GUI Gate。Geometry、Topology、Factory Policy、求解器、碰撞／穿透、2D/3D 同步、DXF、Save/Reload、資料格式、核心 API 等高風險修改立即完整驗證。完整 Gate 通過後清零測試債。正式出包仍必須完整 regression；正常封包後不重跑完整 GUI，只有封裝改變執行環境或交付內容時追加 package GUI Smoke。
