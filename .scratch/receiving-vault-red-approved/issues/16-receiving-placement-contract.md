# T16: Receiving Door / Frame / Divider Authoritative Placement Contract

**GitHub Issue:** #16
**What to build:** 把外門位置、框位置、中隔 3D placement/orientation 收斂為同一份 Receiving family-aware authoritative placement contract，禁止各 consumer 自算 magic offset。

**Approved RED IDs:** R04, R05, R06-Door, R06-Frame-Top, R06-Frame-Left, R06-Frame-Right
**GREEN Guards:** R03, R06-Divider, R14

**Blocked by:** T11 / GitHub #11；T15 / GitHub #14

**Status:** ready-for-agent

**Required contract:** Receiving family coordinate → Outer Door Placement → Inner Door Placement → Frame Placement → Divider Placement。

**禁止:** door_z=depth/2、generic centered-depth origin、frame fallback (0,0,0)、divider 另算世界座標。

- [ ] R04 → GREEN：外門位於正確 Receiving 箱面。
- [ ] R05 → GREEN：中隔 3D 深度／方向正確，不穿出箱身。
- [ ] R06-Door → GREEN：door stable id 可取得 authoritative placement。
- [ ] R06-Frame Top/Left/Right → GREEN：三類 frame 都有 authoritative placement。
- [ ] 2D、3D、collision consume 同一份 transform。
- [ ] Resolve/Rebuild 不跳動。
- [ ] R03、R06-Divider、R14 持續 GREEN。
