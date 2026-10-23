# C2a Event-window Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking. 沿用本 session 原生執行與最後獨立 review；所有瀏覽器測試依序執行。

**Goal:** 用完整事件序號區間定位 Task／IRQ、函式與 Cache 成本，在本機 Web 與離線 HTML 得到一致結果。

**Architecture:** 重用 C1 的逐事件 cache replay，輸出固定 1024 列的 gzip JSON chunks 與來源 manifest。共用 JS worker 逐塊解碼、精確加總，主執行緒只接收圖表桶、函式表與進度。PSF 保留獨立時鐘視圖；本階段沒有 Cache↔PSF 時間映射。

**Tech Stack:** 現有 Python／unittest／Ruff／FastAPI、ECharts SVG／Tabulator／esbuild／Node、瀏覽器 Worker／DecompressionStream、curl／agent-browser。無新增第三方依賴或 CDN。

**Spec:** [C2 設計](../design/cache-psf-time-alignment.md)。使用者已選 A；本計畫只交付 C2a，C2b 必須在 C2a 完成後用另一份 clock-anchor pilot 計畫接續。

狀態：**Tasks1–6本機驗收完成，40 runs／8HTML與最新release證據已保存；發布checkbox待remote核對。C2b尚未開始。**

2026-10-13 review 修正 `0584229`：取消載入、CSV Blob parts、dictionary／gzip 拒絕、source mapping provenance。Python319、Node21、Ruff通過；獨立複查未發現未解的 Important。瀏覽器 RSS 超過512MiB，不能視為整體通過。[checkpoint 操作與還原報告](../event-window-dashboard.md)保存有效證據與已作廢的早期驗收。

歷史進度（2026-10-13）：Task1 完成；Tasks2–5 程式與 pilot 已實作，以下複合條件尚未全部勾選；Task6 完整資料／最終回歸／容量 pending。核准計畫的未勾選項不因單一 pilot 通過而自動完成。

2026-10-14 使用者明確核准：RSS 上限由512改為 **640 MiB**。只調整此項，其他容量條件維持；舊512MiB失敗收據保持原樣，新測試明列 `rss_limit_mib: 640`。2026-10-14 Web／offline RSS均通過；Web時間條件仍有失敗。[重驗紀錄](../../artifacts/verification/event-window/rss-640-20261014/)，正式批次保持未擴大。

2026-10-23：[時間續作](15-c2a-timing-followup.md)與[最新報告](../event-window-dashboard.md)。時間門檻通過，Web CSV匯出RSS650.36MiB仍超限；離線完整操作通過。正式批次維持未擴大。負向fixture已補測，複合項目仍逐項核對。

## Global Constraints

- Cache 固定 L1I 8192、L1D 8192、L2 32768 bytes；64-byte line、4-way、LRU、write-through/write-allocate。1 ns/I event + 2 ns/memory cycle 是模型成本。
- 選取半開區間 [start,end)，0 ≤ start ≤ end ≤ N；空區間合法。不得把 event index 換算為 PSF timestamp，不把一個 access row 稱為完整指令。
- replay 只在 capture 起點建立 cache，查詢區間不重置；MMIO bypass 不補造 raw rows。unknown/unresolved 必須保留。
- 沿用 C1 固定 40 run 集合；一個 workload 一份離線 HTML，共 8 份。每次只查一個 run，不同 run 的相同 event index 不代表相同執行時刻。
- gzip chunks 全量保存；1024 rows/chunk，最後一塊可較短。Worker 依序解碼，一次至多保留兩塊已解碼資料；切 run 先終止舊 worker、釋放 object URL。
- 大整數 wire 格式為十進位字串；JS 精確計算使用 BigInt。僅圖表像素座標可轉 Number，tooltip／CSV 保留精確值。
- Chrome／agent-browser 一次一個 session，Web close 成功後才開始離線；finally close，成功與失敗都保留 close receipt。Playwright workers=1；不得終止使用者的 Chrome。
- A/B/C1 保存資料不得覆寫；新產物在 artifacts/verification/event-window、artifacts/offline/event-window。先 A02 pilot，再擴大正式 40 份。
- 不改 guest、FreeRTOS、QEMU 或 PSF；C2b、PMU、SDK overhead 與因果 layout 實驗另列後續。

## Review Focus

1. 暖 cache 的區間第一筆不能變 cold miss；Task1/3 以切在重複 block 的 fixture 驗證。
2. hash 正確但 chunk 結構錯誤、缺尾塊或重複範圍必須拒絕；Task2/3。
3. 切換 run 後舊成功或失敗不能覆蓋新結果；Task3/4 request_id 與 worker termination 測試。
4. 超過 2^53 的成本不可經 JSON Number 或 CSV 捨入；Task3 精確 fixture。
5. 缺口或同 timestamp 的 PSF 不可自動排序、插值或暗示連動；Task2/4 保留 parser quality 與原順序。

## 檔案與介面

| 工作 | 新增 | 修改 |
|---|---|---|
| 1 逐列 replay | src/psf_lab/hotspot_events.py；tests/unit/test_hotspot_events.py | hotspot_report.py 僅改為彙總共用 iterator |
| 2 分塊資料 | src/psf_lab/event_window.py；tools/tcp/build_event_windows.py；tests/unit/test_event_window.py | 無 |
| 3 查詢引擎 | web/src/event-window-data.js；web/src/event-window-worker.js；web/tests/event-window.test.mjs | 無 |
| 4 UI | web/event-window.html；web/src/event-window.js、event-window.css | web/build.mjs |
| 5 API／匯出 | src/psf_lab/event_window_export.py；tools/tcp/export_event_window_html.py；tests/unit/test_event_window_export.py；tests/integration/test_event_window_api.py | src/psf_lab/server.py |
| 6 驗收 | tools/tcp/verify_event_window_dashboard.py；docs/event-window-dashboard.md | README、C backlog、此計畫 |

## Task 1：可觀測的逐事件 replay

介面：`iter_hotspot_events(rows, ranges, profile, *, contexts)` 逐列 yield dict，包含 index、pc、address、size、operation、context、role、function_id、owner 及 C1 empty_counts 全部欄位；Python 內部保持 int。最後一列消費後才可宣稱 context coverage 完整。

- [x] 新 unittest 先使用以下契約 RED；fixture 用現有 MemoryTiming 產生合法 raw cost，再設定同 PC、兩個 context。

```python
items = list(iter_hotspot_events(rows, ranges, profile, contexts=contexts))
self.assertEqual([r['index'] for r in items], [0, 1])
self.assertEqual([r['context'] for r in items], ['task:A', 'irq:7'])
self.assertEqual(sum(r['instructions'] for r in items), 2)
# 同一 block 第二次 I 已暖；不能因 context switch 冷啟動。
self.assertEqual(items[1]['cache']['l1i']['misses'], 0)
```

- [x] 執行 `.venv/bin/python -m unittest tests.unit.test_hotspot_events -v`，保存 RED。
- [x] 將 hotspot_report 內現有 model、ObservedCache、PC ownership、context coverage 與 raw-cost 檢查抽成 iterator。report 的公共 signature、排序與輸出 schema 不變：

```python
for event in iter_hotspot_events(rows, ranges, profile, contexts=contexts):
    key = (event['context'], event['role'], event['function_id'], event['pc'])
    add_counts(facts[key], event)
```

- [x] 加上 I/R/W、跨 line、write hit、非 cacheable、錯誤成本、缺 context 尾段與 unknown 的 fixture。重用現有 hotspot unit tests；逐欄比較重播 report 與保存的 C1 report，不只檢查 totals。
- [x] targeted unittest 與 Ruff 通過後 commit。原保存 C1 檔案不重新寫入。

## Task 2：來源驗證與完整分塊

介面：`build_event_run(root: Path, entry: dict, output: Path) -> dict` 使用 `load_hotspot_input`，拒絕既有 output；`validate_event_manifest(manifest: dict) -> None`；`load_event_chunk(root: Path, run_id: str, chunk_id: str) -> bytes` 只接受固定 catalog ID。

Schema `event-window-run-v1` 包含 identity/profile/source hashes、N 字串、owners/context dictionaries、totals、獨立 PSF clock/events/quality、chunks。chunk descriptor 包含 id/start/end/rows、gzip_sha256、json_sha256、compressed_bytes、uncompressed_bytes、totals；run manifest 使用 canonical JSON hash，catalog 指向該 hash。

每塊解壓後為 `{schema:'event-window-chunk-v1',start,end,columns,rows}`。columns 固定為 index,pc,address,size,operation,context_id,owner_id；接五個 cost keys；再按 l1i/l1d/l2 各 accesses,misses,compulsory,conflict,capacity。共 27 欄。operation 為 I/R/W，其餘數值含 dictionary ID 皆十進位字串。derived costs 不重複存：instructions=(op=='I')、memory_cycles=sum(costs)、service_ns=2*cycles、accounted_ns=service_ns+instructions。

- [x] RED unittest 建立 1025 列 fixture：

```python
self.assertEqual([(c['start'], c['end']) for c in manifest['chunks']],
                 [('0', '1024'), ('1024', '1025')])
self.assertEqual(sum(int(c['rows']) for c in manifest['chunks']), 1025)
```

- [x] 實作一遍 iterator streaming write；`gzip.compress(json_bytes, mtime=0)`；canonical UTF-8 JSON，固定 separators；保存全部 chunks 與 C1 totals/facts comparison receipt。2 MiB 解壓上限／chunk、1024 列上限，超出拒絕而不截斷。
- [x] 新 CLI：`PYTHONPATH=src .venv/bin/python tools/tcp/build_event_windows.py --workload A02 --output artifacts/local/c2a-pilot`。未指定 workload 才生成完整 40；output 必須新建且不在既有輸入 runset。
- [x] 測試錯 hash、重複／缺尾 chunk、非連續範圍、未知 owner、非法 op、負數／bool／非 canonical 數字；所有失敗留下明確結果，不發布 passed catalog。
- [x] PSF 使用同一 capture 的 trace.psf 與現有 parse_trace；保留 origin、ticks 字串、sequence 與 quality。測相同 timestamp、wrap、sequence gap、非零 origin；不能自創 cache timestamp。
- [x] `.venv/bin/python -m unittest tests.unit.test_event_window -v`、Ruff 通過後 commit。

## Task 3：Web／離線共用精確查詢

介面：`queryEventWindow(manifest, loadChunk, query, emit)` 為 async function。query={request_id,run_id,start,end,context,function_query,metric,event_offset,event_limit}；event_offset 為篩選後列的非負十進位字串、event_limit 為1–200整數；start/end 字串。loadChunk(descriptor) 回傳 gzip Uint8Array；emit 傳進度。回傳 totals、run_totals、function_rows、最多512個 bins、event_count、event_page、next_event_offset 與 quality，所有整數字串。event_page 最多200列，供點選 PC／source；完整 CSV 不受分頁限制。

- [x] Node RED 使用 3 筆已知 fixture 查 [1,3)，比較完整逐列 oracle；加入空區間及大數：

```js
assert.equal(result.totals.memory_cycles, '9007199254740993');
assert.equal(empty.event_count, '0');
assert.deepEqual(empty.function_rows, []);
```

- [x] 實作以 DecompressionStream('gzip') 逐塊解碼；累計輸出 bytes 到 2 MiB 即拒絕。解壓前後 hash、schema、descriptor/range/row count 全核對；不同 filters 重算不變更 cache 狀態，使用已保存逐列結果。
- [x] 分桶依完整所選 [start,end) 固定邊界；sum(bins) 等於篩選 totals。所有後端數值採 BigInt；表格 Top-N 不限制 CSV。
- [x] Worker protocol 為 query/progress/result/error/cancel，全部帶 request_id；main thread 忽略過期結果與錯誤。切 run 使用 terminate 而非等待舊工作完成，清除舊 PC／source selection。
- [x] 函式摘要 CSV 與逐事件 CSV 都覆蓋完整篩選區間。CSV 逐塊生成 Blob parts，匯出後 revoke URL；匯出取消釋放暫存。測 formula injection、quote/newline、空集合與大整數。
- [x] `npm --prefix web run test:unit` 通過後 commit。Node 測試使用相同 query engine，不另寫 production 計算分支。

## Task 4：事件區間 SVG 視圖

- [x] 新頁面提供 workload/run、context、function、metric、start/end 精確輸入；SVG histogram 可 drag/zoom，選取值轉成 index 整數並明示 [start,end)。事件密度不等於每秒發生率。
- [x] 分桶圖、函式表、成本拆解、選定事件 PC／source 明細使用同一 query result。主圖只顯示512 bins，tooltip 明列桶涵蓋範圍與原始列數。
- [x] PSF panel 使用獨立 ticks/time 軸，原順序與 unknown/gap 可見，兩軸不連動。提供「回到 C1 比較」連結，不實作兩個 run index 的逐點差值。
- [x] worker progress 與取消按鈕；零結果清除所有圖、table、detail。DecompressionStream／Worker 不可用則明確顯示不支援，不顯示空成功畫面。
- [x] 使用下列 request gate，加入舊失敗覆蓋新成功的 browser regression：

```js
if (message.request_id !== currentRequestId) return;
// applies equally to progress, result and error
```

- [x] `npm --prefix web run build`、Node tests 通過後 commit；真實拖曳、resize、排序與手機版面在 Task6 驗收。

## Task 5：API 與單檔 HTML

固定 routes：GET `/api/event-windows`、`/api/event-windows/{run_id}`、`/api/event-windows/{run_id}/chunks/{chunk_id}`。合法不存在 ID404、損壞資料503；manifest/hash 驗證後才供應 bytes；不接任意 filesystem path。

介面：`export_event_window_html(root: Path, workload: str, output: Path) -> dict`。HTML 內嵌該 workload 全部 gzip chunks 的 base64、manifests、PSF 與 worker JS；worker Blob URL 由同檔程式產生。CSP connect-src none、worker-src blob:，無 CDN。output exclusive create；匯出 receipt 保存每項來源與最終 HTML hashes。

- [x] RED API integration 測 200/404/503、encoded traversal、gzip bytes exact、gzip hash 正確但內容 malformed。
- [x] export RED 測 `</script>`／U+2028／惡意來源字串、缺 asset、重複 template anchor、既有 output 拒絕。
- [x] 實作前端統一 loadChunk：Web 固定 route，offline 從固定 ID 的內嵌 base64 解碼；兩者進相同 validator。無 window 全量解壓或保留全部 JSON rows。
- [x] `.venv/bin/python -m unittest tests.integration.test_event_window_api tests.unit.test_event_window_export -v`、Ruff、build 通過後 commit。

## Task 6：容量 gate、正式證據與發布

容量門檻是本計畫提出的本機驗收條件，不宣稱所有電腦可達：HTML 每 workload ≤95 MiB；初次 ready ≤25s；完整 run filter ≤5s；page JS heap ≤128 MiB（可量測時），測試 browser process tree 採樣峰值 RSS ≤640 MiB。browser RSS 只統計該測試 session 的 PID 子樹；無法可靠歸屬則記 unknown，不能寫 passed。超限保存失敗，不擴大正式批次；再根據量測修訂方案。

- [x] A02 pilot14 runs，保存 bytes、chunk counts、hashes、3次 load/filter/RSS 原始值、browser/OS/toolchain/commit。記憶體監測為該 session 的低頻採樣，列出間隔與可能漏掉瞬間峰值的限制。
- [x] harness 先 curl API/catalog/chunk/unknown 與 static routes，保存 status/bytes/hash。獨立 Python oracle 讀逐列資料驗證選區 totals、3C、CSV、跨塊切點及空區間。
- [x] agent-browser Web：精確 start/end、zoom/drag、context/filter、排序、欄寬、CSV、快速切 run、PSF gap、hover、mobile；每 mode 至少6張截圖。結束保存 close exit code；非0或仍有該 session PID 就中止後續 browser，不開下一個。
- [x] 停 server、curl證明不可連；才開 offline session，阻擋 HTTP/HTTPS，重做同一 oracle，resource list 不含網路。finally close 保存結果；測試故意失敗一次確認 close 路徑。
- [x] pilot全部通過才生成完整40份與8HTML，新目錄保存來源、逐列 chunks、manifest、容量數字及全部失敗／中間檔。每份與保存 C1 totals/facts 完整一致；正式A08補做最大run操作驗收。
- [x] code先commit；完整Python unittest、Ruff、Node、既有Playwright單worker與C1瀏覽器回歸依序執行。備份／復原歷史tracked測試產物，最終只保存新 evidence。
- [x] 獨立whole-change review，Important先修並重跑受影響測試；記錄所有延期問題。README加入流程、截圖、檔案表、事件序號語意、離線使用與C2b待辦。
- [ ] `verify_docs(Path.cwd())` 與 `git diff --check`；completion需列實測結果與source/tested commit。payload commit後正常push兩個repo，capture transport，核對remote SHA及clean status；不能把預期測試數寫成通過數。

## C2b 接續條件與計畫自我審閱

C2a 完成後另寫 C2b pilot 計畫：先查 QEMU callback 可取 clock 的位置，再定 request/applied anchors、PSF recorder anchor、MMIO序號與clock domains；其後才設定 A02 baseline/pbuf observer off/on 次數和誤差驗收。這項工作沒有被刪除，也未被本計畫當成已完成。

| 規格要求 | 覆蓋 |
|---|---|
| 連續cache／unknown／精確區間 | Tasks1–3 |
| 全量資料／低記憶體／可取消 | Tasks2–3、6 |
| PSF獨立軸／無虛構映射 | Tasks2、4 |
| Web／offline／完整CSV | Tasks3–6 |
| 一次一browser／close證據 | Task6 |
| screenshots／復原／review／push | Task6 |

未實測項目全部維持未勾選。執行前審閱本計畫；沿用原生逐項實作，最後獨立審查。

## 最終驗收補充

最新release-20261023覆蓋全部負向fixture、40-run full parity、8HTML容量、A02/A08 Web/offline oracle、C1/lifecycle/capability與close；Python328/Node25/PW11/Ruff。Web CSV依plan17改HTTP串流，Offline仍Blob；plan18只重用已逐列驗證的整塊totals，未減少資料/驗證。歷史失敗不作廢成成功；preflight意外browser的RSS則明確不可採認。待下方發布條件實際核對後才完成最後checkbox。
