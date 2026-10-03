# M3：本機互動 Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 載入真正 PSF，提供 SVG 時間軸、共用 filters、可操作表格、案例比較與完整篩選 CSV。

**Architecture:** Query／CSV 共用資料語意；FastAPI 負責本機檔案、解析及查詢，ES modules 透過 DataSource 載入資料。UI依同一state更新各view，原始證據與品質隨時可追查。

**Tech Stack:** Python3.13、unittest、Ruff、FastAPI／Uvicorn／python-multipart／httpx；ECharts SVG、Tabulator、Playwright、ES modules、npm lock。

**Spec:** [設計規格](../design/PSF-Lab-設計規格.md)；[共同契約](data-contract.md)

## Global Constraints

- 前置為M2案例與分析契約通過；第一版服務綁`127.0.0.1`，不建立雲端部署。
- SVG renderer必須可驗證；不以Canvas偷換。套件本地保存並保留license。
- 窗口`[start,end)`；顯示filter不能改完整排程分母；CSV匯出所有符合結果，不只目前頁。
- PSF輸入，PDF僅研究來源；不增加PDF upload功能。
- Python unittest＋Ruff，前端另以Node test與真實瀏覽器驗收。
- 離線HTML只保留DataSource邊界；本版不宣稱離線匯出已完成。

## Review Focus

1. 空資料、time未知或大整數 → T1/T3/T4 tests，顯示限制不製造0%。
2. 篩選與排序後CSV漏掉其他頁 → T1/T4匯出250筆、page20對照完整集合。
3. 快速切換trace／filter時舊response蓋新畫面 → T3可控制Promise順序測試。
4. 任意檔名、HTML內容、資源超限 → T2/T3明確拒絕或當純文字顯示。
5. 大量SVG或聚合造成誤讀 → T4量DOM／延遲並標尺度，原始event仍可查。

### Task 1: P3-T1：共用Query與CSV，先交付可測函式

**Files**
- Create: `src/psf_lab/query.py`, `export.py`；`tests/unit/test_query.py`, `test_export.py`；`docs/query-semantics.md`。

**Interfaces**
- Consumes: M1 trace、M2 `analyze`、共同filter／sort契約。
- Produces: `query_events(trace, filters, sort, *, offset=0, limit=200)`、`query_view(trace, analysis, filters)`、`export_csv(trace, analysis, filters, sort, *, kind="events")`。

- [ ] **Step 1：以手工trace寫查詢／CSV測試。** 在test模組直接建立250個event，其ticks為0..249、payload名稱含逗號／引號／換行，actor分A/B。篩選`[10,240)`預期230筆，descending sort後首筆239；table只取20但CSV應230。

```python
import csv
import io
import unittest
from psf_lab.query import query_events
from psf_lab.export import export_csv

class QueryExportTests(unittest.TestCase):
    def test_csv_is_not_limited_to_table_page(self):
        trace = self.trace_250_events
        filters = {"start_ticks": "10", "end_ticks": "240"}
        sort = [{"field": "ticks", "direction": "desc"}]
        page = query_events(trace, filters, sort, offset=0, limit=20)
        rows = list(csv.DictReader(io.StringIO(export_csv(trace, {}, filters, sort))))
        self.assertEqual(page["total"], 230)
        self.assertEqual(len(page["rows"]), 20)
        self.assertEqual(len(rows), 230)
        self.assertEqual(rows[0]["ticks"], "239")
```

`setUp` 建上述250-event fixture；不經parser，expected固定手算。加入窗口縮到5..25時，A10→5、B20→15；隱藏B後分母仍20而非5。

- [ ] **Step 2：先執行 `python -m unittest tests.unit.test_query tests.unit.test_export -v`，確認未實作紅燈。**

- [ ] **Step 3：實作單一predicate與排序規則。** Ticks用Python int比較，不以字串排序。Task filter看`actor_id`，object filter看`object_id`，不得混用；缺時間event於有時間filter時排除但保留品質計數。

```python
# export.py 共用query，沒有另一套filter實作
rows = query_events(trace, filters, sort, limit=None)["rows"]
writer = csv.DictWriter(output, fieldnames=fieldnames)
writer.writeheader()
```

事件CSV欄位：source_sha256、schema_version、event_id、offset、ticks、time_unit、kind、actor_id、object_id、quality、message、spreadsheet_escaped。統計CSV含window／known／unknown／task_share與單位。字串以`= + - @`或tab／CR開頭時加前導單引號，`spreadsheet_escaped=true`；數值欄位由typed數值產生，不把合法負數統計當任意字串。JSON仍保留raw。

- [ ] **Step 4：補空資料、排序平手、null-last、巨大tick、非法sort、反向window、UTF-8與formula字串 tests，再跑Ruff。**

```sh
python -m unittest tests.unit.test_query tests.unit.test_export -v
ruff check .
ruff format --check .
git add src tests docs/query-semantics.md
git commit -m "feat: share trace filters and complete CSV exports"
```

- [ ] **Step 5：以M2 trace核對一個窗口的原始event IDs與CSV一致，保存查詢payload和結果hash。**

### Task 2: P3-T2：有上限的本機HTTP服務

**Files**
- Create: `src/psf_lab/server.py`, `store.py`, `tests/unit/test_store.py`, `tests/unit/test_server.py`, `requirements-runtime.lock`。
- Modify: `pyproject.toml`, `requirements-dev.lock`, `cli.py`；`docs/server-api.md`、README。

**Interfaces**
- Consumes: parse_trace、analyze、query／export、verified run manifests。
- Produces: `create_trace(store: Path, data: bytes, *, source_name: str) -> dict`；`create_app(store: Path) -> FastAPI`；完整路由見共同契約。

- [ ] **Step 1：寫server／store失敗測試。** `unittest.TestCase`用TemporaryDirectory和FastAPI TestClient。固定desktop檔案是真輸入，unit tests不啟動QEMU。

```python
with TestClient(create_app(Path(temp_dir))) as client:
    response = client.post("/api/traces", files={"file": ("demo.psf", data)})
    self.assertEqual(response.status_code, 201)
    trace_id = response.json()["trace_id"]
    self.assertEqual(client.get(f"/api/traces/{trace_id}").status_code, 200)
```

加入`../../escape.psf`檔名不產生store外檔案、空檔422、超16MiB413、超trace quota413、unknownID404、任意檔案path不被當作traceID。頻率0的可解析檔案依品質顯示，不在HTTP層編造秒數。

- [ ] **Step 2：固定依賴，跑紅燈。** Runtime：FastAPI、Uvicorn、python-multipart；tests：httpx。安裝實際相容版本後鎖定，不在此文件假造未查驗版本。

```sh
python -m pip install fastapi uvicorn python-multipart httpx
python -m unittest tests.unit.test_store tests.unit.test_server -v
```

- [ ] **Step 3：實作atomic store與路由。** UUID當ID，顯示用檔名先取basename／移除control chars，不作實體檔案路徑。暫存寫完解析再atomic rename；失敗移除暫存，原始故障檔若保存必須在有界quarantine並標記。Store最多20traces、每檔16MiB、每檔200k events、HTTP page最多2000，依共同契約可配置。

```python
app = FastAPI()
# UploadFile 分塊累積並在超限時即拒絕；不能先await file.read()全讀才檢查。
# run_in_threadpool 執行parse/analyze；semaphore限定同時一個upload。
```

保存source／JSON／analysis／metadata；查詢不重複parse。Server重新啟動仍可列出已完成trace。只允許loopback Host，預設不開CORS；回傳錯誤不含host路徑。外部URL不是合法輸入。不提供server端啟動任意命令或任意ELF。

Run registry只讀本機verified artifacts；必須驗manifest hash、case ID、trace hash與完整性才提供comparison。用明確run ID讀取，不提供任意filesystem path。

- [ ] **Step 4：測startup恢復、重複名稱、failed upload清理、兩次upload限制、所有query／export／comparison路由及schema錯誤；unit／Ruff通過後commit。**

```sh
python -m unittest tests.unit.test_store tests.unit.test_server -v
ruff check .
ruff format --check .
git add src tests pyproject.toml requirements-runtime.lock requirements-dev.lock docs/server-api.md README.md
git commit -m "feat: serve bounded local trace APIs"
python -m psf_lab serve --host 127.0.0.1 --port 8000
```

- [ ] **Step 5：保存OpenAPI JSON與一次真實PSF上傳／filter／CSV回應，不把API通過當瀏覽器驗收。**

### Task 3: P3-T3：SVG介面、互動狀態與表格

**Files**
- Create: `web/package.json`, `package-lock.json`, `build.mjs`, `index.html`, `src/styles.css`, `src/main.js`, `src/data-source.js`, `src/state.js`, `src/timeline.js`, `src/event-table.js`, `src/details.js`, `src/compare.js`。
- Create: `web/tests/state.test.mjs`, `data-source.test.mjs`, `precision.test.mjs`, `web/THIRD_PARTY_NOTICES.md`。
- Modify: `server.py` mount本地`web/dist`，新增`.gitignore`的`web/dist/`；`docs/dashboard-guide.md`。

**Interfaces**
- Consumes: HTTPDataSource／state／routes共同契約。
- Produces: `HTTPDataSource`、`createStore(initial)`、`mountTimeline(element,onWindowChange)`回`{render(view),dispose()}`、`mountEventTable(element,onSelect,onSort)`回`{render(page),dispose()}`；main負責串接，view不得自己解碼PSF。

- [ ] **Step 1：先寫JS測試。** `state.test.mjs`使用Node內建`node:test`／`assert`，測reset、filter不互相污染。DataSource以stub fetch測第一個請求晚回時不覆蓋新狀態；時間轉換以BigInt先減origin再檢查安全整數。

```javascript
import test from 'node:test';
import assert from 'node:assert/strict';
import { relativeTickNumber } from '../src/timeline.js';

test('subtract origin before converting large ticks', () => {
  assert.equal(relativeTickNumber('9007199254741002', '9007199254740992'), 10);
});
```

`relativeTickNumber(ticks,origin)`在timeline.js定義，差值超`Number.MAX_SAFE_INTEGER`丟RangeError，UI顯示需縮小窗口。對common JSON已相對origin的ticks，chart origin選窗口start避免大座標精度流失。

- [ ] **Step 2：固定套件、建立測試與本地bundle。** `npm install --save-exact echarts tabulator-tables`，dev使用esbuild與`@playwright/test`，記錄license及`package-lock.json`。`package.json` scripts固定`test:unit=node --test tests/*.test.mjs`、`build=node build.mjs`、`test:e2e=playwright test`。

```sh
npm --prefix web run test:unit
```

預期因缺模組失敗；安裝或Node相容性錯誤另外記錄。`build.mjs`以esbuild把`src/main.js`打包到`dist/assets/app.js`，複製index、CSS及本地資產，不引用CDN。

- [ ] **Step 3：實作view與共用state。** 套用研究wireframe：上方input／品質／case compare，左filter，中timeline，下table，右可固定details。單一trace工作區先完成，再加入pair compare；空狀態說明「載入PSF」，錯誤不顯示假圖。

```javascript
const chart = echarts.init(element, null, { renderer: 'svg' });
// table: movableColumns=true、resizable欄位；遠端排序回寫同一state.sort。
// tooltip與details使用textContent或安全formatter，來源文字不得成為HTML。
```

Timeline使用custom series畫interval lanes、overview brush控制query window、dataZoom／pointer操作。不要把時間縮放自行寫進沒有顯示的filter；顯示當前export窗口。PSF metadata／event ID／offset可在details回查。

表格遠端分頁、排序後重新查詢，移動欄位與調寬不改資料內容。raw/quality入口永遠可見。CSV按鈕用DataSource.export拿完整Blob；按鈕旁顯示`total`而非page length。

SVG工程初始預算：每次最多2,000個interval marks、overview每lane最多500bins，超出用明確density bins顯示count／range／quality，點選再縮小窗口。不聲稱預算已測得最佳；T4量測再調並記錄。原始表格不因聚合丟資料。

- [ ] **Step 4：加入快速filter race、名稱含HTML、null時間、缺資料品質、超大ticks與reset tests。** pair compare以request-relative窗口對齊，保留每份run自己origin；顯示工作量／clock／verdict與改善量，不能把兩份檔案絕對timestamp直接相減。

```sh
npm --prefix web run test:unit
npm --prefix web run build
python -m unittest tests.unit.test_server -v
ruff check .
ruff format --check .
git add web src tests docs/dashboard-guide.md .gitignore
git commit -m "feat: add interactive SVG trace workspace"
```

- [ ] **Step 5：用真實Queue與三組pair進行人工視覺檢查，保存全畫面與details截圖。** 檢查文字大小、欄位、橫向捲動、品質警告與長名稱；修改後重跑受影響tests。

### Task 4: P3-T4：瀏覽器、效能量測與交接

**Files**
- Create: `web/playwright.config.mjs`, `web/tests/e2e/dashboard.spec.mjs`, `src/psf_lab/benchmark.py`, `docs_validation.py`, `tests/unit/test_benchmark.py`, `test_docs_validation.py`。
- Create: `docs/benchmarks.md`, `docs/research-evidence.md`, `docs/handoff.md`。
- Modify: `cli.py`加benchmark／verify-docs；README、requirements、case-results與當日日誌。

**Interfaces**
- Consumes: M1/M2正式fixtures、M3完整服務。
- Produces: `benchmark(event_counts: list[int], output: Path) -> dict`與`verify_docs(root: Path) -> dict`，在對應module定義；結果存artifacts並附來源／環境。

- [ ] **Step 1：寫真實瀏覽器斷言和量測工具unit tests。** Playwright用localhost服務與固定PSF，不mock掉解析API；JS測試不只是檢查文字存在。

```javascript
await page.locator('[data-testid="psf-input"]').setInputFiles(fixturePath);
await expect(page.locator('[data-testid="timeline"] svg')).toBeVisible();
await expect(page.locator('[data-testid="timeline"] canvas')).toHaveCount(0);
const downloadPromise = page.waitForEvent('download');
await page.getByRole('button', { name: '匯出事件 CSV' }).click();
const download = await downloadPromise;
await download.saveAs(outputPath);
```

Fixture與outputPath由Playwright config的POC root和testInfo.outputPath產生。CSV用真正CSV parser讀，和API的`limit=None`等價集合及順序比較，不只數行；CSV本身可能有quoted換行。

Unit benchmark tests給空event list、invalid count、人工duration，驗證不輸出NaN／除0。Docs validation測故意broken link、hash mismatch、baseline不改寫。

- [ ] **Step 2：實作B01～B14瀏覽器驗收。** 對照 [Dashboard研究](../research/Dashboard功能與設計研究.md)，至少覆蓋：PSF載入、unsupported／partial、task/object/channel filters、time brush、zoom/pan/reset、hover固定details、排序、拖欄寬、拖欄位、全部filteredCSV、event/metric一致性、pair compare、資料精度、SVG renderer、空／大資料。拖動前後讀DOM欄位順序／width，不能只點按鈕算通過。

額外測快速A→B filters的過期response、檔名／事件含`<img onerror>`只作文字、頁面沒有外部network requests。以鍵盤或明確controls操作基本filter，圖表hover不是唯一查看方式。

- [ ] **Step 3：實作benchmark與文件驗證。** 1k／10k／100k固定synthetic fixture明確標synthetic，只測解析／呈現容量，不當作真實FreeRTOS案例。生成binary時僅用支援的事件集合，驗證實際event count；固定seed與hash，warmup1次、正式5次，保存各次與median／p95、peak RSS／tracemalloc各自量測範圍。`ru_maxrss` 依host平台換算並註明原單位，每組測試用新子程序避免前組high-water污染；tracemalloc只代表Python追蹤的配置，不當成整個程序RSS。

```python
# benchmark timing核心；資料生成不算入parse耗時
start = time.perf_counter_ns()
trace = parse_trace(data)
elapsed_ns = time.perf_counter_ns() - start
```

瀏覽器固定viewport與Chrome版本，記first render、filter-to-settled、DOM/SVG marks、table page size。回應完成以view render事件確認，不用任意sleep測速度。先量測再報數字；因目前無使用者效能門檻，不擅自將某個FPS當產品要求。瀏覽器單動作5秒timeout只是hang保護。

文件validator使用Markdown parser抽相對link／image、忽略外部URL；檢查新文件和snapshot hash，不把歷史verification.json的舊hash當成當前結果。

- [ ] **Step 4：執行全體驗收。** code先unit／lint並commit，乾淨來源再suite；正式suite結果先commit，再進後續需要clean的測試。每個工具以實際exit code記錄，不以skip補過。

```sh
python -m unittest discover -s tests/unit -t . -v
ruff check .
ruff format --check .
npm --prefix web ci
npm --prefix web run test:unit
npm --prefix web run build
npm --prefix web run test:e2e
python -m psf_lab benchmark --events 1000 10000 100000
python -m psf_lab verify-docs
```

首次`npx playwright install chromium`所需browser在執行時取得並記版本，已有可用Chrome也必須固定設定。Playwright啟動獨立port／store，測後關閉，不能連使用者其他既有服務。

- [ ] **Step 5：更新研究與操作文件，做整體code review後commit。** `docs/research-evidence.md`使用「主張→支持的case／run→觀察→適用條件→尚未證明」；Dashboard加操作截圖、API連結與SDK接法。README列一套可重跑命令、目前pass／fail、內網U01～U16。

```sh
git add src tests web docs README.md artifacts
# 先檢查staged範圍不含local暫存、憑證或機器私有設定
git diff --cached --check
git commit -m "test: verify dashboard interactions and publish POC evidence"
```

## M3 Gate

真PSF完整流程、七個配置／三組對照、Python與JS tests、Ruff、真實瀏覽器操作、filtered CSV、SVG與量測紀錄全部有最新證據。未實作offline／SMP／ring dump／cloud不算缺陷，但需保留範圍標籤。實體CPU／UART／IRQ／產品source研究繼續列U任務。

## 官方查核入口

[FastAPI file upload](https://fastapi.tiangolo.com/tutorial/request-files/)用於核對UploadFile與multipart；[ECharts SVG](https://echarts.apache.org/handbook/en/best-practices/canvas-vs-svg/)用於renderer選擇；[Tabulator文件](https://tabulator.info/docs/6.3)的實作API必須再對已鎖套件版本核對。
