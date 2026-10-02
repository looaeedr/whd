# T48-1: 受電箱中隔 FW 成形面與箱身 FW 成形面面齊

**What to build:** 以真實折後 skin / face relationship 建立 Receiving Divider 的深度 placement，使中隔第二段 FW 對應成形面與箱身左右 FW 對應成形面真正共面；不得使用固定 world Z、D/2、bbox center 或 renderer origin 當產品契約。

**Approved RED IDs:** R2

**Requirement Authority:** 使用者已核准：FW 是全系統共用 Frame Width；受電箱 3D 輸入區 FW 預設 29；中隔為 `18 / FW / 106 / 17`；中隔 FW 與箱身 FW 的對應折後面必須面齊。R2 已於 run `34166999592` 證明 production 目前不符合：BoxBody FW skins=`172/174`，Divider FW skins=`-52/-50`。

**AI Library References:**
- `個人AI檔案庫/第一層_核心檔案/04_全域AI協作規則.md`
- `個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md`
- `個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md`
- `個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md`
- `個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md`

**AI Library Writeback:** REQUIRED — 完成後更新 `個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md`，只寫入已由實體 geometry 證明的 FW face relationship / placement derivation；禁止寫入單一 probe world coordinate 當規格。

**Blocked by:** None

**Status:** ACCEPTED — run 34167721816, 18 passed / 0 failed

- [x] 追出 BoxBody `fw_left/fw_right` 折後實體 skin/normal 與 Divider 第二段 FW skin/normal。
- [x] placement resolver 由實體 face-flush relation 推導 transform。
- [x] R2 由 RED 轉 GREEN；測試不得硬寫 `Z=121`、`174` 等 world coordinate。
- [x] 修改 D/FW/T 時重新推導 placement，面齊關係仍成立。
- [x] 舊 `Z=0` placement oracle 若與已確認機械關係衝突，修正測試，不弱化 production。
