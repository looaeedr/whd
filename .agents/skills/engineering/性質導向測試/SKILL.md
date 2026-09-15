---
name: 性質導向測試
description: 當工作需要為大輸入空間設計 property / invariant、roundtrip、idempotence、oracle、generator strategy，或解讀 shrinking 後的 counterexample 時使用；它負責「該驗什麼性質」，不取代 pytest mechanics、TDD 或 debugging authority。
---

# 性質導向測試

`性質導向測試` 是 **property / invariant 設計層**。它回答「整個輸入域應該永遠成立什麼規則、怎麼產生有效輸入、失敗後如何判讀」，而不是教你怎麼配置 pytest fixture。

責任邊界固定如下：

- `Python測試實務`：pytest fixture、isolation、markers、mock/monkeypatch、CI mechanics。
- `tdd`：選定 public seam，先看到 RED，再最小實作到 GREEN。
- `diagnosing-bugs`：重現、最小化、hypothesis、根因與 regression loop。
- `性質導向測試`：property 選擇、generator strategy、shrinking / counterexample 分類。

因此本 Skill **不取代** `Python測試實務`、`tdd` 或 `diagnosing-bugs`。

## 1. 先確認這段行為真的適合 property-based testing

Example test 驗一個點；property 驗整個輸入域上的規則。只有當行為有可獨立描述的 algebraic shape / invariant 時，property-based testing 才有價值。

適合的常見 property：

| Property | 形式 | WHD 例子 |
| --- | --- | --- |
| roundtrip | `decode(encode(x)) == x` | Save→Reload、DXF export→reopen |
| inverse | `f(g(x)) == x` | 可逆轉換 |
| oracle | `new(x) == independent_reference(x)` | 重構前後、獨立 verifier |
| idempotence | `f(f(x)) == f(x)` | normalize / canonicalize |
| invariant | transformation 前後規則不變 | physical-part identity、合法幾何約束 |
| easy-to-verify | 複雜產生、便宜驗證 | topology / ordering / containment |
| commutativity | `f(a,b) == f(b,a)` | 真正對稱的集合／組合運算 |
| associativity | `f(f(a,b),c) == f(a,f(b,c))` | 真正具結合律的聚合 |
| identity | `f(x,e) == x` | 有明確 neutral element 的操作 |

強度原則：`no crash → type preservation → invariant → idempotence → roundtrip / oracle`。在 authority 支持的前提下，應選**最強（strongest）**、最能排除錯誤的 property；不要為了「有 property test」只驗 `no crash`。

若沒有可獨立表達的 property，誠實地用 example-based test；不要硬造一條看起來數學化、實際沒有產品承諾的規則。

## 2. Property 必須先 grounded 到 authority

WHD 的 property 不能從目前 production output、fixture、function name 或 shrunk counterexample 反推。

Grounding 順序遵守專案 authority：

1. 使用者本輪已核准的明確規格。
2. `AGENTS.md`、canonical domain spec、Registry / Source of Truth、UI/正式 source 定義。
3. 已明確標記的 interface / persisted format contract。
4. 測試與目前程式行為只能當 evidence，不自動升格成產品規格。

這一點尤其重要：property test 可以證明「某個已核准 invariant 被破壞」，但**不能回灌 production**，也**不能建立新的 Source of Truth**。

## 3. 避免兩種「看起來很強、其實什麼都沒驗」的 property

### 3.1 tautology

Tautology 是把 implementation 重算一次：

```python
assert result == same_formula_again(input)
```

如果 test 與 production 共用同一個錯公式，兩邊會一起錯、一起 PASS。應改驗獨立 property，例如 roundtrip、range、topology invariant 或真正獨立 oracle。

### 3.2 vacuity

Vacuity 是 property 因輸入被大量過濾而幾乎沒跑到有效案例。典型症狀是濫用 `assume()`。

原則：**constraint 放進 strategy，不能表達的跨欄位關係才用 `assume()`。**

```python
# 優先：strategy 直接只產合法值
@given(st.integers(min_value=1))
def test_positive(x):
    ...
```

對相依欄位使用 `st.composite`、`st.builds` 或等價機制，避免先亂產再大量丟棄。

## 4. Generator strategy 要代表「合法輸入域」

Generator 的工作不是製造隨機數，而是編碼已知 precondition 與邊界。

至少考慮：

- 正常範圍與合法離散模式；
- min/max、zero、single-element、duplicate 等邊界；
- 相依欄位間的合法關係；
- 已知 regression edge 用 `@example` 固定每輪都跑；
- invalid-domain case 與 valid-domain property 分開，不用同一條 property 混測。

WHD 幾何 property 生成 W/T/FW 或 multipart 組合時，合法範圍必須來自 authoritative input/domain rules，不是從現有 output 猜出一個「看起來合理」的區間。

## 5. Hypothesis / property library 是 dependency capability，不是假設

若專案已存在 Hypothesis 或其他 PBT dependency，沿用專案既有 library。

若不存在：

1. 先指出想新增的具體 property 與它帶來的價值。
2. 新增 dependency 是專案／使用者決策，不得自動偷偷加入。
3. 沒有 library 時可以先用 deterministic generated cases 或現有工具退化驗證。
4. **不得假裝** Hypothesis、plugin、fuzzer 已安裝或已執行。

## 6. Shrinking / counterexample 失敗分類

得到最小 counterexample 後，先分類，不要看到紅燈就改 production。

必須區分：

- **property 寫錯**：asserted rule 根本不是產品承諾。
- **spec ambiguous**：authority 沒有決定這個 edge；需要規格決策。
- **strategy 過寬**：input 違反已知 precondition。
- **test artifact / vacuity 問題**：生成或隔離方式造成假訊號。
- **code bug**：有效輸入明確違反 authoritative guarantee。

只有最後一類才是已 grounded 的產品 bug；`ambiguous spec` 不能偷改成自己猜的 expected behavior。

Counterexample 可以在 authority 釐清後縮成可讀 regression test；在此之前它只是診斷 evidence。它**不能回灌 production**、不能直接變成 offset / formula，也**不能建立新的 Source of Truth**。

## 7. WHD 優先 property 候選

優先找這些可獨立驗的 invariant：

- Save→Reload：合法專案資料 roundtrip 後語意等價。
- DXF export→reopen：export / reopen 後 authoritative geometry 等價，且 verifier 保持獨立 authority。
- 2D↔3D：同一 physical-part identity / authoritative projection 在合法轉換後保持一致。
- multipart：part identity、ordering/ownership、獨立顯示控制不因 roundtrip 漂移。
- canonicalization：重複 normalize/canonicalize 應 idempotent（若規格真的承諾）。
- domain registry：Registry 命中後不被 shadow validation 反向覆蓋。

不要把「目前所有輸出都一樣」當 invariant。Property 必須先有獨立 authority。

## 8. 執行與報告

1. 寫下 property 與 authority 來源。
2. 定義合法輸入域與 generator strategy。
3. 先用已知 counterexample / `@example` 驗證 property 能真的失敗。
4. 執行 property suite，保留 seed / shrunk counterexample / scope。
5. 對每個 failure 做 property / spec / strategy / code bug classification。
6. 若修 production，回到 `tdd` / `diagnosing-bugs` 的正式修正流程。
7. 報告 passed / failed / discarded / skipped，不把沒跑到的輸入當 PASS。

## 9. 來源與 WHD 適配

輸入來源：`trailofbits/skills@321ccfe628eca0d314b0ee4eaffcdd8a05639aaf` 的 `property-based-testing` Skill，以及 `references/generating.md`、`references/interpreting-failures.md`。

WHD 保留 property catalog、strategy-first constraints、tautology/vacuity 防護與 failure classification；但 authority 以 WHD 使用者／canonical spec／Registry / Source of Truth 為準，且永久遵守「validation 不能反推 production」。
