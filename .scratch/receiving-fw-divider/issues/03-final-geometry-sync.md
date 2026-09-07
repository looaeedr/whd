# T48-3: 中隔 final geometry 同步 2D / 3D / DXF / Save-Reload

**What to build:** 將 T48-1/T48-2 得到的 authoritative Divider placement + final relief material 貫穿 2D、單板 3D、組合 3D、DXF 與 Save/Reload，不允許任何 surface 使用另一套幾何。

**Approved RED IDs:** R2, R3（GREEN 後的 end-to-end acceptance）

**Requirement Authority:** 使用者核准：中隔 DXF 固定孔保留；外框/截角由 runtime assembly geometry 產生；3D 有的 final geometry 2D/DXF 必須同步；3D→2D / Save→Reload 不可掉資料。

**AI Library References:**
- `個人AI檔案庫/第一層_核心檔案/04_全域AI協作規則.md`
- `個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md`
- `個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md`
- `個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md`
- `個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md`

**AI Library Writeback:** None — no new durable rule expected; this ticket implements existing canonical final-geometry invariants. 若施工發現新的跨層坑，轉交 T48-4 統一回寫。

**Blocked by:** T48-2 — ACCEPTED run 34168152160

**Status:** ready-for-agent

- [ ] 2D 使用 solver 後 Divider final material。
- [ ] 3D 使用同一 final material + authoritative placement。
- [ ] DXF CUTTING 使用同一 final material，固定孔仍來自 baseline feature source。
- [ ] Save/Reload 後 FW、Fold Profile、placement、relief metadata、final material 一致。
- [ ] 三件式箱身 left/back/right physical IDs 不漂移。
- [ ] 不建立第二套 Divider relief/state。
