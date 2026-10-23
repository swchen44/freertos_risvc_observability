# C2a 正式本機驗收 · 2026-10-23

**本機驗收通過；發布狀態見publication.json。** 固定L1I8KiB/L1D8KiB/L232KiB，64-byte line、4-way LRU、write-through/write-allocate。這些是相對模型；不是實機效能或MCU RAM測量。

40 runs、19,177,626 events、18,753 gzip chunks已與保存C1完整facts/totals比較，來源/manifest/chunk hash皆通過。8份單檔HTML均小於95MiB，包含完整資料。API curl、agent-browser、真TCP faults及全部測試均有下方證據。C2b時間對齊尚未開始。

| 模式／workload | 範圍 | ready s | filter s | RSS MiB |
|---|---|---:|---:|---:|
| fast-A08-server | full-interactions | 13.83 | 3.08 | 502.62 |
| fast-A02-server | full-interactions | 10.66 | 2.44 | 489.64 |
| fast-A08-offline | full-interactions | 4.42 | 3.31 | 571.31 |
| fast-A02-offline | full-interactions | 3.60 | 2.73 | 600.52 |
| fast-A01-offline-capacity | capacity-only | 3.67 | 2.27 | 473.73 |
| fast-A03-offline-capacity | capacity-only | 3.88 | 2.60 | 427.66 |
| fast-A04-offline-capacity | capacity-only | 3.66 | 2.29 | 466.36 |
| fast-A05-offline-capacity | capacity-only | 3.51 | 2.29 | 469.92 |
| fast-A06-offline-capacity | capacity-only | 3.75 | 2.41 | 470.27 |
| fast-A07-offline-capacity | capacity-only | 3.42 | 2.30 | 471.89 |

所有上述browser收據都close=0且無剩餘owned PID；每次唯一session，逐一執行。RSS是Chrome程序子樹0.2秒採樣總和，可能漏瞬間峰值並重複計算共享頁；不是leak證明或所有電腦的保證。C1使用原heap政策，C2a使用指定headless/64MiB V8 old-space設定。

## 使用與還原

- Web：POC根目錄安裝既有依賴、`npm --prefix web run build`，再`PYTHONPATH=src .venv/bin/python -m psf_lab serve --port 8017`；確認curl `/api/event-windows`回200後開`http://127.0.0.1:8017/event-window.html`。
- Offline：直接開`artifacts/offline/event-window/A01.html`至`A08.html`，不需要Python/網路。驗收時停止server、阻擋HTTP/HTTPS，resource list無網路。
- 新checkout已有正式40-run chunks，無須再解壓舊pilot。舊pilot14與早期HTML在checkpoint/csv-memory目錄；不得拿舊serving路徑名稱當正式驗收。
- 重生資料：build_event_windows.py必須指定新output；每run會重新連續replay並與C1完整facts比對。不要覆寫既有capture或驗收目錄。

## 檔案

- `completion.json`：全部gate、來源/tested commit、10份容量收據、40-run/8HTML摘要。
- `ui/`：A02/A08 Web/offline完整互動，其他6HTML容量、C1/lifecycle/capability及故意失敗的close證據；screenshots/CSV/logs均保留。
- `csv-equivalence.json`：Web HTTP與offline Blob的完整CSV逐byte SHA相同。
- `tcp-faults/`：獨立toy fixture真socket，正常200/exit0、late corruption200/exit18、first corruption503；沒有破壞正式資料。
- `history/`：先前RSS/時間/下載等待失敗，C1誤套heap限制、錯誤中介層與preflight意外啟動等，皆未改寫原收據。
- `tests/`、`playwright/`、`driver/`：Python328/Node25/Ruff/Playwright11、RED/GREEN、實際命令/host aggregate load與序列driver。
- `environment.json`、`review.md`、`inventory.json`：工具版本、獨立source review與每檔SHA/大小。

## HTTP CSV與取消邊界

Web先完成既有Worker選區/驗證/統計，再透過同源`GET /api/event-windows/{run_id}/events.csv?start=...&end=...&context=...&function_query=...`原生下載。Server只保留manifest、當前chunk與約64K字元緩衝加當前一列，不在頁面建立約105MB CSV Blob。Offline仍逐塊Blob，沒有Python依賴。兩路UTF-8、QUOTE_ALL、CRLF、formula guard及完整欄位/精度相同。

分析/驗證進度未完成時，頁面取消會終止Worker且不得啟動下載；交由原生下載後，由瀏覽器下載列取消。UI明示此邊界。原生下載完成等待180s、非gate互動命令120s，沒有放寬25/5秒與640MiB等gate。這次104.9MB curl為38.12秒；不是UART/PSF/MCU throughput，也不是公平速度A/B測試。

## 真實發現與限制

- UTF8 transfer trial未證明RSS收益，因此撤回；完整before/after CSV及source快照仍在csv-memory目錄。
- BaseHTTPMiddleware曾讓late fault在log拋錯後仍回正常HTTP結尾，curl誤以為成功。pure-ASGI LocalOnly保留相同localhost/origin規則，真TCP regression已證明截短變傳輸失敗。
- Preflight失敗時舊診斷eval會意外啟動預設Chrome；該次RSS814464KiB無效。已關閉能歸屬本次的8個程序，新增unit禁止preflight失敗呼叫browser/process table，並改唯一session。其他無法歸屬的Chrome未碰。
- 前面650MiB/6.48s等真失敗仍保留；本輪通過是特定本機/版本的驗收，不代表歷史不存在。最後額外移除重複數字解析與全塊總和，三組A08完整JSON hash一致且host分析約快2成；不是SDK CPU loading百分比。
- Cache event index與PSF ticks獨立，沒有自創timestamp/插值/連動。模型輸入/連續暖cache不因查詢區間重置。
- 跨機實測已依使用者決定暫緩；本資料可還原分析/HTML，重新compile/capture仍需現有toolchain與source lock。未做實機PMU、SDK overhead校準或C2b anchors。

Page heap只採初始與完整filter後的Chrome回報點，非全時段/Worker/native heap峰值；RSS採樣與此不同。較早相同工作負載的時間失敗也保留，不能外推所有主機的保證。
