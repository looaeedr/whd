# T14: Box Body Child Input Sections

**GitHub Issue:** #15
**What to build:** 依既有 authoritative box-body physical pieces，在箱身區為二件式／三件式顯示各自獨立輸入區，呈現方式比照資料區。

**Approved RED IDs:** R11
**GREEN Guard:** R10

**Blocked by:** T11 / GitHub #11；T12 / GitHub #13

**Status:** ready-for-agent

**Do not rebuild:** R10 已 GREEN：二件式已是 2 個真 physical pieces；三件式已是 3 個真 physical pieces。

- [ ] R11 二件式 → GREEN：顯示 2 個獨立子板件輸入區。
- [ ] R11 三件式 → GREEN：顯示 3 個獨立子板件輸入區。
- [ ] 每個 UI section 綁定對應 physical piece stable id。
- [ ] 二件式 ↔ 三件式切換後 section 數量即時一致，不殘留舊 section。
- [ ] Save/Reload 後 UI sections 與 physical pieces 一致。
- [ ] R10 持續 GREEN，不新增第二套 fake child-piece model。
