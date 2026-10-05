# T4 Review

獨立 reviewer `timing_dashboard_review` 讀取 loader、API、JS/HTML、offline exporter、tests 與 plan；結論無 findings。Reviewer 自行驗證 6/6 Python、2/2 新 Node tests 與相關檔案 Ruff。

主代理另驗證 curl、agent-browser Web/離線與既有 UI。窄螢幕測試抓到 grid min-content 造成 SVG overflow，已加 min-width:0 並重驗通過。

初次全測試在未 commit 的工作目錄執行，3 個正式 firmware integration 被 clean-tree guard 拒絕；保留 precommit-tests.log。完成記錄必須以後續 clean commit 的全測試為準。

原始 T3b/T3c capture、comparison 與 profile 未修改；新 manifest 固定來源 hash。新頁排除舊 geometry standard；不宣稱 CPU pipeline、task-exclusive、PMU 或 execution hotspots。

補充 hover 驗收：agent-browser find/hover 不會替畫面外 SVG 捲動，先 scrollIntoView 再 hover 後，分母與3C tooltip 正確顯示；調整驗收腳本，沒有改動產品 tooltip。
