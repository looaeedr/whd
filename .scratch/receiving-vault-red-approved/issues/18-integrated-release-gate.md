# T18: Integrated RED Closure + Headless/Xvfb Release Gate

**GitHub Issue:** #18
**What to build:** T11-T17 全部完成後執行整合驗證與正式 release gate；本工單只驗證，發現 RED 時不得在 T18 偷修 production，必須退回對應前置工單。

**Approved RED IDs:** R01, R02, R04, R05, R06-Door, R06-Frame-Top, R06-Frame-Left, R06-Frame-Right, R07, R08, R09, R11, R12, R13, R15, R16
**GREEN Guards:** R03, R06-Divider, R10, R12-D, R14

**Blocked by:** T11/#11, T12/#13, T13/#12, T14/#15, T15/#14, T16/#16, T17/#17

**Status:** ready-for-agent

- [ ] 所有 Approved RED 全部轉 GREEN。
- [ ] R03、R06-Divider、R10、R12-D、R14 全部持續 GREEN。
- [ ] 2D → 3D → Confirm → 2D → Save → Reload → 3D round-trip 比較 stable id、piece count、family state、placement、geometry、inner-door enable、55 default、80 default。
- [ ] 完整 Phase6 Headless durable gate complete。
- [ ] 完整 Xvfb GUI durable gate complete。
- [ ] collection fingerprint 一致。
- [ ] 0 unresolved failed nodeids。
- [ ] 0 unresolved timeout nodeids。
- [ ] config.ini unchanged。
- [ ] production/test drift audit 完成。
- [ ] checkpoint / provenance / 修改日誌完整。
