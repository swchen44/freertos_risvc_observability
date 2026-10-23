# C2a 時間門檻續作 · 2026-10-23

沿用已核准C2a計畫；RSS640MiB、ready25s、filter5s不變。

1. 先用CLI profile分離API成本，再重跑單一browser容量。保留原始量測，profile本身有額外成本，不能當HTTP延遲。
2. profile已證明：20個chunk請求共1.565s，其中每次重讀、解析、驗證同一manifest共0.534s；chunk解碼共1.000s，uint大量呼叫re.fullmatch。先改善這兩個有證據的位置。
3. 用內容bytes作key，只保留一份已驗證manifest；每個請求仍重新讀取catalog與manifest、核對SHA。公開讀取回傳獨立副本，防止呼叫端污染cache。測同長度檔案修改、錯hash、更新catalog後的malformed資料、呼叫端修改與容量上限。
4. 預編譯原有整數regex，保留完全相同的canonical格式規則。重跑同一profile、unittest/Ruff及API curl，再跑agent-browser一次一個、finally close。
5. 先驗A02容量，未通過不擴大正式40。通過後續依plan14完成負向fixtures、正式40／8HTML、最大A08與回歸。C2b仍另立計畫。

禁止用mtime判定資料可信、跳過hash/schema驗證、放寬時間門檻或改寫舊失敗收據。

JS profile：A02完整430324列3.894s；add的多個遞迴frame合計為主要self-samples，empty另占156 samples。採固定schema迭代／literal初始化，減少每列Object.keys／fromEntries配置；保持BigInt與所有validator。以前後完整query結果hash、既有Node與新增負向fixtures核對。
