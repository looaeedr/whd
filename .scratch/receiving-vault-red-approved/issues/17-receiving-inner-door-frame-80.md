# T17: Receiving Inner Door / Frame Default 80 mm Datum

**GitHub Issue:** #17
**What to build:** Receiving 的 inner-door 與 frame placement 預設值都是「相對該片自己的外門門面往箱內退 80 mm」；80 是可調預設，不是世界座標 magic constant。

**Approved RED IDs:** R15, R16

**Blocked by:** T15 / GitHub #14；T16 / GitHub #16

**Status:** ready-for-agent

- [ ] R15 → GREEN：inner-door 預設相對自己的 outer-door plane 往箱內退 80 mm。
- [ ] R16 → GREEN：frame datum 預設相對自己的 outer-door plane 往箱內退 80 mm。
- [ ] 方向由 Receiving family coordinate contract 決定，不硬寫 Z-80。
- [ ] 80 為預設且可由使用者修改。
- [ ] 修改某片外門的 inner-door/frame offset 不污染其他外門。
- [ ] Save/Reload 保留設定。
- [ ] 多門時每片都以自己的外門面為 datum。
