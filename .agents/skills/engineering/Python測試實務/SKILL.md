---
name: Python測試實務
description: 當工作需要撰寫、整理或改善 Python pytest 測試，尤其涉及 fixture、parameterization、mock/monkeypatch、async、test isolation、markers、property-based testing、coverage 或 CI 測試結構時使用。
---

# Python測試實務

把這個 Skill 當成 **pytest 工程實務層**。它處理「測試怎麼寫得隔離、可讀、可重跑」，**不取代** `tdd` 決定要測哪個 seam、RED → GREEN 如何前進，也不取代 `diagnosing-bugs` 建立 repro、最小化與根因診斷的流程。

來源輸入為 `wshobson/agents` 的 `python-testing-patterns`，但 WHD 版以專案自己的 AGENTS / Preflight / Source of Truth / acceptance gate 為最高 authority。

## 1. 責任邊界

開始前先分清楚三層：

- `tdd`：決定 public seam、先看到 RED、最小實作到 GREEN、以及 validation authority 單向。
- `diagnosing-bugs`：決定怎麼重現、提高 reproduction rate、最小化、建立 hypothesis 與 regression loop。
- `Python測試實務`：在 seam 已確定後，選擇 pytest fixture、parameterization、mock/monkeypatch、async、marker、temporary workspace、property-based 與 CI mechanics。

因此：

1. 不因為 pytest 很方便，就跳過 seam / RED / GREEN。
2. 不因為能 mock，就把真正行為替換成 mock behavior。
3. 不因為 coverage 高，就宣稱需求或 final acceptance 已通過。
4. 若 domain 規格不清楚，先回到 authoritative spec / registry / 使用者確認；測試技巧不能創造產品規格。

## 2. Test isolation：測完不能污染專案

### 2.1 檔案與工作目錄

預設使用 pytest `tmp_path` / `tmp_path_factory` 建立 temporary workspace。除非測試目的本身就是驗證 repository mutation，測試不得直接覆寫：

- `config.ini`；
- `基準檔/**`；
- canonical registry / AI Library；
- production source；
- 其他 Git **tracked** 檔案。

這是 WHD 的 isolation 硬規則：**測試結束後 repository state 必須和測試前一致。**

對可能碰到真實檔案的測試：

1. 優先複製輸入到 `tmp_path` 後操作。
2. 若必須暫時修改真實檔，使用 `try/finally` 或 fixture teardown 保證還原。
3. 對高風險檔案保留前後 SHA256 / hash；必要時再用 `git diff --exit-code` 驗 tracked tree。
4. `config.ini`、基準檔等既有 invariant 若前後不同，測試即使 assertions 全 PASS 也不能接受。

禁止把「測試自己會清」當假設；cleanup 必須能被 assertion 或 invariant 證明。

### 2.2 Process / environment isolation

環境變數、cwd、time、global cache、singleton state 優先用 `monkeypatch` 或明確 fixture 管理，測完自動復原。不要讓 test order 決定結果。

fixture scope 採最小必要範圍：能用 function scope 就不要升 session scope。共享昂貴資源可以放大 scope，但 mutable state 必須在每個 test 前重置或提供獨立 instance。

## 3. Fixture 與 `conftest.py`

fixture 用來表達 **setup / resource lifecycle / teardown**，不是另一個 Source of Truth。

```python
@pytest.fixture
def project_copy(tmp_path):
    work = tmp_path / "case"
    work.mkdir()
    yield work
    # pytest 會清 tmp_path；額外資源在此 teardown
```

規則：

- fixture name 描述提供的能力，不描述內部實作。
- fixture 若含 setup + teardown，使用 `yield` 讓生命週期清楚。
- `conftest.py` 只放跨多個測試真正共用的 fixture；單檔專用 fixture 留在該檔。
- autouse fixture 要慎用，因為隱藏依賴會讓測試難讀；只有 repository invariant / unavoidable isolation gate 才值得考慮。
- fixture 中的 literal、expected output、snapshot、tolerance 仍只是 validation input，不能因為放進 fixture 就取得 production authority。

## 4. Parameterization：擴 invariant，不是製造規格

使用 `pytest.mark.parametrize` 時，目的是讓**同一 invariant**跨多組輸入成立。

適合：

- 正常／邊界／錯誤輸入；
- 多個箱型或模式共用同一已核准規則；
- 同一 parser / formatter / adapter 的等價行為；
- regression cases 已有獨立 authority 可證明 expected value。

不適合：

- 把目前 production 的大量輸出抄進表格，再宣稱它們是規格；
- 為了追求 case 數量混入不同 domain rule；
- 讓一個 parametrized test 同時測多個不相關行為。

每組 case 建議有清楚 `id=`，failure 才能直接指出是哪個 invariant instance。

## 5. Mock / monkeypatch：只隔離真正的外部邊界

`mock` / `monkeypatch` 適合隔離目前測試**不是要驗證**的外部邊界，例如：

- network / SaaS client；
- environment variable；
- injectable clock / randomness；
- 明確的 OS service adapter；
- 很昂貴且已有自己 contract test 的外部 dependency。

但不得把真正要驗的 seam **mock 掉**。對 WHD 特別禁止用 mock 取代：

- manufacturing / `geometry` 結果本身；
- DXF actual export → reopen → compare；
- `Save→Reload` persistence；
- multipart / physical-part identity；
- `2D/3D` parity / authoritative projection。

測 adapter 時可以 mock adapter 的外部 dependency；測 end-to-end seam 時則必須讓真實下游行為跑過去。

Patch 要 patch **被測模組查找依賴的位置**，不是盲目 patch 原始定義模組。Assertion 優先驗最終可觀察 behavior；call count 只有在「呼叫次數本身就是 contract」時才是主要 assertion。

## 6. Async、time 與 retry 測試

- 專案已安裝 `pytest-asyncio` 時才使用 `@pytest.mark.asyncio`；沒有 dependency 就先確認專案是否要加入，不能假裝 plugin 存在。
- async test 要 await 真正 coroutine，不用 sleep 猜完成時間。
- time-dependent code 優先注入 clock 或用 `monkeypatch`；只有專案真的有 `freezegun` 時才使用它。
- retry test 用可控制的 side effect 表達「暫時失敗 → 成功」「達上限」「永久錯誤不重試」，不要真的等 network/backoff wall time。

## 7. Property-based / fuzz 測試

`property-based` testing 適合已知 invariant、輸入空間很大、example-based case 容易漏邊界時使用。若要用 Hypothesis，先確認 dependency 實際存在或由專案正式加入。

正確資料流：

```text
已核准 invariant
    ↓
產生很多 inputs
    ↓
找到 counterexample
    ↓
證明 production 違反 invariant
    ↓
回 authority/root cause 修正
```

錯誤資料流：

```text
counterexample / shrink 出來的數值
    ↓
直接回灌 production offset / formula
```

**counterexample、fixture、expected、tolerance、probe result 都不得回灌 production。** 它們只能回答「目前結果是否違反規格」，不能建立新的 Source of Truth。

找到穩定 counterexample 後，可在 authority 已釐清時把它縮成可讀 regression case；若 authority 尚未確定，保留為診斷證據，不先硬編碼 expected production behavior。

## 8. Markers、skip、xfail

pytest marker 要表達可操作分類，例如 `slow`、`integration`、`gui`、`xvfb`、`requires_<capability>`。

- `skip` / `skipif` 必須附具體原因與條件；不要用「目前不方便」永久跳過。
- `xfail` 只用在已知且仍被追蹤的 defect / platform contract；能用 `strict=True` 時優先，避免 XPASS 長期被忽略。
- **SKIP 不等於 PASS。** 報告必須分開列 passed / failed / skipped / xfailed / xpassed。
- Headless PASS 不能推論 GUI/Xvfb PASS；反之亦然。
- **focused GREEN 只代表該 scope GREEN，不等於 final acceptance。** 若 `AGENTS.md` / `驗證板件與DXF` / release gate 要求更高層驗收，仍必須跑完。

不要因為 suite 沒有 FAIL 就把大量 SKIP 說成「全部通過」。

## 9. Coverage 與 CI mechanics

Coverage 是「哪些 code path 被執行」的觀測，不是 correctness 證明。

- 不從外部 Skill 範例直接搬一個任意 coverage threshold（例如 80%）變 WHD 硬規則。
- 若專案已有 coverage gate，遵守現有 gate；沒有時先用 report 找洞，再由專案規格決定是否建立 threshold。
- CI 要固定 Python / dependency provenance，並把 headless / GUI / platform-specific scope 分清楚。
- suite 分層：focused/unit → integration/roundtrip → project/final acceptance；低層 GREEN 不能冒充高層 GREEN。
- remote QA 一旦啟動，依 `monitoring-remote-qa` 鎖定 `run_id + head_sha` 到 terminal。

## 10. 寫測試前的快速檢查

1. `tdd` 的 seam / desired behavior 是否已確定？
2. 這是 unit、integration、roundtrip、GUI 還是 final acceptance？
3. 哪些依賴是真正外部邊界，哪些是這次必須跑真的 seam？
4. 是否需要 `tmp_path` / fixture teardown 防止污染？
5. expected value 的獨立 authority 是什麼？
6. parameterization 是否真的共用同一 invariant？
7. mock 是否讓測試失去抓到真 bug 的能力？
8. SKIP / xfail 是否會被誤報成 PASS？
9. 這輪 GREEN 到底只證明 focused scope，還是已滿足 final acceptance？

## 11. 來源與 WHD 適配

輸入來源：`wshobson/agents@a30778f8c4e6b0a87567941b7cca4f534bf642b6` 的 `python-testing-patterns`、`references/details.md`、`references/advanced-patterns.md`。

WHD 保留 pytest fixture、parameterization、mock/monkeypatch、async、temporary files、property-based、markers、coverage/CI 等實務；另外加上 repository isolation、validation authority 單向、真實製造 seam、SKIP/PASS 分離，以及 focused GREEN / final acceptance 邊界。
