# Cache replay 驗收證據

本輪最終 Python 119 tests、Node 5 tests、既有 Playwright 11 tests 通過；新增 agent-browser Web／offline 各一完整流程，包含真實 curl API、篩選、來源、CSV 數值／排序與 browser errors。離線流程在 Server 停止且網路封鎖下執行。

- `completion.json`：被測 commit、counts、截圖 hash、已知未完成範圍。
- `python-tests.log`／`node-tests.log`／`ruff.log`／`playwright.log`：最終結果。
- `server/`／`offline/`：agent-browser 實際命令、回應、CSV；server 另含 curl API 結果。
- `restore.json`：對應最終 archive SHA-256、1,172 個檔案、乾淨解壓、重播、模型 tests、六次重新模擬與結果一致性。
- `history/`：早期工作目錄錯誤的 unit log、v2 開發時 API，不作最終驗收。
- `precommit-python-tests.log`：尚未形成乾淨來源 commit 時，被既有 provenance guard 拒絕的紀錄。

完整 suite 曾因 Playwright 更新受 Git 管理的量測檔而再次被 clean-tree guard 擋下；保存並提交量測結果後，在 commit `5470a42ae551da883a9d57d74bec742da9cf887e` 重新跑 119 tests 通過。沒有放寬 provenance guard。
