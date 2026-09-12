# DM7 展開工作區導覽 identity / topology 踩坑規則

<!-- DM7_OPERATOR_NAVIGATION_DURABLE_CONTRACT -->

## Authority 分層

1. `Phase6DesignerWorkspace.available_parts` / resolved manufacturing physical IDs 是 authoritative part topology。
2. operator navigation 只把 authoritative IDs 投影成 Menu / Structure Tree / Corner Data / child editor 可使用的 stable identity / hierarchy。
3. navigation memory 只是 View convenience，不是 manufacturing state、physical presence、Save/Reload truth 或 topology authority。
4. display label、tree/menu/tab index、widget text 都不是 stable identity authority。

## Explicit identity 永遠優先

- 明確選 `box_body`：保持 aggregate parent `box_body`；remembered child 不得覆蓋。
- 明確選現存 `box_body:<role>`：保持 exact physical-child identity。
- 明確選到已被 topology contraction 移除的 `box_body:<role>`：fail closed，`resolved=None / STALE_PHYSICAL_CHILD`；不得偷偷換 remembered sibling、nearest sibling 或 `children[0]`。
- remembered child 只可在語意明確是 `RESTORE_CHILD_CONTEXT` 時使用；remembered child 已 stale 時清除 memory，不猜下一片。

## Hierarchy 只是 projection

- parent/child hierarchy 只能從 authoritative `available_parts` 投影。
- aggregate `box_body` 不在 authoritative parts 時，不得為了 UI 好看自行創造 parent。
- parent 存在而 child topology 改變時，explicit parent 仍是 parent；child 新增/刪除不得改寫 parent identity。
- Menu / Structure Tree / Corner Data 必須共用同一 identity/hierarchy owner，不得各自維護 BoxBody resolver。

## Topology contraction / family switch

- authoritative family/structure topology 必須先 commit/sync，才重建 navigation projection / visible UI。
- 被移除的 active/selected physical child 應失效/清除，而不是自動跳 sibling/first child。
- Corner Data selection 是 view-only；不得因 navigation selection mutate manufacturing workspace。

## Save → Reload

- Project persistence 保存 authoritative project/workspace state；navigation memory、UI hierarchy、display labels 不升格 persistence truth。
- Reload 後先由 authoritative project state 重建 `available_parts`，再重新 project hierarchy。
- stale remembered child 不因舊 UI context 在 reload 後復活。

## 禁止 fallback

- `explicit parent -> remembered child`
- `stale child -> remembered sibling`
- `stale child -> children[0]`
- `label/menu text/tree text -> stable identity`
- `tab/list/tree index -> physical child`
- `Corner Data selection -> manufacturing mutation`
- caller-local duplicate hierarchy resolver

## Validation boundary

Regression / expected / fixture 只能判斷上述 contract 是否符合；不得把測試 output、UI order、label 或 observed current child 反向寫成 production topology/identity authority。

## Durable regression

至少永久覆蓋：parent → child → parent、child A → child B、stale explicit child、stale remembered child、topology contraction、missing aggregate parent、first family switch、Menu/Tree/Corner Data shared projection、Save→Reload、Corner Data purity，以及 source forbidden-pattern scan。
