# Phase6 已認證截角資料庫與 3D Fallback 架構規格書

**Certified Relief Registry / 3D Discovery & Shadow Validation**

- 版本：v1.0 — 2026-08-29
- 狀態：v1 架構已實作並進入回歸保護

## 1. 文件目的

本規格定義 Phase6 板金系統中「已知正確截角公式」與「3D 幾何求解器」的正式責任邊界。核心目標是保護已驗證、已認證的製造公式，不再允許 3D solver、容差、triangulation、renderer 或 solid kernel 的改版，把原本正確的截角結果改成錯誤結果。

新的最高原則為：已知組合由「已認證截角資料庫」提供製造 Source of Truth；3D 幾何求解只在資料庫查不到時負責 discovery/fallback，並在所有情況下可作為獨立 shadow validator，但不得擅自覆蓋已認證結果。

## 2. 問題背景與設計動機

目前 3D 求解鏈曾出現以下風險：同一組封頭／封尾資料在單板 3D、2D、組合圖間出現 40×27、39×27、38×27 等不一致；solver 將 skin 接觸帶誤判為穿透；OVERLAY 被求出非法二級薄片；求解後再用最終幾何偵測碰撞而顯示「未偵測到穿越」；修正一種組合時可能影響另一種已知正確組合。

這些問題共同指出：把「所有已知與未知組合」都交給每次即時計算的 3D solver 作為唯一真值，對製造系統風險過高。需要把已確認的知識固化為可版本化、可追溯、可回歸的認證規則，並讓 3D solver 的責任逐步收斂到未知區域。

## 3. 核心架構原則

本架構採「Certified-first，3D-fallback，3D-shadow-validation」三層責任模型。

A. CERTIFIED 命中時：公式結果直接成為 canonical relief。3D 可以檢查是否有衝突，但不得修改、擴大、縮小或改變其拓撲。

B. 查不到 CERTIFIED 時：才允許 3D solver 產生 provisional relief。結果必須標記來源與可信等級，不能偽裝成已認證公式。

C. 任何新組合在累積足夠驗證證據後，可將 provisional 規則整理成公式並升級為 CERTIFIED。隨資料庫增加，3D solver 的 fallback 使用範圍應逐步縮小。

D. 資料庫必須保存「參數化公式與適用條件」，禁止把某一次特定參數算出的 38×27、25×11.482 等結果直接寫死成通用答案。

## 4. Source of Truth 新定義

舊原則「3D 幾何是所有截角唯一 Source of Truth」正式改為以下契約：

1. 已認證組合：Certified Assembly Relief Rule 是製造 Source of Truth。
2. 未知組合：3D solver 是暫定 discovery/fallback Source。
3. 顯示層：2D、單板 3D、組合 3D 只能消費同一份 Canonical Relief Result，不得各自重算。
4. 輸出層：DXF / NC / batch export 必須消費同一份 canonical result。
5. 3D shadow validation 永遠不能反向覆蓋 CERTIFIED 規則，只能產生 PASS / WARNING / ENGINE_CONFLICT。

## 5. 信任等級與狀態模型

每一筆截角規則或求解結果至少必須具有以下 trust level：

CERTIFIED：已認證公式。正式製造真值。3D solver 不得覆蓋。
PROVISIONAL_3D：資料庫查無規則時，由 3D solver 即時求出的暫定結果。可使用，但必須明確標示未認證。
CERTIFIED_FROM_3D：歷史來源為 3D discovery，但已經過多參數、多方向、多板件與 Save/Reload 回歸後，整理成正式公式並完成認證。實際執行時與 CERTIFIED 同等級。
ENGINE_CONFLICT：CERTIFIED 公式結果與 3D shadow validator 顯著衝突。正式製造仍採 CERTIFIED，但必須阻止系統靜默吞掉差異，並留下診斷資料。
FAILED：未知組合且 3D solver 無法在合法拓撲與允許幾何內消除真穿透。不得輸出生產用 NC。

## 6. Certified Relief Registry 資料模型

每一筆規則建議使用與 CornerType 類似的語意資料模型，而不是散落在 if/else 中。最低欄位如下：

rule_id：全域唯一 ID。
revision：規則修訂版號。
status：CERTIFIED / CERTIFIED_FROM_3D / DEPRECATED。
cabinet_family：適用盤體家族，可為 ANY 或指定家族。
part_role：HEAD / TAIL / BOX_BODY / DOOR / BASE_PLATE / ...。
joint_face：TOP / BOTTOM / LEFT / RIGHT 或更細的 joint identity。
assembly_intent：INSERT / OVERLAY / INSERT_OVERLAY / 後續新增類型。
preconditions：板件結構、折彎是否存在、對稱條件、厚度條件、必要 feature flags。
topology_contract：合法截角級數、各級連接關係、允許／禁止的層級變化。
formula_x / formula_y：以 W/H/D/T/FW/折彎參數/局部幾何符號為輸入的公式。
secondary_formula：只有二級拓撲才允許存在。
symmetry_policy：NONE / MIRROR_IF_GEOMETRY_SYMMETRIC / ALWAYS_MIRRORED 等。
manufacturing_clearance：若有額外製造間隙，必須明確獨立於 3D tolerance。
source_evidence：來源文件、實測件、回歸案例、核准記錄。
solver_shadow_policy：該規則是否要求 shadow validation，以及允許差值。
introduced_at / supersedes / deprecated_reason：版本追蹤欄位。

## 7. 公式儲存原則

資料庫只能儲存「公式」，不能把單一案例的輸出尺寸當作公式。

例如「自訂(9) 的封頭上方 INSERT 在 T=2 時為 38×27」只能作為驗證 fixture；正式 registry 應保存能由當時板件折彎後接合線推導 38×27 的通用公式或幾何關係。W、D、FW、T、yl1、yr1、ytop1 等改變後，必須重新依公式計算。

禁止：INSERT = 38×27。
允許：INSERT 的 X 尺寸 = 某已認證局部接合公式；Y 尺寸 = 某已認證折彎／FW 公式；38×27 只是特定參數代入後的結果。

## 8. Registry 查找與優先級

查找順序必須 deterministic，禁止兩筆規則同時命中卻依載入順序決定結果。建議優先級：

1. cabinet_family + part_role + exact joint + exact assembly_intent + exact structure/preconditions。
2. cabinet_family + part_role + joint + assembly_intent 的較通用規則。
3. ANY family 的共享規則。
4. 無 CERTIFIED 命中 → 進入 3D fallback。

若同一優先級存在兩筆有效 CERTIFIED 規則同時命中，必須回報 REGISTRY_AMBIGUOUS，禁止任意選一筆。規則 revision 只能透過明確 supersedes 關係取代，不得以『最新檔案』暗中覆蓋。

## 9. Canonical Relief Result

無論來源是 CERTIFIED 或 PROVISIONAL_3D，後續系統只能消費統一的 Canonical Relief Result。最低內容：

part_id / corner_id / joint_id；來源 rule_id 或 solver run id；trust_level；topology；primary dimensions；secondary dimensions；local material polygon / cut profile；units；source parameters snapshot；registry revision；solver version；validation status；diagnostics。

2D、單板 3D、組合 3D、尺寸標註、Save/Reload、DXF/NC 都只能讀這個結果。禁止單板 3D 再 fallback 到舊固定截角、禁止 2D 自己四捨五入成另一個製造尺寸、禁止組合圖重新求一份 relief。

## 10. 3D Solver 的新責任

3D solver 保留以下兩種責任：

A. Unknown discovery/fallback：只有 registry MISS 時才有權產生 provisional relief。它必須從真實板厚、折彎後實體、實際裝配位置與 joint responsibility 求解，並維持合法 topology contract。

B. Shadow validation：registry HIT 時，3D solver 只能在背景檢查 CERTIFIED 結果是否仍然沒有真穿透、是否符合當前 assembly。它不得把 shadow candidate 寫回 canonical relief。

3D solver 禁止做的事：用自己的 38.98 取代 CERTIFIED 38；為單級 OVERLAY 憑空增加 0.15 mm 第二級；因 tolerance 或 mesh 變化而修改已認證公式；在 shadow conflict 時靜默自動修正。

## 11. 接觸、穿透與容差契約

3D validation 必須區分 Contact 與 Penetration。正常面接觸、線接觸、板厚 skin 的數值接觸帶不得當成需要增加截角的真穿透。

solver tolerance 是數值運算參數，不是製造間隙。manufacturing clearance 必須另有欄位。若 tolerance 改版導致 shadow 結果不同，只能產生診斷，不得改 CERTIFIED 製造公式。

對已認證規則，若 shadow validator 判定仍有明顯實體穿透，狀態為 ENGINE_CONFLICT；正式結果保持 CERTIFIED，並要求檢查 3D model、assembly transform、板厚方向、joint 定義或規則適用條件。

## 12. 拓撲保護契約

每一筆 CERTIFIED rule 必須明確聲明合法截角級數與拓撲。3D solver 無權改變它。

例如單級 INSERT / OVERLAY：允許調整 provisional 案例的尺寸，但若是 CERTIFIED，連尺寸也不得由 solver 改；更不允許增加第二級薄片。

INSERT_OVERLAY 若合法定義為二級，則 canonical result 必須保留二級關係。solver 不得將二級壓成單級，也不得新增第三級。

對 registry MISS 的新組合，3D discovery 可以提出新 topology candidate，但在升級為 CERTIFIED 前必須保留 PROVISIONAL_3D 狀態，且不得污染既有規則。

## 13. 3D Discovery → Certified Promotion 流程

新組合的正式升級流程：

1. Registry MISS。
2. 3D solver 產生 PROVISIONAL_3D candidate。
3. 建立參數化 fixture，不只保存單一尺寸。
4. 以多組 W/H/D/T/FW、折彎參數、Head/Tail、左右／上下接合面驗證。
5. 驗證求解前碰撞可見、求解後零真穿透。
6. 驗證 2D = 單板3D = 組合3D = Save/Reload = DXF/NC。
7. 檢查 topology 穩定，不因 mesh/tolerance 小變動產生額外薄片。
8. 從多組結果整理出可解釋、可維護的參數化公式。
9. 人工審核公式與適用條件。
10. 寫入 registry，狀態升為 CERTIFIED_FROM_3D。
11. 建立固定 regression fixtures，solver 後續只能 shadow validate。

## 14. 新組合自動測試矩陣

測試矩陣不能手寫只列目前知道的 INSERT / OVERLAY / INSERT_OVERLAY。所有已註冊 Assembly Intent / Relief Rule 必須由 registry 自動列舉進參數化測試。

每個 CERTIFIED rule 至少驗證：Head/Tail（若適用）；所有適用 joint face；左右對稱與非對稱情境；不同 T；不同 FW；至少一組尺寸縮小／放大；求解前 collision probe；套公式後零真穿透；2D/單板3D/組合圖一致；尺寸標註一致；Save/Reload 一致；DXF/NC canonical output 一致；registry revision round-trip；shadow validator 不得覆蓋 canonical result。

新增組合若沒有測試 fixture、沒有 registry entry、或測試未通過，不得標記為 CERTIFIED、不得視為正式可生產功能。

## 15. 已知規則的不可變性與版本升級

CERTIFIED 規則不是永遠不能改，但只能透過顯式版本升級：Rev.N → Rev.N+1。禁止 solver、UI 或 renderer 在 runtime 偷偷改它。

升版必須包含：修改原因；舊公式與新公式；受影響 assembly intents / families / joints；migration 決策；舊專案載入策略；回歸比較；生產影響；核准記錄。

既有 .p6fold 必須保存足以辨識當時採用的 registry revision。載入舊檔時若目前 registry 已升版，系統不得無提示地重算成新尺寸；至少要能明確顯示『使用儲存結果／升級到新規則』的政策。

## 16. Save / Reload 契約

專案檔至少要保存：canonical relief result、source trust level、rule_id、rule_revision、source parameter snapshot、solver_version（若 provisional 或 shadow）、validation status。

Reload 後若 rule_id + revision 仍存在且輸入參數未改，必須重現完全相同 canonical material。不得因目前 solver 版本不同而重新改寫 CERTIFIED 結果。

若資料庫規則缺失、revision 不存在或輸入結構已變更，必須明確 invalidation 並重新走 registry lookup，而不是靜默 fallback。

## 17. UI 與診斷要求

每一個截角至少應能顯示來源：已認證公式、3D 暫定、3D 衝突、人工 Override（若未來支援）。

建議顯示：規則名稱 / rule_id；revision；實際尺寸；拓撲級數；shadow validation 狀態；若有 ENGINE_CONFLICT，顯示『正式製造採已認證公式，3D 驗證衝突』，並提供診斷資訊，不可自動改值。

組合圖的碰撞區應使用求解／套公式前 probe 來顯示『原始碰撞』，並可另外顯示套用 canonical relief 後的 residual penetration。不能拿已切完的最終板件再說『未偵測到碰撞』。

## 18. 人工 Override 邊界

若未來保留人工 Override，優先級必須明確且可追蹤。建議只有在特殊製造需求下才允許，且不能偷偷改寫 registry。

Override 應保存：原 CERTIFIED/PROVISIONAL 結果、人工值、原因、操作者、時間、是否允許生產。Shadow validator 仍可檢查 Override 是否造成穿透，但不得自動將 Override 寫成 CERTIFIED。

## 19. 相容性與遷移策略

第一階段不刪除現有 solver，而是在其前方加入 Certified Relief Registry lookup，並把 solver 降級為 fallback/shadow validator。

既有 CornerType / Assembly Intent 保留作高階語意輸入，但已知固定截角公式逐步搬入 registry。舊散落公式在完成一一對照與 regression 後才可刪除；禁止一次大改把所有公式搬走而沒有 deletion test。

建議先從目前已反覆確認的封頭／封尾上方 INSERT、OVERLAY、INSERT_OVERLAY 建立第一批 CERTIFIED rules，再逐步納入 CROSS 與其他板件／接合面。

## 20. 第一批認證資料建議

第一批 registry 應只放「目前已經有足夠證據」的規則，不為了填滿資料庫而猜公式。

建議候選：封頭／封尾上方 INSERT；封頭／封尾上方 OVERLAY；封頭／封尾上方 INSERT_OVERLAY；既有明確且穩定的 CROSS STANDARD / RETAIN / EXTRA_CUT 加工規則。

其中每一筆都必須先從現有程式、公式文件、實檔 fixture、3D 驗證與製造語意交叉核對。尚有爭議的公式保持未認證，繼續走 3D fallback。

## 21. 38×27 案例的正式定位

「自訂(9)」的 38×27 應被保存為 regression fixture / evidence，而不是通用硬編碼。它的用途是保護：已知 INSERT 接合公式在相同參數下必須永遠得到 38×27；3D shadow validator 即使因 skin、tolerance 或 mesh 算出 38.98、39 或 40，也不得覆蓋 canonical 38×27。

若未來公式 revision 合法變更，必須明確升版並解釋為何此 fixture 的預期值應變；不能因 solver 改版而自動更新測試答案。

## 22. 錯誤與失敗處理

REGISTRY_MISS：正常進 3D fallback。
REGISTRY_AMBIGUOUS：多筆同優先級規則命中，阻止自動決策。
ENGINE_CONFLICT：CERTIFIED 與 3D shadow 明顯衝突；保留 CERTIFIED，記錄診斷。
SOLVER_FAILED：未知組合無法求出合法 relief；不得輸出生產 NC。
TOPOLOGY_VIOLATION：candidate 改變不允許的層級拓撲；拒絕 candidate。
STALE_RULE_REVISION：專案引用的規則 revision 不可用；要求明確遷移。
CANONICAL_DIVERGENCE：2D/3D/組合/DXF 使用不同 material；視為高嚴重度 bug，禁止交付。

## 23. 驗收標準

本架構第一階段完成必須同時滿足：

1. Registry 可以註冊、查找、版本化至少第一批 CERTIFIED rules。
2. CERTIFIED 命中後，即使刻意讓 shadow solver 產生不同 candidate，canonical result 仍保持公式值。
3. Registry MISS 才會呼叫 3D fallback。
4. PROVISIONAL_3D 結果可 Save/Reload 且來源清楚。
5. 2D、單板3D、組合圖與 DXF/NC 共用 canonical result。
6. 自動測試矩陣從 registry 動態列舉，不依賴手工白名單。
7. 新增一個假的 Assembly Intent 後，若未提供 fixture / rule，測試門會自動要求 fallback 測試；若標記 CERTIFIED 卻缺驗證，CI 必須失敗。
8. 既有 38×27 fixture 維持；已知 OVERLAY/INSERT_OVERLAY 拓撲維持；不得產生假二級薄片。
9. config.ini 與不相關製造流程不得被本架構遷移順手改動。

## 24. 建議模組邊界

建議新增／整理為小而深的介面，不為了拆檔而硬拆：

relief_registry：規則定義、查找、revision、ambiguity 檢查。
relief_formula：安全、可測試的公式執行介面；不承擔 UI。
canonical_relief：統一結果型別與 serialization。
relief_resolver：唯一入口，流程為 registry → fallback solver → canonical result。
shadow_validator：獨立執行 3D validation，不可寫 canonical result。
certification_tests：從 registry 自動生成矩陣。

只有當現有模組已具備清楚 caller / Source of Truth 邊界時才抽出；禁止純粹為縮檔案或追求模組數量硬拆。

## 25. 正式決策摘要

本規格正式建議 Phase6 從「3D solver 全權決定所有截角」改為「已認證知識優先的混合架構」。

已知且已驗證的截角公式進入 Certified Relief Registry，成為不可被 runtime solver 改寫的製造真值；未知組合才由 3D solver discovery；3D 在已知組合上退居 shadow validator。所有結果統一進 Canonical Relief Result，再供 2D、單板3D、組合3D、Save/Reload、DXF/NC 消費。

這個架構的目的不是降低 3D 幾何的重要性，而是把 3D 的探索能力與已知製造知識分開：已知答案受到保護，未知答案仍可持續透過 3D 補齊，並逐步升格成新的已認證公式。


## 25. 2026-08-29 實作完成對照

本規格第一階段已落地。正式程式以 `ae_engine/certified_relief_registry.py` 為 registry owner。

已完成：
- 金庫型固定 EndCap / Door / Indicator Box / Indicator Door / Base Plate 規則入庫。
- 受電箱固定 EndCap / Door / Indicator Box / Indicator Door / Base Plate 規則以 family-specific 項目入庫，不靜默借用金庫型。
- Assembly Intent：標準 INSERT / OVERLAY / INSERT_OVERLAY 皆有 active certified formula rule。
- linked-FW INSERT：`ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1`，`自訂(9)` 為 38×27 regression evidence。
- linked-FW INSERT_OVERLAY：`ENDCAP_TOP_INSERT_OVERLAY_LINKED_FW_V1`，沿用 2026-08-21 已認證 C04 製造契約；`自訂(10)` 僅作 linked-FW regression evidence。狀態為 `CERTIFIED`；公式以 side fold、FW、T 推導。
- CERTIFIED / CERTIFIED_FROM_3D 命中時 3D 僅 shadow validate；`ENGINE_CONFLICT` 不得替換 canonical formula。
- registry MISS 才允許 3D fallback；fallback 開關不會關閉 certified lookup。
- `REGISTRY_AMBIGUOUS` 直接阻止自動決策。
- Save/Reload 保存 `rule_id / rule_revision / trust_level`，stale revision 不得靜默 replay。
- Promotion UI 只建立 manifest candidate，不允許 runtime 修改正式 registry。
- GUI acceptance matrix 直接由 active Certified Relief Registry 列舉 Assembly Intent；未來新增 active rule 會自動進驗收矩陣。

相容常數 `VAULT_C01..C04` 仍可保留在底層 geometry 作舊資料/API compatibility，但 production fixed-policy adapter 與 known-model GUI state 的 Source of Truth 已移至 Certified Registry。
