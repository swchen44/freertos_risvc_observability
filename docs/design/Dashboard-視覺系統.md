# Dashboard 視覺系統

延續已確認的 Tracealyzer 參照配置，面向排程除錯與證據比對。採用 frontend-design／web-design-engineer 的設計與視覺驗證流程；使用者已選 A 開始實作，沿用既有規格。

- 色彩：背景 #F2F5F9、面板 #FFFFFF、文字 #203449、主要操作 #155EB8、正常 #177C78、警示 #B96516；task 類別另用固定可區辨色票，unknown 灰色。
- 字體：Avenir Next／PingFang TC 作介面，SFMono-Regular 作原始offset／ticks；完全使用本機字體。正文16px，資料表14px，主標題24px。
- 版面：固定資訊層級。頂部input與案例；左filters；中間task timeline與CPU／timing視圖；下方events；右側detail。資料比裝飾優先，不加入行銷hero或假的範例數值。
- 間距：4px基本單位，控制項8px間距，區塊16px。面板8px圓角，input4px，主要靠空間和細邊界分組。
- 互動：操作後才更新chart，loading／error／empty清楚可辨。支援鍵盤filter、表格選取、可固定details；無自動播放。
- 暗色模式：同一資訊階層，維持contrast與task語意色；圖表依theme更新。
- 檢視前提：task share單位與分母、unknown、QEMU／unspecified時間模型、缺ISR重建限制都能看見。受控異常case通過顯示「預期重現異常」。

設計檢查：本工具的核心辨識是可連動的排程lane、原始offset和可驗證案例；不以通用數字卡取代工程資料。完整CSV數量與目前頁數同時顯示，避免誤會匯出範圍。
