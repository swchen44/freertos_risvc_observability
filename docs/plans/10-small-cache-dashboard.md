# T4：8/8/32 KiB 最佳化 Dashboard

2026-10-06，承接使用者 go。沿用本機 Python、SVG/JavaScript 與離線 HTML 架構。

## 範圍與設計

以 T3b/T3c 已驗證 comparison.json 為輸入，來源 hash 固定於獨立 manifest。API 每次讀取檢查 hash、schema、通過狀態及成本/3C 守恆。這是既有實驗結果的視覺化，不代表每次開頁重新執行 raw trace oracle。

- 獨立 `/timing.html`、`/api/timing`，保留既有 TCP TX 頁。
- 三個比較組：T3b 單段四候選、T3c 單段回歸、T3c 13+0+51 chain。改善比例僅使用同組 baseline。
- SVG 時間/指令、3C miss、記憶體服務成本；函式大小表、可排序/調欄寬/移欄的結果表。
- filter 後 CSV 保留排序；數值與分母透明。時間使用 guest_ns；memory cycles 不冒稱 total CPU cycles；stack window 不冒稱 task-exclusive。
- 共用 JS/CSS，離線 HTML 內嵌同一資料與 assets，CSP 禁止網路連線。
- 視覺：沿用現有藍/綠/橙圖表，白底、深色文字；比較在上、歸因在下，基準与候選名稱保持可讀。

## 驗收

- [x] unittest：缺檔/竄改、錯誤 schema、成本與3C不守恆、組內 baseline、API、離線匯出。
- [x] Ruff、Web build、Node filter/CSV tests、完整 Python regression。
- [x] curl：API 與 HTML/assets 狀態、資料相等。
- [x] agent-browser：Web/離線篩選、排序、選列、CSV下載、SVG、無錯誤、離線無HTTP請求；保存截圖。
- [x] README/交接文件整理、驗收 receipt、Git commit。

## 明確保留的後續工作

新的 guest workload、ISR/observer/recorder/task-exclusive 成本分離、逐事件 PSF/cache 對時與新函式執行熱點不在本次資料集範圍。較多 request/pbuf chain 的實際模擬另立下一輪驗證；不能從現有四筆結果外推。

完成：clean commit `5955ce6` 上 230/230 tests，46.483 秒；Node 9/9，既有 UI 11/11；curl、agent-browser Web/離線均通過，含 hover、CSV 與 390px 溢位驗證。獨立 review 無 findings。最終 commit 與 push 另外查 Git；完整證據見 [completion.json](../../artifacts/verification/small-cache-dashboard/completion.json)。
