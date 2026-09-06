# T15: Per-Door Inner Door Selection + Physical Inner-Door Panel

**GitHub Issue:** #14
**What to build:** 每一片外門各自擁有獨立「內門」勾選；只有被勾選的外門才生成自己的一片真實 inner-door panel physical piece。

**Approved RED IDs:** R12, R13
**GREEN Guards:** R12-D, R14

**Blocked by:** T11 / GitHub #11

**Status:** ready-for-agent

**Do not rebuild:**
- R12-D 已 GREEN：authoritative state 已能表達每片外門獨立有／無內門。
- R14 已 GREEN：單門 0 中隔；多門才有中隔。

- [ ] R12 → GREEN：每片外門資料區都有自己的「內門」checkbox。
- [ ] R13 → GREEN：只為已勾選的外門生成一片真實 inner-door panel。
- [ ] 取消勾選後該外門 inner-door panel 消失。
- [ ] 未勾選外門不得生成 inner-door panel。
- [ ] 每片 inner-door panel 具有穩定 stable id。
- [ ] R12-D、R14 持續 GREEN。
