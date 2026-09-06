# T11: Family State Isolation：類型切換只共享 W/H/D/T

**GitHub Issue:** #11
**What to build:** 建立受電箱／金庫型彼此獨立的 family-specific state；切換 family 時只沿用 W/H/D/T，FW、折法、結構、角落與其他 family-specific 設定不得互相污染。

**Approved RED IDs:** R08, R09

**Blocked by:** None

**Status:** ready-for-agent

- [ ] R08 → GREEN：Vault → Receiving 時 W/H/D/T 沿用，不被 family default 重設。
- [ ] R09 → GREEN：Receiving → Vault 時恢復 Vault 自己的 FW／折法／結構。
- [ ] Vault → Receiving → Vault round-trip 後 Vault family-specific state 完整恢復。
- [ ] Receiving → Vault → Receiving 反向 round-trip 同樣成立。
- [ ] 不修改 config.ini。
