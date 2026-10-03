# 本機服務 API

```sh
.venv/bin/python -m pip install -e . -r requirements-dev.lock
.venv/bin/python -m psf_lab serve --host 127.0.0.1 --port 8000
```

僅允許loopback host／origin，未開CORS。資料預設存 `artifacts/local/store`；啟動後已有traces可再次查詢。OpenAPI：`http://127.0.0.1:8000/openapi.json`。第一版單process；API不執行任何上傳程式或ELF。

| 路徑 | 用途 |
|---|---|
| POST `/api/traces` | multipart file上傳；回201與trace_id、source、quality |
| GET `/api/traces` | 已完成的本機trace metadata |
| GET `/api/traces/{id}` | schema／clock／objects／quality |
| POST `/api/traces/{id}/events` | filters、sort、offset、limit，回total／rows |
| POST `/api/traces/{id}/view` | filters，回intervals、task share／trend、requests、signals、quality |
| POST `/api/traces/{id}/export` | filters、sort、kind=events或metrics，完整CSV附件 |
| GET `/api/runs` | 已驗manifest與raw evidence的案例清單 |
| GET `/api/runs/{id}/psf` | 僅下載已驗證run的PSF，供UI載入 |
| POST `/api/comparisons` | pair_id與兩個run_ids；回verdict／assertions與分析資料 |

查詢規則見 [Query semantics](query-semantics.md)。HTTP每頁最多2000、PSF最多16MiB／200000 events、每store最多20 traces。`create_app`可設定byte／trace上限；parser硬上限仍生效。上傳整個multipart request另限PSF上限＋64KiB，避免先無限制spool再拒絕；解析在worker thread一次一個upload。

檔名只作顯示，不作路徑；UUID隔離。先完整解析到暫存目錄，再atomic rename。失敗清除本次暫存。重複名稱建立不同trace。錯誤為 `{error:{code,message,offset}}`：422輸入、404不存在、413容量、400非本機Host；不回傳host檔案路徑。

Run registry在首次存取建立唯讀清單，核對PSF、oracle、case、所有manifest檔案hash與harness；使用時再驗manifest／核心證據。服務運行中新增suite須重新啟動載入。比較以各run自己的origin與request ID，禁止拿兩份絕對timestamp直接相減。

套件版本见runtime／dev lock。此版本Starlette仍支援httpx TestClient但發出轉用httpx2的deprecation warning；目前tests有實際通過，未隱藏warning。
