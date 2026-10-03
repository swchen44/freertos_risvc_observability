# 第一版資料與命令契約

狀態：計畫中的介面，尚未實作。所有路徑相對 POC 根目錄。

## 檔案責任

| 模組 | 唯一主要責任 |
|---|---|
| `src/psf_lab/doctor.py`、`provenance.py` | 工具檢查、來源 lock、run 可重現性 |
| `src/psf_lab/parser/binary.py` | 有邊界的 binary framing |
| `src/psf_lab/parser/semantic.py`、`schemas/` | 平台派送、物件與 user event 解碼 |
| `src/psf_lab/analysis.py` | 執行區間、request 指標與有效窗口 |
| `src/psf_lab/runner.py`、`harness.py` | 真實模擬程序控制、獨立 assertions |
| `src/psf_lab/query.py`、`export.py` | 共用 filters、穩定排序、完整 CSV |
| `src/psf_lab/server.py`、`store.py` | 本機 HTTP、隔離檔案儲存與資源上限 |
| `src/psf_lab/cli.py` | 組合已有函式，不另寫解碼／統計規則 |
| `web/src/` | DataSource、互動狀態、SVG、table、details |

Python API 第一版回傳 JSON-compatible `dict`，欄位由以下契約與 schema tests 約束；避免計畫中引用尚未定義的 model class。

## Python 介面

```python
# doctor.py
inspect_tools(required: tuple[str, ...]) -> dict
# provenance.py
verify_sources(root: Path, lock: dict) -> dict
require_clean_tree(root: Path) -> str  # returns full commit, raises RuntimeError
# parser/binary.py
parse_binary(data: bytes, *, source_name: str = "memory.psf", strict: bool = True) -> dict
# parser/semantic.py
parse_trace(data: bytes, *, source_name: str = "memory.psf", strict: bool = True) -> dict
# analysis.py
analyze(trace: dict) -> dict
# runner.py
run_case(root: Path, case_id: str, *, timeout_s: float = 30.0) -> Path
# harness.py
check_case(case: dict, trace: dict, oracle: dict) -> dict
compare_cases(pair_id: str, runs: list[dict]) -> dict
# query.py
query_events(trace: dict, filters: dict, sort: list[dict], *, offset: int = 0, limit: int | None = 200) -> dict
query_view(trace: dict, analysis: dict, filters: dict) -> dict
# export.py
export_csv(trace: dict, analysis: dict, filters: dict, sort: list[dict], *, kind: str = "events") -> str
# store.py
create_trace(store: Path, data: bytes, *, source_name: str) -> dict
# server.py
create_app(store: Path) -> FastAPI
```

`Path` 為 `pathlib.Path`，FastAPI 為套件 class。`parse_binary`／`parse_trace` 對不支援格式、header／metadata 損壞丟 `ParseError(code: str, offset: int, message: str)`，定義在 `parser/errors.py`。Partial 模式只容許已確定 framing 的完整 prefix；不能掃 magic 猜恢復。

## Trace JSON v1

| 欄位 | 固定語意 |
|---|---|
| `schema_version` | 整數 `1` |
| `source` | `name`、`sha256`、`byte_length` |
| `platform` | `format_version`、`platform_id`、`name`、`schema`、`word_bytes`、`endianness`、`core_count` |
| `clock` | `frequency_hz` 十進位字串、`tick_hz` 整數、`type`、`origin_ticks` 字串或 null、`time_model` |
| `objects` | `object_id`、十六進位 `address`、`epoch`、`kind`、`name`、建立／刪除 offset |
| `events` | 下表事件列表 |
| `quality` | `status` 為 `valid`／`partial`／`unsupported`、`issues`、`capture_complete` 為 true／false／null |
| `derived` | `parse_trace` 初始 `{}`；由 `analyze` 回傳內容另存或填入 |

`valid` 表示支援範圍內結構可解析，不保證捕捉完整；獨立 complete marker／oracle 核對後才把 `capture_complete` 設 true。只有來源檔案無 metadata 時，`time_model="unspecified"`；run manifest 指明 `qemu-icount` 才可標記。

每個 event 固定有：`event_id="0:<byte_offset>"`、`offset`、`id`、`sequence`、`core`、`timestamp_raw`、`ticks` 字串或 null、`payload_hex`、`kind`、`actor_id` 或 null、`object_id` 或 null、`fields`、`quality`。`fields` 依 schema 解碼；實驗 user event 再加 `case_id`、`phase`、`message_id` 或 `request_id`。所有原始 payload 不變。`actor_id` 是事件當時已知的執行 task，`object_id` 是操作的 queue／mutex／task 等目標；無足夠排程證據時 actor_id=null。`ticks` 是相對 `clock.origin_ticks` 的延伸時間，原始32-bit值保留在 timestamp_raw。

`parse_binary` 用同一 envelope，但 `objects=[]`、`kind="raw"`、`fields={}`；原始 entry table 留 `raw_metadata.entries`。`parse_trace` 在此之上派送語意。未知合法事件用 `kind="unknown"`，不丟 payload。

`analyze` 回傳：`intervals`、`requests`、`metrics`、`quality`。Interval 有 `object_id`、`start_ticks`、`end_ticks`、`state`、`quality`；state 第一版為 `running` 或 `unknown`。ready／blocked 只有匹配已確認 hook 時才加入，不由「沒 running」直接推導。Metrics 同時提供 `window_ticks`、`known_ticks`、`unknown_ticks`、`task_share`；不把 task share 命名為含 ISR 的整體 CPU utilization。

## Filters 與 HTTP

```json
{"start_ticks":"0","end_ticks":"100000","task_ids":[],"object_ids":[],"channels":[],"event_ids":[],"search":""}
```

Ticks 是相對 trace origin、單位為 recorder counter 的十進位整數字串；`start_ticks`／`end_ticks` 可省略表示整個可用窗口。時間窗口 `[start,end)`，起點不得大於等於終點。時間有效事件才匹配時間 filter；無時間資料有獨立品質入口。空陣列不限制。`task_ids` 匹配 actor_id，`object_ids` 匹配 object_id；兩者以AND結合。大小寫不敏感的 literal substring 搜尋名稱與已解碼訊息，不執行 regex。

Sort 是 `[{"field":"ticks","direction":"asc"}]`，允許 `ticks`／`kind`／`object_id`／`sequence`／`offset`，最後以 offset 升冪打破平手。Null 永遠在後。`query_events` 回 `{total, rows}`；`limit=None` 為全部結果，只有內部 CSV 使用。`query_view` 回窗口裁切 intervals、以完整排程計算的 metrics、品質、顯示聚合尺度。

| 方法與路徑 | 請求／回應 |
|---|---|
| `POST /api/traces` | multipart `file`，回 201 `{trace_id, source, quality}` |
| `GET /api/traces/{id}` | source、platform、clock、objects、quality |
| `POST /api/traces/{id}/events` | `{filters,sort,offset,limit}` → `{total,rows}` |
| `POST /api/traces/{id}/view` | `{filters}` → query_view 結果 |
| `POST /api/traces/{id}/export` | `{filters,sort,kind}` → UTF-8 CSV 附件 |
| `GET /api/runs` | 已核對的本機 run 摘要、案例、品質與 artifacts ID；不暴露任意路徑 |
| `POST /api/comparisons` | `{pair_id,run_ids}` → compare_cases 結果；只接受已核對 run |
| `GET /` | 本地靜態 Dashboard |

上傳結果即使 partial 也需顯示警告；unsupported／header 損壞回 422。不存在 ID 回 404；不合法查詢回 422；超出資源上限回 413。所有錯誤為 `{error:{code,message,offset}}`，不包含 host 敏感路徑。

初始工程上限：PSF 16 MiB、200,000 events、20 traces／store、單次 event query 2,000 rows；超限明確拒絕，不能靜默截掉。上限可用啟動參數調整，需記錄在測試環境；不代表已測得此容量效能。第一版解析同步但一次只處理一個 upload，放 worker thread 不阻塞 HTTP event loop。無限量背景解析不在範圍內。

## Case、oracle 與 CLI

Case JSON：`case_id`、`expected_outcome`、`required_event_families`、`parameters`、`assertions`、`guest_timeout_ticks`。Case name 僅允許 plan 定義的七種加 `clock_probe`；不得直接拼進 shell command。

Oracle JSON：`case_id`、`complete`、`outcome`、`sent_ids`、`received_ids`、`phases`、`requests`、`transport_ok`、`mtime_hz`、`tick_hz`。不適用列表填空陣列；`complete` 僅在 guest 正常收尾時 true。PSF user events 與 oracle 由同一應用動作記錄，但 oracle 不呼叫 decoder，也不依 recorder event ID 決定業務結果。

```sh
python -m psf_lab doctor
python -m psf_lab decode INPUT.psf --output trace.json
python -m psf_lab analyze trace.json --output analysis.json
python -m psf_lab run queue_baseline
python -m psf_lab check RUN_DIRECTORY
python -m psf_lab suite --repeat 3
python -m psf_lab serve --host 127.0.0.1 --port 8000
python -m psf_lab benchmark --events 1000 10000 100000
python -m psf_lab verify-docs
```

CLI exit 0＝已完成且符合命令預期；1＝case assertion 不符；2＝設定／輸入錯誤；3＝證據不足；4＝模擬 crash／host timeout／capture 失敗。`doctor` 缺工具回 2。`suite` 結合七個配置各三次與三組 pair assertions；任一缺工具／skip／未完成都非零。CLI 逐 task 擴充，不先交付全部空 handler。

## 前端介面

`HTTPDataSource` methods：`upload(file)`、`metadata(id)`、`events(id,request)`、`view(id,request)`、`export(id,request)`、`runs()`、`compare(request)`，全部回 Promise；export 回 Blob。未來 offline adapter 實作相同介面，不在第一版實作。

`relativeTickNumber(ticks,origin)` 使用BigInt相減再轉安全Number，定義於timeline.js；數值超限回RangeError。

`createStore(initial)` 回 `{getState,setState,subscribe}`；state 是 `{traceId,filters,sort,selection,viewport,comparison}`。Selection 存 event_id；filters 是後端契約。`viewport` 只影響畫面聚合，不能偷偷成為 CSV filter。請求以遞增序號或 AbortController 排除過期 response。
