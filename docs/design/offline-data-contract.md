# 離線資料契約 v1

Python `export-html INPUT.psf --output OUTPUT.html` 在匯出時執行既有 parser／analysis。單一 HTML 內嵌 metadata、完整 events／intervals／requests、Python Unicode casefold table、CSS 與 IIFE JavaScript。source SHA-256 與品質欄位保留。限制與 Server 一致：輸入最多 16 MiB，支援目前兩個 PSF v14 schema；未知／部分資料以既有品質語意呈現。

瀏覽器不解析新 PSF；新資料需再次匯出。離線資料來源實作 metadata、traces、events、view、export、latest；runs 回空列表。upload、runPSF、compare 不是此模式能力，相關 controls 隱藏，頁尾說明改用本機 Server。單檔只含一個 trace，不宣稱獨立 oracle 驗證或成對案例比較；Server 保留三組比較。

query／metrics 規則與 [query semantics](../query-semantics.md) 相同。ticks 以 BigInt 計算，只有繪圖比例／秒／統計平均轉 Number。事件搜尋使用匯出時的完整 Python Unicode casefold 對照；排序字串依 Unicode code point、null 置後。CSV 輸出全部符合列，不受分頁或 2,000 marks 限制；浮點文字的等價表示（例如 1 與 1.0）可不同，數值與其他欄位須相同。

以 Python query/CSV 作跨語言 regression oracle；七個真實 PSF 與手建邊界資料另含大 ticks、Unicode、負 Counter、unknown、空 trace、density、signals truncation。既有 hand-count metrics 測試繼續保留，不用移植兩份相同演算法作為唯一正確性證明。

HTML 將輸入 JSON 的 `<` 轉為 Unicode escape，禁止網路與外部資源的 CSP；資料文字使用 textContent／plaintext。截圖與數值驗證分開保存，PNG 不代表資料正確。
