# T13: Receiving Base Plate 55 Contract

**GitHub Issue:** #12
**What to build:** 恢復受電箱底板四邊縮正式預設 Top/Bottom/Left/Right = 55 mm，並將 family shrink 與 local seam relief 分離。

**Approved RED IDs:** R01, R02

**Blocked by:** None

**Status:** ready-for-agent

**Required contract:** Receiving base plate → 55/55/55/55 family default → nominal resolved plate → local seam relief。

- [ ] R01 → GREEN：新 Receiving 預設固定為 55/55/55/55。
- [ ] R02 → GREEN：local seam relief 不得把 55 吃掉或改成 0。
- [ ] Resolve / Rebuild / 2D↔3D / Save/Reload 後仍維持 55。
- [ ] 修正與正式規格衝突的舊 Receiving shrink=0 regression。
- [ ] Vault base plate policy 不受影響。
