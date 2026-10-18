# C2a Web 效能候選修正（2026-10-18）

狀態：**候選 patch，尚未通過整體 pilot 驗收。** 基準分支 `poc-history`，remote SHA `dd8cbb4fdc75309d11629c740464c1e7557b3c7d`。不生成正式 40 runs／8 HTML；C2b 尚未開始。既有 A／B／C1、512 MiB 與 640 MiB 驗收證據保持原樣。

## 判讀與修改

1. **後端資料驗證是首次載入的優先路徑。** A02 baseline 有 430,324 rows／421 chunks，manifest 1,283,132 bytes。每次 chunk GET 原本都重新讀 catalog、讀／hash／parse／驗證完整 manifest，再解壓、驗證該塊全部 rows。一次完整 run 的 cProfile 中，約 33% 在 manifest loader、66% 在 chunk 解碼驗證。Profiler 有額外成本，不能拿它的 142.88 秒與既有 25 秒 Web gate 比較。
2. **最小後端修正。** `_parse_event_manifest` 以完整原始 bytes 作 LRU key，最多兩份；每次請求仍讀 catalog、manifest 並比對 SHA-256。公開 loader 回傳 defensive copy，chunk loader 只讀內部物件。不同內容即使 path／length 相同仍重新驗證；chunk 完整解壓、schema、hash、逐列與 totals 驗證全部保留。uint 正規表示式預先編譯，語意不變。沒有快取已解壓的 chunks。
3. **Worker 配置與加總是篩選的優先路徑。** 固定形狀的 BigInt counts 改用 literal 與固定欄位加總，減少每列 `Object.fromEntries`／`Object.keys`／遞迴配置。Context／function 比對在 dictionary 層預算；分桶沿已驗證連續 index 走精確 BigInt 邊界，避免每列 BigInt 除法。仍逐塊驗證，不使用摘要代替逐事件查詢，不改原始 cache replay。
4. **測試環境與渲染尚不能排除。** 歷史 `ready_seconds` 包含專用瀏覽器啟動、viewport 與工具往返；`filter_seconds` 包含 scroll／click／wait 往返。本次維持這兩個 gate 的原算法與 25s／5s 門檻，另加每個命令耗時、頁面 `query_ms`、Worker load／decode／aggregate、`render_ms`，供下一次瀏覽器重驗區分。`render_ms` 是圖表／表格 API 完成時間，不保證最後 paint 已完成。沒有實際新瀏覽器資料，不能宣稱 ECharts／Tabulator 就是瓶頸或已排除。

## 已做的驗證

原始工具 logs 以 lossless gzip 保存，inventory 同時記錄解壓後 hash。新收據在 [perf-20261018](../artifacts/verification/event-window/perf-20261018/)。這次是 Linux／Node 24.19.0／Python 3.12.14，後者不符合專案宣告的 Python 3.13 runtime；歷史瀏覽器收據則是 macOS Chrome 153，兩者不能直接比較。

- Node 23 tests 通過；build、Ruff、`git diff --check` 通過。
- C2a／共用 replay 相關 Python 10 tests 通過。新增暖快取篡改、公開回傳值污染隔離、hash-valid malformed API chunk、非 canonical wire、所有 cache counters／metrics、跨 1024 邊界、稀疏 context／function、uneven 512 bins 及超過 `2^53` 的精確 oracle。
- A02 baseline 的完整 query result（包含 totals、bins、function rows、event page）修改前後 SHA-256 均為 `2b16423c5555f70be38745dea03c3526e61e27c09169a7c8da41320ae4bb18be`。這只證明本次實際查詢的等價性，不把它延伸成 14 runs 全部重新驗收。
- 全 Python suite 實跑 320 tests，3 failures／6 errors，未通過。原因包括缺少 FreeRTOS 子模組來源、RV32 compiler／built firmware／pkg-config，以及 formal-run 要求 committed clean checkout。沒有停用這些檢查或把失敗改為 skip。
- Playwright 以 workers=1 實跑，第一個 case 因 Chrome executable 不存在而失敗，10 cases 未執行；afterEach 也因 beforeEach 未完成而出現 secondary error。Chrome 153 與 runtime Chrome 151 安裝均收到無效下載內容，另存實際 `Site Unavailable` 回應。沒有成功啟動測試 Chrome。
- Docs validator 的 baseline 422 個檔案 hash 通過；兩條既有 FreeRTOS source 連結因子模組未還原而失敗。這不是 docs 整體通過。

Node 引擎的壓縮輸入預載於記憶體，不包含 HTTP、主執行緒、SVG／表格、browser startup 或 browser RSS；Python benchmark 保留完整驗證但也不包含 HTTP。兩者只是同一環境內的資料路徑診斷，不是 25s／5s／640MiB 的替代驗收。最早 `baseline-engine.json` 與 cProfile 同時執行，只作探索；比較採用之後獨立執行的 `baseline-engine-isolated.json`。

## 本機資料路徑診斷（秒）

| 路徑 | 原版三次 | 候選版三次 | 中位數變化 |
|---|---|---|---|
| Python 全部 421 chunks，完整驗證 | 41.44／44.35／44.13 | 20.83／20.59／27.21 | 44.13 → 20.83 |
| Node 全 run 精確 query | 22.11／14.62／23.04 | 10.23／8.44／8.95 | 22.11 → 8.95 |

兩路徑修改前後各三次 hash 全部一致；backend gzip bytes 合併 hash 為 `60c923ea85e90f959416aa1f2520926185ae00384514f518ea485d598f661d21`。同一遠端 host 仍有明顯時間波動，不能把這個差異視為硬體無關的速度保證。完整數值、來源檔 hashes 與 gate 的未驗證狀態見 [summary.json](../artifacts/verification/event-window/perf-20261018/summary.json)。

## 重跑方法

以下從 repository root 執行。先還原既有文件說明的 A02 pilot 到 API 的 `formal` 路徑；該名稱仍只是 pilot14，不代表正式批次。輸出目錄必須新建。正式重驗請用已備妥的 Python 3.13、SDK／FreeRTOS／韌體與相同專用 Chrome／agent-browser。

```sh
mkdir artifacts/verification/event-window/new-perf-check
npm ci --prefix web
npm --prefix web run test:unit
npm --prefix web run build
PYTHONPATH=src .venv/bin/python -m unittest \
  tests.unit.test_event_window tests.unit.test_hotspot_events \
  tests.unit.test_event_window_export tests.integration.test_event_window_api -v
.venv/bin/ruff check .
git diff --check

# 無瀏覽器的診斷；不可採認為容量 gate
PYTHONPATH=src .venv/bin/python tools/tcp/benchmark_event_window.py \
  --output artifacts/verification/event-window/new-perf-check/backend.json
node tools/tcp/benchmark_event_window.mjs \
  artifacts/verification/event-window/formal/A02-baseline-b1-1-1 \
  artifacts/verification/event-window/new-perf-check/engine.json

# 在另一個 terminal 啟動 server
PYTHONPATH=src .venv/bin/python -m psf_lab serve --port 8017
# 此命令須完成三次，每次改成新的 output；先看每次 close/PID 收據再繼續
PYTHONPATH=src .venv/bin/python tools/tcp/verify_event_window_dashboard.py \
  --mode server --capacity-only --browser-executable /path/to/chrome \
  --output artifacts/verification/event-window/new-perf-check/server-capacity-1
# 完整互動驗收不加 --capacity-only；同樣使用新 output
```

完整 Web 完成並 close 成功後，使用候選版 build **重新匯出** A02 HTML 到新檔；停止 server、curl 證明無法連線，才依原 harness 執行 offline。不能使用舊 checkpoint HTML 來驗收新 Worker。匯出僅 A02 pilot，沒有擴大正式 40 runs。

```sh
PYTHONPATH=src .venv/bin/python tools/tcp/export_event_window_html.py \
  --workload A02 --output artifacts/local/candidate-A02-new.html
PYTHONPATH=src .venv/bin/python tools/tcp/verify_event_window_dashboard.py \
  --mode offline --html artifacts/local/candidate-A02-new.html \
  --browser-executable /path/to/chrome \
  --output artifacts/verification/event-window/new-perf-check/offline-full
```

仍須完成：相同 Chrome／限制下三次 Web／offline load、full-run filter、RSS／heap，候選版完整互動／CSV／取消／run race、C1 browser 與既有 Playwright 回歸，以及符合 runtime／SDK 的完整 Python suite 與獨立 whole-change review。所有 pilot 條件確實通過後，才另行考慮正式 40 runs／8 HTML／A08 最大 run。
