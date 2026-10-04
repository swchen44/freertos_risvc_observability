# FreeRTOS／RISC-V PSF POC


**新增 Cache 相對最佳化實驗：**[操作與內網還原](docs/cache-replay.md) · [研究報告：cache 效率與 PSF 擴充](docs/research/Cache效率與PSF擴充.md) · [離線 Cache Dashboard](artifacts/offline/cache-comparison.html)。本機服務開啟 `/cache.html`，原 PSF 頁也提供「Cache 比較」入口。


**這裡是後續實驗與文件的主要入口，使用獨立 Git 管理。**

目前已固定工具鏈、完成 PSF parser，並在 RISC-V QEMU 跑通 FreeRTOS Queue／clock probe。正式 harness 與七配置三次重跑已通過；本機 Dashboard 已通過瀏覽器驗收；獨立 review 的 3 個 Important 已修正，最後全套回歸驗證通過。建立日期：2026-10-03。

## 離線 HTML 與實際畫面

已新增 Python → 單檔離線 HTML；觀看時不需 Python、Server 或網路。新 PSF 需重新匯出。跨機重現依 2B 整項暫緩。

```sh
npm --prefix web ci
npm --prefix web run build
.venv/bin/python -m psf_lab export-html fixtures/desktop/trace.psf --output artifacts/local/report.html
```

雙擊 `report.html` 即可篩選、拖曳時間軸、排序／調整表格、查看詳情與匯出 CSV。[可下載 Queue 示範](artifacts/offline/queue-baseline.html)；GitHub 上請下載原始檔後開啟。

[本輪完成紀錄](artifacts/verification/offline/completion.json)｜[完整 20 張操作圖解與模式比較](docs/offline-guide.md)｜[實作計畫](docs/plans/05-offline-portability-documentation.md)｜[curl 驗證](artifacts/verification/offline/http-tests.log)｜[agent-browser Server](artifacts/verification/offline/browser-server.log)｜[agent-browser 離線](artifacts/verification/offline/browser-offline.log)

**Web Server：載入 Queue PSF。** 時間軸與 CPU share 呈現執行區間，右側保留來源與品質。

![Web Server Queue 全覽](artifacts/screenshots/server/02-overview.png)

**單檔離線 HTML：同一份 Queue 資料。** 右上角標明離線模式，來源與品質保留。這不是圖片報告，仍可操作。

![離線 HTML Queue 全覽](artifacts/screenshots/offline/02-overview.png)

**篩選 consumer 與時間窗。** Task 選取不會錯改 CPU 分母。

![離線篩選與時間窗](artifacts/screenshots/offline/03-filter-window.png)

**滑鼠拖曳時間軸。** 拖曳後窗口、統計與事件表同步更新。

![離線滑鼠拖曳窗口](artifacts/screenshots/offline/04-timeline-brush.png)

**排序、欄寬與 CSV。** 畫面每頁 20 筆，但 CSV 實測輸出全部 281 筆。

![離線排序與欄寬](artifacts/screenshots/offline/05-sort-resize.png)

**Server：Logger 干擾／改善案例。** 比較含獨立 oracle；單 trace 離線版不內嵌案例 registry。

![Server Logger 案例比較](artifacts/screenshots/server/09-comparison.png)

## 文件入口

1. [需求與進度](docs/requirements.md)：所有原需求、新需求、完成與未完成項目。
2. [設計規格](docs/design/PSF-Lab-設計規格.md)：PSF → Python → 互動 HTML／SVG＋JavaScript。
3. [實作計畫](docs/plans/README.md)：13 個任務、測試與完成條件。
4. [過程日誌](docs/journal/2026-10-03.md)：本次做了什麼、依據、限制與下一步。

## 目錄用途

| 目錄 | 保存內容 |
|---|---|
| `docs/` | 需求、研究、架構、操作與交接文件 |
| `docs/design/`、`docs/plans/` | 設計規格與後續實作計畫 |
| `docs/decisions/` | 已確認選擇、理由與影響 |
| `docs/reviews/` | review 發現、修正與尚未驗證事項 |
| `docs/journal/` | 按日期記錄過程、命令、結果與下一步 |
| `docs/research/` | 本輪 PSF、模擬與 Dashboard 研究 |
| `firmware/` | FreeRTOS＋TraceRecorder 接合與 RISC-V firmware |
| `src/` | Python parser、分析、harness 與本機服務 |
| `web/` | JavaScript、HTML、CSS 與 SVG 視圖 |
| `cases/` | 正常／異常案例定義及獨立預期 |
| `tests/` | unittest、整合與瀏覽器驗收 |
| `tools/` | toolchain-lock.json、瀏覽器測試服務；CLI 在 src/psf_lab/cli.py |
| `scripts/` | 保留用途說明，目前沒有完整安裝自動化 |
| `fixtures/` | 固定輸入、來源與 SHA-256 |
| `runs/` | 每次實驗的設定、版本、log、PSF、JSON、判定 |
| `artifacts/` | ELF、map、圖表、CSV、驗證摘要等產物 |
| `references/` | 既有研究、PDF、SDK 與來源 manifest |

空目錄內的 README 說明未來用途，不能視為功能已實作。

## 找回實驗過程

每次實驗使用唯一 `run_id`，遵循 [執行紀錄規範](runs/README.md)。成功與失敗都保留；重跑使用新 ID，不能覆寫前次證據。每份結果記錄程式 commit、dirty 狀態、工具版本、時鐘、案例、命令及檔案 hash。

可用 `git log --oneline --all` 看變更，`git log -- docs/journal` 找工作紀錄。大型暫存放 `runs/local/`、`artifacts/local/`；完成判斷所需的小型證據移到正式 run 目錄並 commit。

## 已確認方向與驗收

- 輸入為 **PSF**；「PDF 轉 HTML」是筆誤，PDF 僅為研究參考。
- 原先先做 **本機 Python 服務**；現在已新增單 trace 離線 HTML。
- 互動圖表使用 SVG＋JavaScript，包含 filters、hover、時間軸、可排序／調整欄位的表格與完整篩選結果 CSV。
- Python 必須有 `unittest`、`ruff check`、`ruff format --check`；瀏覽器操作另做驗收。
- 不購買 Tracealyzer；QEMU 的虛擬時間不能當成實體 CPU overhead。

GitHub 發布採同一 repository 的 `poc-history` 分支保留完整 POC 歷史，`main` 的 `poc/` submodule 固定到 POC commit。先前知識庫的 push 是另一項已完成工作。

## 參考來源

[原始完整研究](references/baseline/research/FreeRTOS-RISC-V-Observability-研究報告.md)、[原始需求／過程](references/baseline/README.md)、[內部 AI 接續任務](references/baseline/research/內部AI-接續研究任務.md)。快照含原始來源與圖片，完整性見 [manifest](references/manifest.json)。快照維持歷史內容；目前狀態以此 README 與 `docs/` 為準。

新增研究：[L1／L2 cache、bus latency 與 CPU task usage](docs/research/Cache-Bus與CPU使用率.md)，包含 QEMU 的能力邊界、PSF 計算公式、Tracealyzer 功能對照與待驗證項目。

[案例教學與21份原始證據](docs/case-results.md)：Queue、Logger干擾、priority inversion／inheritance、deadlock／ordered locks。

## 啟動與重跑

先依 [環境設定](docs/setup.md) 建 Python 3.13 環境。Dashboard 不需啟動 QEMU；內含已收集的 PSF 可直接分析。

```sh
.venv/bin/python -m pip install -e . -r requirements-dev.lock
npm --prefix web ci
npm --prefix web run build
.venv/bin/python -m psf_lab serve
```

開啟 http://127.0.0.1:8000 ，操作見 [Dashboard 指南與截圖](docs/dashboard-guide.md)。API 見 [server-api](docs/server-api.md)，本機啟動後可讀 `/openapi.json`。

```sh
.venv/bin/python -m unittest discover -s tests/unit -t . -v
.venv/bin/ruff check .
.venv/bin/ruff format --check .
npm --prefix web run test:unit
npm --prefix web exec -- playwright install chromium
npm --prefix web run test:e2e
.venv/bin/python -m psf_lab benchmark --events 1000 10000 100000
.venv/bin/python -m psf_lab verify-docs
```

瀏覽器測試自行啟動 port 8766 與暫存 store，測後關閉。測試資料中的三份 synthetic PSF 隨 `artifacts/benchmarks` 保存，benchmark 可重新產生。容量測試結果不當成板端 SDK 成本。

重新編譯／收集需要 [固定工具鏈](tools/toolchain-lock.json) 與乾淨 Git。先保存修改，再執行：

```sh
.venv/bin/python -m psf_lab run queue_baseline
# 完成後先將本次 runs 證據 commit，才能開始下一次正式 capture。
.venv/bin/python -m psf_lab suite --repeat 3
```

單次 run 輸出新目錄；`check <run目錄>` 重驗 PSF／oracle／case，`decode <trace.psf> --output <trace.json>` 與 `analyze <trace.json> --output <analysis.json>` 可分別使用。不要覆寫既有正式 run。

## 研究與後續交接

- [主張與實驗證據](docs/research-evidence.md)：每項結論的支持案例、條件與尚未證明事項。
- [容量與效能量測](docs/benchmarks.md)：parser 時間／memory、瀏覽器載入／篩選／SVG 數量。
- [內網 AI 接續工作](docs/handoff.md)：U01～U16 的目的、產品完成條件與可直接使用的 POC 成果。
- [Cache 相對最佳化計畫](docs/plans/04-cache-relative-optimization.md)：M1～M3 之後執行；比較 L1I／L1D／L2 miss、指令數、size 與模型成本。接受非 cycle-accurate，保留假設與敏感度分析。

本版提供單 trace 離線 HTML；仍不提供完整 ISR／SMP、任意 PSF schema、實體 UART 或 cloud。SDK CPU 百分比、每事件 cycles、最差 IRQ 與產品 Flash／RAM 仍需內網／硬體量測。


## M1～M3 歷史驗證紀錄（2026-10-03）

- Python unit tests：90／90；integration tests：6／6；Node tests：5／5。
- Playwright：11／11；SVG、drag／pan／zoom、filters、完整 CSV、欄寬／欄位拖曳、品質與來源競爭均有實際操作。
- Ruff check／format、native transport tests、npm ci／build 通過。
- 最終正式 suite：[21 次 capture 與 9 組比較](runs/suite-20261003T085652Z-2732b56355/index.json)，source commit `a3802c5`，全部 pass。
- 文件／baseline 驗證：[docs.json](artifacts/verification/docs.json)；422 份原始檔案 hash 保持不變。
- [Python log](artifacts/verification/unit-tests.log)、[integration log](artifacts/verification/integration-tests.log)、[browser log](artifacts/verification/browser-tests.log)。

Starlette TestClient 有建議移到 httpx2 的 deprecation warning，現行測試通過；尚未將測試 client 遷移。瀏覽器與 parser 容量限制見 benchmarks，產品 U01～U16 維持未結清。


獨立 [整體 code review 與修正](docs/reviews/final-code-review.md) 及 [實作決策／代價](docs/reviews/implementation-decisions.md) 已保存。沒有延後的功能性 Minor。


最終修正 commit `5f84e53`：完整 Python 測試 96／96 通過，包含 90 unit＋6 integration；[完整 log](artifacts/verification/all-tests-final.log)。11／11 browser 與 5／5 Node tests 亦通過。先前本機交付保留 `feat/psf-lab`；本次 GitHub 發布將相同歷史送至 `poc-history`，不改寫舊實驗 commit。


## 從 GitHub 取得與首次上傳驗證（歷史）

完整研究入口：[GitHub main](https://github.com/swchen44/freertos_risvc_observability)。在該 repo 根目錄執行 `git submodule update --init poc` 後進入 `poc`；修改前可用 `git switch -c my-poc-experiment` 建立自己的分支。

Dashboard 可先使用既有 PSF，不需要 FreeRTOS toolchain。重新模擬須依 [setup](docs/setup.md) 安裝工具並適配／提交本機 toolchain lock，原 lock 包含已驗證機器的絕對路徑和 binary hash。

本次上傳前重新執行 96 Python tests 和 11 browser tests；[checklist 與來源 commit](artifacts/verification/github-upload/checklist.json)、[Python log](artifacts/verification/github-upload/python-tests.log)、[browser log](artifacts/verification/github-upload/browser-tests.log) 可複查。M1～M3 共 13 tasks 的步驟勾選已核對，該次上傳時 offline 尚未實作；目前已提供單 trace 離線 HTML。M4／U01～U16 與跨機重現仍待後續。

重要程式入口：`src/psf_lab/cli.py`、`parser/semantic.py`、`analysis.py`、`runner.py`、`harness.py`、`server.py`；前端 `web/src/main.js`；韌體 `firmware/config/FreeRTOSConfig.h`、`firmware/app/main.c`、`firmware/app/cases/`。文件集中於 `docs/`，驗證 logs 在 `artifacts/verification/`，正式 capture 與原始 PSF 在 `runs/`。


## 2026-10-04 接續工作

- 修正 Dashboard 指南仍稱離線 HTML 尚未提供的舊描述。
- M4.1 已建置官方 cache plugin 並在 RV32 Queue baseline 實跑；正常結束、oracle 相同，取得 L1I／L1D／L2 統計。見 [原始證據與限制](artifacts/verification/cache/README.md)。
- [M4 計畫](docs/plans/04-cache-relative-optimization.md) 已拆成六階段。下一步先校驗地址語意、cache oracle 與 read/write 邊界，再做 A/B 和 Dashboard。
- 產品 U01～U16 仍待內網 source／硬體；跨機工作維持暫緩。此 smoke 不代表已完成產品 cache 模型或效能最佳化。


## Cache 實驗與內網還原

相同 checksum 的 row／column 各三次 RV32 實跑，共 18 組模型結果。4 KiB L1D 下，連續存取由 8,192 降至 512 misses，byte utilization 由 6.25% 升至 100%；這是 data-region 模型內比較。

![本機 Cache Dashboard](artifacts/screenshots/cache/server-01-overview.png)

![離線 Cache Dashboard](artifacts/screenshots/cache/offline-01-overview.png)

- [篩選、容量比較、來源與更多截圖](docs/cache-replay.md)
- [source 還原包](artifacts/restore/cache-replay-source.tar.gz)／[archive SHA-256](artifacts/restore/cache-replay-source.json)：含 FreeRTOS、SDK、plugin source、六次原始 captures 與 viewer；未含 host toolchain 執行檔。已在同機乾淨目錄核對逐檔 hash、重播並重新建置模擬。
- [正式原始 evidence](runs/cache-relative-v3/)：每輪 PSF、ELF、map、oracle、access CSV、manifest；`suite.json` 保存擷取來源，`analysis-receipt.json` 保存分析來源。
- [驗證紀錄](artifacts/verification/cache-replay/)：unittest、Ruff、curl、agent-browser、CSV、restore。

仍待完成：instruction cache、function hot/cold、AoS／SoA、GEMM tiling、逐 task／PSF 時間同步，以及真機 PMU 接入。原始 PSF 未被修改成自訂 binary 格式；目前用 sidecar hash 關聯。
