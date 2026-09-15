# 2026-08-29 已認證截角資料庫實作任務清單

## 目標
把已知正確截角公式提升為可版本化 registry。CERTIFIED / CERTIFIED_FROM_3D 命中時，正式製造結果以資料庫公式為準；3D solver 只做 shadow validation，不得覆蓋已認證公式。只有 registry MISS 才允許 3D fallback。

## A. Registry 資料模型
- [x] 建立 `ae_engine/certified_relief_registry.py`。
- [x] 定義 `CERTIFIED / PROVISIONAL_3D / CERTIFIED_FROM_3D / ENGINE_CONFLICT / FAILED`。
- [x] 規則具 `rule_id / revision / family / part / joint / intent / topology / formula / evidence`。
- [x] deterministic lookup；同優先級多筆命中回 `REGISTRY_AMBIGUOUS`。
- [x] 提供 revision existence 驗證與 registry 列舉 API。

## B. 金庫型固定截角資料庫
- [x] Head/Tail：上方 INSERT_OVERLAY 1T / 0.5T / 2T；下方 CROSS EXTRA_CUT BOTH 0.5T。
- [x] Door：CROSS RETAIN WIDTH 1T。
- [x] Indicator Box：CROSS RETAIN WIDTH 1T。
- [x] Indicator Door：CROSS RETAIN WIDTH 1T。
- [x] Base Plate：CROSS STANDARD。
- [x] known-model GUI state 與固定板件 adapters 改由 registry 供應，不再由 caller 自己硬建 C01~C04。

## C. 受電箱固定截角資料庫
- [x] Head/Tail 上方 family rule。
- [x] Head/Tail 下方 INSERT_OVERLAY 0.5T / 0.5T / 2T family rule。
- [x] Door / Indicator Box / Indicator Door / Base Plate family-specific 固定規則。
- [x] 受電箱 adapter / GUI family routing 使用 registry。

## D. Assembly Intent 已認證公式
- [x] `ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1`：linked-FW INSERT；`自訂(9)` 38×27 evidence。
- [x] `ENDCAP_TOP_INSERT_STANDARD_V1`：有獨立 `ytop1` 的標準 INSERT。
- [x] `ENDCAP_TOP_OVERLAY_STANDARD_V1`：flat-X + `ytop1` 的標準 OVERLAY。
- [x] `ENDCAP_TOP_INSERT_OVERLAY_STANDARD_V1`：標準二級 INSERT_OVERLAY。
- [x] `ENDCAP_TOP_INSERT_OVERLAY_LINKED_FW_V1`：無獨立 `ytop1` 的 linked-FW 二級 INSERT_OVERLAY，狀態 `CERTIFIED`；`自訂(10)` 正確 fixture 為 40×23 + 16×4，公式沿用既有 C04 製造契約。
- [x] Head canonical Y mirror：semantic TOP joint 在 Head canonical material 對應 physical bottom，Tail 對應 physical top。

## E. Solver 信任邊界
- [x] solver 先查 registry，再決定是否進 3D fallback。
- [x] CERTIFIED 公式採用後，3D 僅 shadow validation。
- [x] shadow 衝突回 `ENGINE_CONFLICT`，canonical 仍採 certified formula。
- [x] fallback OFF 只禁止 registry MISS 的 3D discovery，不得禁止 certified lookup。
- [x] unknown + fallback OFF 明確 `FAILED`，不猜幾何。
- [x] ambiguity 不得被 exception swallowing 後偷偷 fallback。

## F. Canonical 2D / 3D / Assembly 接入
- [x] Bridge raw material → registry/solver → canonical relief replay。
- [x] 已認證 Head/Tail replay 第二次 query，2D / single 3D / assembly 共用同一 canonical material。
- [x] collision overlay 保留 pre-solve probe，不拿已切完 material 誤報「未偵測到」。
- [x] fixed-policy visibility / dimensions 不影響 registry 製造真值。

## G. Save / Reload / Revision
- [x] 保存 `rule_id / rule_revision / trust_level / canonical_accepted / shadow_validation`。
- [x] reload rule revision 存在且 source fingerprint 有效時重現相同 canonical material。
- [x] stale/missing certified revision 不得靜默 replay 舊 cut。

## H. Promotion candidate
- [x] GUI 提供「建立認證候選」。
- [x] 只有 verified `PROVISIONAL_3D` 可建立 candidate manifest。
- [x] manifest 明確 `mutates_registry=False`；runtime 不可一鍵升格正式資料庫。

## I. Registry 驅動自動測試矩陣
- [x] GUI matrix 直接從 active Certified Relief Registry 列舉 Assembly Intent。
- [x] active relief/fixed rule 的 ID+revision 唯一、公式/evidence/schema 自動驗證。
- [x] 每種 intent 驗證 Head/Tail、pre-solve collision、canonical replay、2D=single3D=assembly、Save/Reload metadata。
- [x] 新增 active intent/rule 後不需人工白名單即可進驗收 gate。

## J. 實檔回歸
- [x] `自訂(9).p6fold`：Head/Tail `ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1@1`，38×27，collision visible，2D/3D/assembly/reload diff=0。
- [x] `自訂(10).p6fold`：Head/Tail `ENDCAP_TOP_INSERT_OVERLAY_LINKED_FW_V1@1`，`CERTIFIED`，40×23 + 16×4，collision visible，2D/3D/assembly/reload diff=0。

## K. 文件 / AI / 交付
- [x] 正式 design spec 寫回 `docs/superpowers/specs/2026-08-29-certified-relief-registry-design.md`。
- [x] 更新 verification、修改日誌、AI_HANDOFF、CONTEXT、目前主要任務、截角類型、AI SOP/踩坑庫。
- [x] Fresh final regression / py_compile。
- [x] FULL + UPDATE 同時間戳打包，實際解壓逐檔 SHA256 驗證，`config.ini` 不變。

> 最終 fresh gate 與封包驗證均已完成；本清單全部關閉。
