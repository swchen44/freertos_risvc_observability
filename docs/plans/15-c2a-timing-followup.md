# C2a 時間門檻續作 · 2026-10-23

沿用已核准C2a計畫；RSS640MiB、ready25s、filter5s不變。

1. 先用CLI profile分離API成本，再重跑單一browser容量。保留原始量測，profile本身有額外成本，不能當HTTP延遲。
2. profile已證明：20個chunk請求共1.565s，其中每次重讀、解析、驗證同一manifest共0.534s；chunk解碼共1.000s，uint大量呼叫re.fullmatch。先改善這兩個有證據的位置。
3. 用內容bytes作key，只保留一份已驗證manifest；每個請求仍重新讀取catalog與manifest、核對SHA。公開讀取回傳獨立副本，防止呼叫端污染cache。測同長度檔案修改、錯hash、更新catalog後的malformed資料、呼叫端修改與容量上限。
4. 預編譯原有整數regex，保留完全相同的canonical格式規則。重跑同一profile、unittest/Ruff及API curl，再跑agent-browser一次一個、finally close。
5. 先驗A02容量，未通過不擴大正式40。通過後續依plan14完成負向fixtures、正式40／8HTML、最大A08與回歸。C2b仍另立計畫。

禁止用mtime判定資料可信、跳過hash/schema驗證、放寬時間門檻或改寫舊失敗收據。

JS profile：A02完整430324列3.894s；add的多個遞迴frame合計為主要self-samples，empty另占156 samples。採固定schema迭代／literal初始化，減少每列Object.keys／fromEntries配置；保持BigInt與所有validator。以前後完整query結果hash、既有Node與新增負向fixtures核對。

第二輪profile：固定schema後，number仍占370個samples，regex另66；三次Web重算5.29／3.05／3.64s，保留第一次失敗。只對已知canonical字串"0"與"1"直接回傳BigInt常數，其他值仍走原validator；用完整query byte equality與既有非法數字fixture驗證，再重跑容量。

## 最新驗收邊界

16e0cbc 的 Web 三次 ready/filter 均過時間門檻，完整操作也通過；完整 CSV 匯出階段 RSS 665968 KiB（650.36 MiB）超過640，故不生成正式40。此次功能結果不是整體驗收通過。

下一個實驗先量測 CSV 各階段：worker 文字產生、postMessage 傳遞、主執行緒 Blob parts、最終下載；保留現行輸出逐 byte 基準及取消生命週期。若證據支持，才比較可轉移 UTF-8 buffer 或分段產生的記憶體成本。不能減少列數、降低欄位精度、放寬門檻或強制使用者手動 GC。先完成 Web／offline 最終候選的對照，再決定修正。
