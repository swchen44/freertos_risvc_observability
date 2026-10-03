# FreeRTOS／RISC-V PSF POC

**這裡是後續實驗與文件的主要入口，使用獨立 Git 管理。**

目前完成目錄、研究快照、需求與決策紀錄及設計草案；尚未建置 QEMU firmware、正式 parser、harness 或 Dashboard。建立日期：2026-10-03。

## 先看這三份

1. [需求與進度](docs/requirements.md)：所有原需求、新需求、完成與未完成項目。
2. [設計規格](docs/design/PSF-Lab-設計規格.md)：PSF → Python → 互動 HTML／SVG＋JavaScript。
3. [過程日誌](docs/journal/2026-10-03.md)：本次做了什麼、依據、限制與下一步。

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
| `scripts/` | 取得依賴、建置、執行與驗證工具 |
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
- 先做 **本機 Python 服務**，之後才擴充離線 HTML。
- 互動圖表使用 SVG＋JavaScript，包含 filters、hover、時間軸、可排序／調整欄位的表格與完整篩選結果 CSV。
- Python 必須有 `unittest`、`ruff check`、`ruff format --check`；瀏覽器操作另做驗收。
- 不購買 Tracealyzer；QEMU 的虛擬時間不能當成實體 CPU overhead。

目前只有本地 Git repository，未設定 remote、未 push 此 POC。先前知識庫的 push 是另一項已完成工作。

## 參考來源

[原始完整研究](references/baseline/research/FreeRTOS-RISC-V-Observability-研究報告.md)、[原始需求／過程](references/baseline/README.md)、[內部 AI 接續任務](references/baseline/research/內部AI-接續研究任務.md)。快照含原始來源與圖片，完整性見 [manifest](references/manifest.json)。快照維持歷史內容；目前狀態以此 README 與 `docs/` 為準。
