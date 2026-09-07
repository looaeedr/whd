# T48-4: Combined Acceptance、舊 oracle 清理、AI 庫收斂與整合

**What to build:** 對 T48 全鏈做 targeted + Combined Acceptance；清掉仍鎖錯誤 placement / stale numeric oracle 的測試與臨時 workflow；完成 AI 庫 writeback、config invariant、drift audit，最後才允許 fast-forward `cleanup/2d-3d-sync`。

**Approved RED IDs:** R2, R3

**Requirement Authority:** 最新使用者核准規格優先；R1 已 GREEN，禁止把已正常的三件式 3D input sections 當修復範圍。R2/R3 是唯一已核准 repair RED。

**AI Library References:**
- `個人AI檔案庫/第一層_核心檔案/04_全域AI協作規則.md`
- `個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md`
- `個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md`
- `個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md`
- `個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md`

**AI Library Writeback:** REQUIRED — 反讀並收斂 T48-1/T48-2 的兩處 writeback；移除/修正任何仍把 probe world coordinate、固定 cut depth、或未證明 physical-face 名稱當產品 authority 的 stale 文字。

**Blocked by:** T48-3 — ACCEPTED run 34168398865

**Status:** ready-for-agent

- [ ] targeted: R2/R3 + Divider/FW/Receiving/multipart/collision/placement regression 全綠。
- [ ] Combined Acceptance 全綠，完整 summary 有 0 FAIL / 0 ERROR。
- [ ] `config.ini` before/after SHA256 = `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`。
- [ ] remote QA 鎖定 run_id + head_sha 並監控到 terminal；不得停在 queued/in_progress。
- [ ] one-shot workflow / RED probe / temporary artifacts cleanup。
- [ ] execution-tree drift audit / checkpoint provenance 完成。
- [ ] AI Library writeback 已反讀確認。
- [ ] 僅在上述全部成立後整合 `cleanup/2d-3d-sync`。
