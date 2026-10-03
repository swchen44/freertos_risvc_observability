# 首次 GitHub 上傳：todo／checklist 與證據稽核（歷史）

更新：2026-10-04 已完成單 trace 離線 HTML、curl／agent-browser 驗證與 20 張操作截圖，最新證據見根 README。跨機重現依使用者 2B 暫緩。以下測試數與 receipt 是首次發布的歷史證據。

日期：2026-10-03。目標 repository：<https://github.com/swchen44/freertos_risvc_observability>。

**M1～M3 完成並通過重驗；整個產品研究路線尚未全部完成。** 上傳採 `main` 研究入口＋`poc` submodule，POC 全歷史保存於同 repo 的 `poc-history` 分支，避免改寫實驗 manifest 中的來源 commit。

## 已完成項目與複查入口

下列 GitHub 連結指向 POC 分支內的證據；本機初始化 `poc/` 後，同一路徑位於 `poc/` 下。每份原始 run 的來源、PSF／oracle／ELF／map hash 保留，不用本次測試 log 覆蓋舊實驗。

| 檢查 | 結果 | 可複查證據 |
|---|---|---|
| M1／M2／M3 計畫任務 | 5＋4＋4＝13 tasks，實際步驟無未勾選 | [checklist.json](https://github.com/swchen44/freertos_risvc_observability/blob/poc-history/artifacts/verification/github-upload/checklist.json)：每份計畫 SHA-256、task／checkbox 數、受測 commit |
| Python unit＋integration | 本次重跑 96／96，含 90 unit＋6 integration | [python-tests.log](https://github.com/swchen44/freertos_risvc_observability/blob/poc-history/artifacts/verification/github-upload/python-tests.log) |
| Playwright 真實介面 | 本次重跑 11／11，包含 SVG、拖曳／縮放、filters、CSV、race、截取提示 | [browser-tests.log](https://github.com/swchen44/freertos_risvc_observability/blob/poc-history/artifacts/verification/github-upload/browser-tests.log)、[完整 JSON](https://github.com/swchen44/freertos_risvc_observability/blob/poc-history/artifacts/verification/github-upload/browser-results.json) |
| JavaScript unit tests | 5／5 | [js-tests.log](https://github.com/swchen44/freertos_risvc_observability/blob/poc-history/artifacts/verification/github-upload/js-tests.log) |
| Ruff | check／format 通過 | [ruff.log](https://github.com/swchen44/freertos_risvc_observability/blob/poc-history/artifacts/verification/github-upload/ruff.log) |
| 既有正式 PSF | 兩輪共 42 份 capture 重新 decode／check 全數 pass；兩輪各 9 組 comparison 的已保存結果均 pass | [run-recheck.json](https://github.com/swchen44/freertos_risvc_observability/blob/poc-history/artifacts/verification/github-upload/run-recheck.json)；本次沒有重跑另一套 42 次模擬 |
| 文件與基準 | POC 相對連結與 422 個 baseline hash 重驗 | [docs.json](https://github.com/swchen44/freertos_risvc_observability/blob/poc-history/artifacts/verification/github-upload/docs.json) |
| 獨立 review 的 3 項 Important | 已修正且有 RED→GREEN 證據 | [final-code-review.md](https://github.com/swchen44/freertos_risvc_observability/blob/poc-history/docs/reviews/final-code-review.md) |
| 根 README | 補資料夾用途、重要檔案、文件位置、POC 下載／執行／複查 | [README](../README.md) |
| 原研究的需求、PDF、圖文與試算 | 由既有 verify_report.py 再檢查；詳細值見輸出 | [research/verification.json](verification.json)；此腳本保留原 host 測量暫存依賴，不能當新機器已重測 CPU 成本 |

## 沒有勾成完成的工作

| 待辦 | 為什麼尚未完成 | 後續完成條件 |
|---|---|---|
| M4 cache 相對最佳化 | 使用者明確要求排後面，本輪只有計畫 | 驗 cache plugin、相同工作量 A/B、L1I／L1D／L2 miss、指令數／size、模型假設與校驗 |
| 離線 HTML | **2026-10-04 已完成單 trace 匯出** | agent-browser 已在 Server 停止／瀏覽器 offline 下驗證；新 PSF 仍需 Python 重新匯出 |
| U01～U16 產品任務 | POC 控制案例不能取代產品 source／BSP／實體平台 | 依 [內部 AI 任務](內部AI-接續研究任務.md) 的個別完成條件 |
| 組織內部網路部署 | 上傳 GitHub 不等於部署內網 | 依組織環境部署、權限與實際檔案存取驗收 |
| 相同工具鏈跨機重現 | 原 lock 是 macOS arm64 的路徑／hash，工具 archive 不上傳 | 安裝、驗 checksum、依環境更新並提交 lock；正式 run 必須 clean |

README 原有兩個未勾選事項「放到組織內部網路」、「與產品原始碼比較」維持未勾選。計畫開頭的 `` `- [ ]` `` 是語法示例，不是另一個待辦。SDK 上游程式中的 TODO/FIXME 是上游註解，本次沒有把它們統一改成已完成。

## 發布內容與保存邊界

- `main`：研究文件、PDF、圖片、下載 SDK／demo 快照、既有 LICENSE、POC gitlink。
- `poc-history`：完整 POC commit 歷史、原始 PSF／JSON／oracle、ELF／map、tests、Dashboard 與文件。
- FreeRTOS 保持上游 submodule pin；不另外複製整個上游歷史到研究根目錄。
- 本機 `.venv`、`.tools`、`node_modules`、暫存 build／preview store 與巢狀 `.git` 不上傳。
- 研究 ZIP 已依要求從 `main` 的全部歷史移除，並加入 `.gitignore`；SDK 原有的其他 ZIP 不受影響。
- 原檔 license／notices 保留；GitHub 原有 LICENSE 不覆蓋第三方各自條款。

## 如何獨立複查

```sh
git clone https://github.com/swchen44/freertos_risvc_observability.git
cd freertos_risvc_observability
git submodule update --init poc
git submodule status poc
cd poc
git log --oneline -8
# 依 README 建 Python 環境後：
.venv/bin/python -m psf_lab verify-docs
.venv/bin/python -m unittest discover -s tests/unit -t . -v
```

要重驗單次正式 capture：`.venv/bin/python -m psf_lab check runs/<suite>/<run_id>`。這會解碼 raw PSF、核對 oracle／case 與 hash；查看舊 JSON 或已保存的 pass 字樣不能取代這個步驟。

GitHub 上傳後已重新 clone，研究區 920 個檔案、POC 1,202 個檔案的 SHA-256 全部一致；422 個基準檔、219 個文件連結與 42 份 PSF 重驗通過。下載版本另外執行 90 項 Python unit tests，全數通過（沿用本機 Python dependencies，沒有重建跨機工具鏈）。

可複查：[上傳與下載核對紀錄](github-publish-receipt.json)、[下載版本測試 log](measurements/github-clone-unit.txt)。receipt 明確記錄受驗證的 snapshot commit；本身於核對後另行提交。

## ZIP 歷史清理

上傳驗證完成後，使用者要求移除研究 ZIP 的全部 Git 歷史。使用 `git filter-repo` 精確移除該路徑，再以 `--force-with-lease` 更新 `main`。`poc-history` 不含此檔案，保持原 commit。原上傳 receipt 保留當時事實；其中 main commit 與檔案數是清理前的歷史紀錄，版本對照見 [清理紀錄](zip-removal.json)。GitHub 快取與別人已下載的副本不在此次可保證清除範圍。
