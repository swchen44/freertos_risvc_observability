# 查詢、統計與 CSV 規則

時間窗口為 `[start_ticks,end_ticks)`，ticks 為十進位字串，以 Python int 比較。`event_ids` 指平台事件類型的數字 ID；精確事件位置另外用 `event_id=0:offset`。

Task filter 匹配 actor；object filter 匹配被操作的物件；channel、type、literal search 共同限制 event table／signal。Search 不執行 regex。Null 時間不匹配指定時間窗口；品質入口仍提供未定時事件數。

Task lanes 依 task 選取顯示，但 CPU share 的分母與底層排程保留整個時間窗。Object／channel／文字 filters 不裁掉排程事件。Request 統計納入與窗口相交的完整 request，response 值保留完整 request 時長，不把裁切長度誤當 response。

排序支援 ticks、kind、object_id、sequence、offset；null 永遠置後，平手依 offset 升冪。API 每頁最多2000。CSV共用同一查詢，使用 `limit=None` 匯出所有結果，包含來源hash、schema、units與品質；特殊字串正確 quoting，公式字首加單引號並標記 spreadsheet_escaped，原始 JSON 不修改。

圖表最多2000個interval marks。超限改為每lane按區間起點分桶的密度概覽，顯示count與bin寬；這不是精確的running區間圖。超過2000 lanes需縮小選取，明確回報too_many_lanes。Metric仍由完整intervals計算；signals／requests畫面最多2000筆並提供total，原始event CSV不受圖表聚合限制。
