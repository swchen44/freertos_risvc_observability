# M2：排程分析與對照案例 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立可追查的執行區間與 request 指標，完成 Logger、priority inversion、deadlock 三組對照，加上 Queue 共七個配置。

**Architecture:** 分析使用 M1 的語意事件與品質標記。案例先定義同步順序、guest 窗口與 oracle，再實作 firmware；harness 檢查事件關係與應用結果，不憑 UI 圖形判通過。

**Tech Stack:** M1 環境、Python unittest／Ruff、FreeRTOS task／queue／semaphore／mutex／notification。

**Spec:** [設計規格](../design/PSF-Lab-設計規格.md)；[共同契約](data-contract.md)

## Global Constraints

- 前置為 M1 Gate 通過；保留 PSF／JSON schema1 與來源 hash。
- 工作位置 `~/git/percepio/poc`；正式 run clean commit、獨立 oracle、host timeout。
- 七配置為 queue_baseline、logger_bad、logger_fixed、inversion、inheritance、deadlock_abba、ordered_locks。
- 結果僅對固定 QEMU virtual-time 模型有效，不換算成實體 recorder CPU overhead。
- 異常案例的驗收成功標成「預期重現異常」，不能顯示成無異常。
- 所有 Python 變更有 unittest 與 Ruff；每個正式 run 不覆寫。

## Review Focus

1. trace 邊界／loss 區間被算作 idle → T1 手工 timeline＋窗口測試。
2. Logger 改善是工作量變少 → T2 固定 request／logger 完成量與 ID 再比較。
3. binary semaphore 被錯當 mutex inheritance → T3 分開物件及 priority event 斷言。
4. ABBA 只因沒有事件就宣稱 deadlock → T4 必須有持鎖與等待環及 supervisor oracle。
5. 多次 run 使用不同 source／clock → T4 suite 在執行前鎖同一 commit，pair 檢查條件一致。

### Task 1: P2-T1：執行區間、request latency 與品質傳播

**Files**
- Create: `src/psf_lab/analysis.py`, `tests/unit/test_analysis.py`, `tests/fixtures/semantic_traces.py`、其 package `__init__.py`。
- Modify: `src/psf_lab/cli.py` 加 analyze；`docs/format-support.md` 增分析前提。

**Interfaces**
- Consumes: `parse_trace` JSON v1，event.fields 與 quality。
- Produces: `analyze(trace: dict) -> dict`，回共同契約 intervals／requests／metrics／quality；不改寫 trace。

- [x] **Step 1：手工建立排程與 request trace，寫失敗測試。** `semantic_traces.py` 的 `schedule_trace()` 直接建立 JSON，不呼叫 writer／parser；頻率1000Hz、origin0、A在0switch-in、B在10switch-in、complete30，無 loss。建立明確 case_end，而非以最後task switch作end。

```python
import unittest
from psf_lab.analysis import analyze
from tests.fixtures.semantic_traces import schedule_trace

class AnalysisTests(unittest.TestCase):
    def test_known_schedule(self):
        result = analyze(schedule_trace())
        self.assertEqual(result["metrics"]["known_ticks"], "30")
        self.assertEqual(result["metrics"]["task_share"]["A"]["running_ticks"], "10")
        self.assertEqual(result["metrics"]["task_share"]["B"]["running_ticks"], "20")
```

另測 request開始5完成25：response20、task execution依所屬 task intervals 算，兩者不可共用欄位。未完成 request 的 end／latency=null，不能補0。

- [x] **Step 2：執行 `python -m unittest tests.unit.test_analysis -v`，確認缺 analyzer 的紅燈。**

- [x] **Step 3：實作 event sweep。** task switch 關閉上一個 running interval；trace 開始到首個可信 switch 是 unknown。Create/delete 管 lifecycle，無證據的 ready／blocked 不推導。End取case completion／已知capture邊界，缺end則最後interval標open。

```python
# interval 與窗口相交的單一規則
left = max(start_ticks, window_start)
right = min(end_ticks, window_end)
visible_duration = max(0, right - left)
```

Sequence gap／未知排程事件後，直到足以恢復該分析狀態的明確事件前標unknown；單一 switch可恢復誰running，但不能恢復先前mutex持有關係。這些品質層分開保存；不在loss後繼續輸出確定的deadlock關係。

- [x] **Step 4：加入首尾open、相同timestamp、跨wrap、loss、object reuse、unknown actor、未完成request、空trace與純metadata測試。** Frequency0時保留ticks、秒值null，避免除以0；以手算10/30與20/30驗分母。CLI analyze不帶UI filter。

```sh
python -m unittest tests.unit.test_analysis -v
ruff check .
ruff format --check .
git add src tests docs/format-support.md
git commit -m "feat: derive trace intervals with explicit uncertainty"
```

- [x] **Step 5：對 M1 Queue trace 執行 analyze，保存與原始事件的人工抽查。** 圖表尚未建立，先核對兩段切換的offset、ticks、task；記錄結果於當日日誌。

### Task 2: P2-T2：Logger 干擾／改善對照

**Files**
- Create: `firmware/app/cases/logger.c`, `cases/logger_bad.json`, `cases/logger_fixed.json`, `tests/unit/test_logger_assertions.py`, `tests/integration/test_logger_pair.py`。
- Modify: `firmware/Makefile`, `firmware/app/case_api.h`, `src/psf_lab/harness.py`。

**Interfaces**
- Consumes: M1 `poc_mtime`／oracle／capture、T1 analyze。
- Produces: `compare_cases(pair_id: str, runs: list[dict]) -> dict` 第一組 `pair_id="logger"`，回 `{pair_id, verdict, assertions, issues}`。每個run dict含manifest、case、trace、analysis、oracle。

- [x] **Step 1：在 JSON 先固定控制條件與 pair assertions。** 每輪一個request，共8輪；coordinator priority5、worker2，logger_bad4／logger_fixed1。Worker busy2 ticks、logger busy8 ticks；只用poc_mtime busy loop模擬工作，不放printf。每輪coordinator先記request_start，再讓worker/logger可執行，自己block。下一輪等兩者完成才開始，確保工作量一致。

```json
{"pair_id":"logger","requests":8,"worker_ticks":2,"logger_ticks":8,"required_response_improvement_ticks":4,"same_work_required":true}
```

此門檻是受控實驗的驗收值，不是產品效能承諾。若實際不符合，判fail並查時鐘／排程／trace成本，不能偷偷改門檻。

- [x] **Step 2：寫測試讓相同delay、不同工作量或漏request都失敗。**

```python
result = compare_cases("logger", [bad_run, fewer_requests_run])
self.assertEqual(result["verdict"], "fail")
self.assertIn("workload_mismatch", result["issues"])
```

`bad_run`／`fewer_requests_run` 在此測試模組直接手工建立，8與7個 request，其他條件相同。先跑 `python -m unittest tests.unit.test_logger_assertions -v` 確認紅燈。

- [x] **Step 3：實作同一C檔的兩個priority配置。** 每輪phase是 START、LOGGER_BEGIN/END、WORKER_BEGIN/END、COMPLETE，user event與oracle共用request ID，oracle另外存開始／完成mtime。

```c
/* 同一份 logger.c，只有編譯設定不同 */
const UBaseType_t logger_priority = POC_LOGGER_FIXED ? 1u : 4u;
/* worker 與 logger 都由 coordinator 的通知啟動，禁止偶然 delay 競賽。 */
```

比較request response與execution分開，先要求oracle／PSF時間邊界一致、8個worker與logger工作都完成，再判每輪bad比fixed多至少4ticks。Raw mtime換算使用已核對frequency，不硬寫1tick=某host時間。

- [x] **Step 4：跑 unit／Ruff、commit code，再真實跑pair。**

```sh
python -m unittest tests.unit.test_logger_assertions -v
ruff check .
ruff format --check .
git add firmware cases src tests
git commit -m "feat: reproduce and reduce controlled logger interference"
python -m unittest tests.integration.test_logger_pair -v
```

Integration pair在一個 suite session開始前clean check一次，接續兩個run只允許該session自己新增產物；來源hash中途不變。輸出放local開發區，正式21run留T4 suite。

- [x] **Step 5：記錄兩組response分布、完整工作量與原始證據；將研究結果寫入日誌。** 若未重現仍保存fail，不把預測改稱觀察。

### Task 3: P2-T3：Priority inversion／inheritance 對照

**Files**
- Create: `firmware/app/cases/inversion.c`, `cases/inversion.json`, `cases/inheritance.json`, `tests/unit/test_inversion_assertions.py`, `tests/integration/test_inversion_pair.py`。
- Modify: `firmware/Makefile`, `src/psf_lab/harness.py`。

**Interfaces**
- Consumes: M1 recorder＋oracle、T1分析、`compare_cases`。
- Produces: `compare_cases("priority", runs)`；`check_case` 加兩種case assertions。

- [x] **Step 1：先寫同步順序與測試。** Coordinator5、H4、M3、L2。L先取得鎖後通知coordinator並block在繼續通知；coordinator啟動H，自己block讓H確實嘗試鎖，再由H發起前的通知喚醒coordinator。coordinator收到H的嘗試通知後，以有上限的1-tick等待讓H執行到take，並用 `eTaskGetState(H)==eBlocked` 確認，最多5ticks；未到達就fail。設定 `INCLUDE_eTaskGetState=1` 並記錄檢查結果。這個等待用於驗證狀態，不能把經過1tick直接當作已阻塞；確認後才同時放行M與L。

L busy2ticks再release；M busy6ticks；H取得後記完成。inversion用預先give一次的binary semaphore；inheritance用mutex。

```python
result = compare_cases("priority", [semaphore_run, mutex_without_boost_run])
self.assertNotEqual(result["verdict"], "pass")
self.assertIn("missing_inheritance_evidence", result["issues"])
```

手工 trace 預期互斥版有priority inherit、L繼續執行、release／disinherit；binary版不能冒出相同證據。先執行 `python -m unittest tests.unit.test_inversion_assertions -v` 看紅燈。

- [x] **Step 2：實作同一C案例兩種物件。**

```c
SemaphoreHandle_t lock = POC_USE_MUTEX
    ? xSemaphoreCreateMutex() : xSemaphoreCreateBinary();
if (!POC_USE_MUTEX) {
    configASSERT(xSemaphoreGive(lock) == pdTRUE);
}
```

所有create與take/give return code都檢查。Recorder啟用必要priority／mutex事件。H開始take與實際blocked的證據分開，若SDK缺少必要hook，以應用phase補足但標明來源，不改名假裝kernel事件。

- [x] **Step 3：實作順序與oracle比較。** Semaphore版M工作在L release前完成；mutex版L被提升後先release，H取得早於M完成；L release後priority回原值。所有版本H最終完成，沒有deadlock。Missing/loss時回indeterminate而非判沒有繼承。

- [x] **Step 4：跑unit／Ruff、commit，再跑真實pair。**

```sh
python -m unittest tests.unit.test_inversion_assertions -v
ruff check .
ruff format --check .
git add firmware cases src tests
git commit -m "feat: verify priority inversion and mutex inheritance"
python -m unittest tests.integration.test_inversion_pair -v
```

- [x] **Step 5：保存鎖類型、priority、順序、wait時間與來源offset。** 改善值只對本工作量有效，報告保留case條件。

### Task 4: P2-T4：Deadlock／ordered locks、三次重跑與M2 gate

**Files**
- Create: `firmware/app/cases/deadlock.c`, `cases/deadlock_abba.json`, `cases/ordered_locks.json`, `tests/unit/test_deadlock_assertions.py`, `test_suite.py`, `tests/integration/test_case_suite.py`。
- Modify: `firmware/Makefile`, `harness.py`, `runner.py`, `cli.py` 加suite；`docs/case-results.md`、`docs/requirements.md`、README。

**Interfaces**
- Consumes: 七個case與全部先前模組。
- Produces: `compare_cases("locks", runs)`；`run_suite(root: Path, *, repeat: int=3) -> Path` 定義runner.py；CLI suite回整體exit code。

- [x] **Step 1：寫等待環與超時區別測試。** deadlock有T1持A等B、T2持B等A的四條關係；缺任一hold／wait證據時indeterminate。只輸入沒有進度的trace不能pass。

```python
result = check_case(deadlock_case, quiet_trace, {**oracle, "complete": False})
self.assertNotEqual(result["verdict"], "pass")
```

Suite test模擬其中一次host_timeout，整體必須fail且21個case attempt不會漏記；不同commit／clock的pair拒絕比較。先跑 `python -m unittest tests.unit.test_deadlock_assertions tests.unit.test_suite -v`。

- [x] **Step 2：實作可終止的兩種鎖順序。** ABBA各task取第一把後barrier，兩者都hold才放行取得第二把。Ordered版本兩者都A→B，**不使用「各持第一把後等對方」barrier**，否則修正版也被測試控制製造deadlock。改為取得任何鎖前的共同start gate。

```c
/* ABBA：T1=A,B；T2=B,A。Ordered：兩者=A,B。 */
SemaphoreHandle_t first = (POC_ABBA && task_id == 2) ? lock_b : lock_a;
SemaphoreHandle_t second = (POC_ABBA && task_id == 2) ? lock_a : lock_b;
```

Supervisor priority5等待20ticks，到期檢查task states／持有與等待記錄、寫case outcome、完成trace並退出；不要求被鎖task協助收尾，不在supervisor拿這兩把鎖。Ordered必須兩個worker完成；ABBA的正常收尾代表「已重現異常」。

- [x] **Step 3：實作suite來源保護與21個正式run。** 一次開始前clean check並保存source fingerprint，manifest記同一commit；每個child run後檢查tracked與untracked來源未變，只允許本session登記的輸出目錄新增。單獨run仍使用嚴格clean規則。更新 `runs/README.md` 說明suite-session例外只允許自身產物，非允許dirty source。

```python
# suite 結束必須檢查完整集合，不能只檢查已產出的成功結果
expected_attempts = 7 * repeat
if len(results) != expected_attempts:
    raise RuntimeError("Incomplete case suite")
```

Sequence count與timestamp允許依已定義模型變動；一致性看預期事件關係、outcome、工作量及pair門檻，不能要求不同run的PSF byte-for-byte相等。

- [x] **Step 4：跑測試、commit code、執行正式suite。**

```sh
python -m unittest discover -s tests/unit -t . -v
ruff check .
ruff format --check .
git add firmware cases src tests docs runs/README.md README.md
git commit -m "feat: validate lock ordering and repeatable case suite"
python -m psf_lab suite --repeat 3
```

Suite產生index指到21份run以及三組compare結果；用既有tests/integration/test_case_suite驗證該index的完整性，測試不得重寫oracle。

- [x] **Step 5：保存case教學與研究結論對照。** `docs/case-results.md` 每組列問題、條件、PSF事件、原因、修改、重測、限制；附offset／JSON／CSV與圖表待M3補。Commit正式產物與文件；失敗項保持未完成。

## M2 Gate

七個配置各三次，Queue／logger／priority／locks的獨立驗證通過；異常與改善有對應source及工作量；unknown／loss不當成正常。輸出仍是CLI／JSON，M3才建立互動GUI。U01～U16產品任務不因控制案例完成而結清。
