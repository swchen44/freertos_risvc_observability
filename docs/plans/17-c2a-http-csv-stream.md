# C2a Web CSV 串流實驗

目標仍為完整CSV、RSS640MiB、ready25s、filter5s。正式A08所有功能斷言通過；Web17.09/3.94s但RSS664624KiB，最高值在後續interaction而非只有export。Offline5.23/6.48s、RSS507008KiB，時間gate失敗。兩筆均保留，不宣稱leak已證明。

## 設計

- Web先用既有Worker完成同一篩選/全量驗證/統計，分析期間取消沿用request gate；不產生頁面CSV Blob。結果完成後交由同源HTTP attachment串流下載。原生下載開始後，由瀏覽器下載列取消，狀態明示分析與原生下載的邊界。
- 新GET events.csv endpoint：固定catalog ID、canonical start/end與既有context/function篩選；每塊仍核對hash/schema。CSV使用與JS相同QUOTE_ALL/CRLF、UTF-8與formula prefix規則，保持單一完整檔案及原欄位。
- server以約64KiB文字緩衝逐段yield；不將整份CSV留在頁面或server RAM。先驗首塊可在開始傳輸前回503；晚期損壞中斷串流，下載不得當完整成功。正式input不可變。
- Offline保留既有逐塊Blob流程，沒有Python/HTTP依賴；維持同一worker選區/BigInt計算。Web和offline CSV逐byte比對。
- Harness改用真實下載檔驗證interval/function CSV，避免攔截Blob專用假設；保存curl、完整CSV、取消、UI、RSS與close。容量測試期間不跑產生器/匯出器。

## 驗證順序

1. 先unittest測stream range/context/function、完整/空集合、Unicode/formula/大整數、首塊和晚期損壞；route 200/400/404/503及Content-Disposition。
2. Node test-first：Web Worker不累積CSV，Offline照舊；舊request不能觸發下載。完整Python/Node/Ruff/build與review。
3. 新Web A08 full對照，CSV hash對舊版與offline；不放寬gate。Offline A08的filter另保留profile/固定重測，未通過不宣告完成。
4. 若收益成立，重產8HTML並保留上一候選；A02/A08 Web/offline、其他6HTML容量、C1 offline、capability回歸；每次僅一session且finally close。
5. 更新plan14/README/evidence、push兩repo並核對SHA。任何失敗均保留，正式資料已生成不代表最終驗收。
