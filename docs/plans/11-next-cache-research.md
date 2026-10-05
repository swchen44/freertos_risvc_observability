# 下一輪 Cache／TCP 研究 Implementation Plan

> **For agentic workers:** 實作時使用 `superpowers:executing-plans` 逐項執行。使用者已指定 A → B → C；A 詳細計畫已由使用者 OK 核准，B/C 為後續里程碑，未勾選的工作不能宣稱完成。

**Goal:** 驗證 pbuf 最佳化跨 workload 的有效性，並逐步建立可守恆的成本歸屬及定位視圖。

**Architecture:** 延用既有 QEMU/FreeRTOS/TraceRecorder、raw trace replay、獨立封包 oracle 與 FastAPI/ECharts/Tabulator。分 A workload、B attribution、C views 三條，避免同時變更工作量與時間模型而失去可比較基準。

**Tech Stack:** Python 3.13、unittest、Ruff；RV32IMAC、-Os、現有 patched QEMU/GCC；本機 Web 與離線 HTML、curl、agent-browser。

**Spec:** [下一輪 Cache／TCP 研究設計提案](../design/next-cache-experiments.md)。狀態：順序已確認為 A → B → C；A 已完成 96 次擷取、分析與 Web/離線驗收；最後回歸與發佈收據整理中。

## Global Constraints

- 固定 `cases/timing/sysram-10-small.json`：L1I/L1D 8192 bytes、L2 32768 bytes、64-byte line、4-way、LRU；記憶體 write-through/write-allocate。
- 500 MHz 僅作 memory cycle→2 ns，另有 1 ns/instruction 基底；不稱為 cycle-accurate CPU。
- baseline/pbuf 每對只差單次走訪實作；同組 workload、輸入、工具、timer 與 compiler flags 一致。
- 新結果寫新目錄；正式 capture 前 commit 且 Git clean；保存完整 source/tool manifest。
- 舊來源 hash 與目前程式不符時，用歷史 commit 還原驗證；不能修改舊 manifest 讓新程式冒充原程式。
- Python 行為變更新增有意義的 unittest；Ruff、正式回歸、curl、agent-browser 與截圖是交付條件。

## Review Focus

1. 異長 payload 的 client sequence、ACK 或 expected bytes 仍寫死 64/128，讓錯誤測試通過。
2. Guest receipt 只是複製設定，沒有觀察 callback 收到的實際 chain。
3. 大 request 使 control 跨 tick，既有 `control ticks == 0` 不再成立；不能放寬 guard 後仍宣稱同樣的 IRQ 校驗。
4. 不同 compiler/linker layout、觀測碼或記憶體配置影響結果，卻把差異全算成演算法改善。
5. 將 ISR/recorder/task 重複加總，或把不完整 PSF 對時硬填成精確 task-exclusive 比例。

## A：TCP workload 擴充

### A1：版本化案例契約及獨立 oracle

**檔案：** 新增 `cases/tcp/workload-matrix-v1.json`、`src/psf_lab/tcp_workload.py`、`tests/unit/test_tcp_workload.py`；延伸 `src/psf_lab/tcp_session.py`。檔案已新增。

**介面提案：** `load_workload(path, case_id) -> dict` 回傳 `id, request_bytes, request_segments, rounds`；`validate_session(packets, metrics, *, workload=None)` 保留既有省略參數行為；host 依固定測試契約推導 payload/seq/ACK，不以 guest 結果作 expected。

- [x] 先寫錯誤設定測試：0/負值/bool/float 長度、總和不符、超過8段、首段0、未知欄位；明確拒絕。
- [x] 寫資料被修改的 oracle 測試：錯誤 ACK、少1 byte、同長錯內容、chain receipt 遺漏/錯 totals，必須失敗。
- [x] 實作契約及 oracle，讓 64-byte 舊 API 與既有 fixtures 全部保留。
- [x] 使用 `python -m unittest discover -s tests/unit -p test_tcp_workload.py -v` 驗證，執行 Ruff，commit。

### A2：Guest 參數化及擷取

**檔案：** `firmware/app/cases/tcp_request_response.c`、`firmware/Makefile`、`tools/tcp/run_live_cache.py`、`src/psf_lab/tcp_session.py`；新增 `tests/unit/test_tcp_workload_runner.py`。

**介面提案：** runner 新增 `--workload-id`，從版本化 registry 取參數；與既有 `--tcp-workload` 的非預設值互斥。manifest 保存完整 workload 與 registry hash。

- [x] 先測 CLI 互斥、未知案例、manifest 缺少 workload/hash 的拒絕行為。
- [x] request buffer、收到的累積 bytes、client_seq、receipt array 改用有限 compile-time 參數；保留舊設定編譯路徑。
- [x] callback 遍歷實際 `len/tot_len` 保存 receipt；最多8段，輸出 buffer 寫入要逐次檢查剩餘容量。
- [x] 相同 wire packet 在 harness 建立 chain；首段容納完整 IP/TCP headers，callback 才驗 payload shape。
- [x] 先建置 baseline/pbuf；保存 text/data/BSS/map/assembly，不執行正式 capture 前先 commit。
- [x] 使用最大 request A08 的 4 次探索測試記錄 wall time、artifact bytes、control/injection tick 行為；若 IRQ 假設不成立，停止該案例正式量測並記錄，另訂 oracle 校驗，不增加容差掩蓋原因。

### A3：成對矩陣與重現證據

**檔案：** 新增 `tools/tcp/analyze_workload_matrix.py`、`tests/unit/test_tcp_workload_matrix.py`、`docs/tcp-workload-matrix.md`；正式資料位於新 `runs/tcp-workload-matrix-v1/`，分析位於 `artifacts/verification/tcp-workload-matrix/`。

**輸出契約提案：** `tcp-workload-matrix-v1`；每列包含 `workload_id, variant, repeat, timing_mode, request_bytes, request_segments, guest_ns, instructions, memory_cycles, cache counters, oracle_verdict, evidence paths/hashes`。

- [x] 測試缺 repeat、不同工具/profile、跨 workload 比較、竄改 packet/source/hash，必須拒絕或明確隔離。
- [x] 第一批 A01～A04，48 次正式執行；每組同 workload baseline/pbuf wire bytes 一致、兩個 request/response/ACK/FIN/資源歸零。
- [x] 驗證 PSF 邊界、event 完整性、native/Python 成本守恆；三次重跑差異逐筆保存，不能只留下最好結果。
- [x] 第一批通過才執行 A05～A08；每組改善率以相同 workload baseline 為分母，同時保存絕對值及 code size。
- [x] 任一案例變慢也保留；報告解釋可證明的原因，未能歸因就標記未知。

### A4：結果進入 Web／離線

**檔案：** `src/psf_lab/timing_dashboard.py`、`web/src/timing-view.js`、`web/src/timing.js`、`web/timing.html`、相關 Python/Node tests 與 `tools/tcp/verify_timing_dashboard.py`。

- [x] 測試每個 workload 獨立 baseline、篩選後分母不變、錯誤/未通過結果不混入成功比較。
- [x] 增加 workload 選擇及 request shape；沿用 SVG/表格/CSV，不改既有 T3b/T3c frozen reports。
- [x] curl 核對 API 數值；agent-browser 核對 Web/離線組別切換、hover、排序、CSV 下載，保存截圖。

## B：成本歸屬，獨立里程碑

**現有入口：** `src/psf_lab/tcp_hotspots.py` 已提供 PC self-cost；`src/psf_lab/live_cache_irq.py` 驗證 observer/task switch，但沒有逐 access 執行上下文。

- [ ] B1 新增 `src/psf_lab/cost_attribution.py` 與 unit tests，從固定 ELF/source ranges 建立 code-role mapping，重疊/未解析/邊界 PC 必須測試。
- [ ] 各函式 self-cost 合計等於全域 instructions/memory cycles；未解析留獨立分類，不能丟棄。
- [ ] B2 先盤點 `tools/tcp/live_cache.c` 與 FreeRTOS port 的可觀察 IRQ/task 邊界，產出上下文對齊設計；需要新增 hook 或 trace schema 時先更新規格。
- [ ] 用可手算的 task→IRQ→nested call→return fixture 驗證上下文狀態機；缺邊界、巢狀不匹配必須拒絕或標 unknown。
- [ ] 分別列 context/code-role 的交叉表，任一維度均守恆；確認後才使用 task-exclusive 標示。

## C：定位視圖，拆成 C1/C2

- [ ] C1 重播既有 raw trace，輸出 function/PC self instructions、memory cycles、3C misses，使用該 run 的 ELF；新 `tests/unit/test_hotspot_report.py` 檢查總和、unresolved、截斷不可改分母。
- [ ] C1 在 Web/離線呈現 metric 排序、function filter、source line 僅在 addr2line 有證據時顯示；CSV 匯出完整篩選資料，圖表 top-N 需標記總數。
- [ ] C2 先建立 `docs/design/cache-psf-time-alignment.md`，盤點原始 access schema、事件順序、模型注入位置、mtime 粒度及 MMIO bypass；沒有足夠時間證據就保留 event index。
- [ ] 對齊測試至少涵蓋 IRQ 搶占、同 timestamp 多事件、缺失邊界、非零 capture 起點；保存對齊誤差及拒絕條件。
- [ ] 時間語意驗證後，再做區間拖拉/zoom、context filter、hover、CSV 和 Web/離線一致性。

## 各工作線共用完成條件

- [x] 工作線順序已由使用者指定 A → B → C。
- [x] A 的具體設計與計畫已審閱；B/C 到階段開始時再核對詳細設計。
- [ ] 先失敗再通過的單元測試，Ruff、必要 Node tests；正式回歸在 clean commit 上執行，log 放 repo 外避免造成 dirty source。
- [ ] 新 capture、來源/工具 hashes、restore 所需設定與程式已納入 Git；review 重要問題處理完成。
- [ ] README 更新需求、過程、已完成/未完成及截圖，連結驗證通過；不得把計畫當成結果。
- [ ] 最終 completion.json 記錄 tested commit、log SHA-256、實際 count、成功及失敗範圍。
- [ ] POC commit 後更新 root gitlink；依既有授權 push POC/root，遠端 SHA 查核一致。

## 本次規劃產物與狀態

A 實作、96 次正式 capture、16 份詳細 replay、Web/離線驗收已完成；結果與反例見 [A 報告](../tcp-workload-matrix.md)。最後全套回歸與 Git 發佈尚在收尾。B/C 尚未實作。

## A 實作時的測試契約範例

以下保留原設計的契約範例；實際測試已在 tests/unit/test_tcp_workload.py。`validate_workload(value)` 在 A1 的 `tcp_workload.py` 定義，輸入單一 registry entry，回傳驗證後的新 dict；不能原地修改輸入。僅接受 `id, request_bytes, request_segments, rounds`，其中 rounds 固定2、id 必須為 registry 唯一識別。

```python
# tests/unit/test_tcp_workload.py 的核心測試
import unittest
from psf_lab.tcp_workload import validate_workload

class WorkloadContractTests(unittest.TestCase):
    def test_empty_middle_segment_is_valid(self):
        case = dict(id="A02", request_bytes=64,
                    request_segments=[13, 0, 51], rounds=2)
        self.assertEqual(validate_workload(case), case)

    def test_wrong_sum_and_boolean_are_rejected(self):
        for parts in ([13, 0, 50], [True, 0, 63], [0, 64]):
            with self.subTest(parts=parts), self.assertRaises(ValueError):
                validate_workload(dict(id="bad", request_bytes=64,
                                       request_segments=parts, rounds=2))
```

A1 其餘測試包含未知欄位、request大於1460、超過8段、rounds不是2、同名id；A3 比較器不能把拒絕或缺少repeat的資料當成功列。

實作後的正式命令範例，`--workload-id` 已實作；正式 96 次執行使用此介面：

```sh
# poc/；來源須先 commit，目錄不得已存在。
PYTHONPATH=src .venv/bin/python tools/tcp/run_live_cache.py   --qemu .tools/qemu-time-control/qemu-system-riscv32-relative   --case tcp-irq --cache-profile small --checksum-opt Os   --tcp-variant baseline --workload-id A01 --repeats 3   --output runs/tcp-workload-matrix-v1/A01-baseline
```

Baseline/pbuf 各一個 output；runner 一次輸出 control/injection 配對。正式檔案清單、run count、案例 ID 必須由 manifest 完整列出，不能用 glob 出現多少就當完整。

## 計畫自我檢查

- 已確認 A 的互相依賴：registry → guest/receipt → oracle → 成對比較 → Dashboard。
- 已修正原流程圖的平行分支，改為使用者指定的 A → B → C。
- 已分開「順序已確認」與「A 具體設計已核准」，完成項目依實際收據勾選。
- 已補最大 workload 探索、IRQ guard、payload位址影響、同組wire hash、舊schema相容及失敗結果保留。
- B/C 目前為後續里程碑；在 A 尚未完成時，不把它們當成本輪實作項目。

## A 實作裁定

- 實際比較報告每組提供 injection repeat 1 代表列；`attempts` 保留完整 control/injection × 3，不丟棄重跑資料。
- A08 額外 receive-window ACK 已納入 oracle；未調整 IRQ guard。首次失敗 probe 也保留。
- 原始 96 次均做 native/Python audit；彙整重新 hash 全部 raw streams，另 replay 16 份代表 trace。
- `run_workload_matrix.py` 為後續重跑批次入口；正式本輪排程原始 log 保存於 verification/logs。
