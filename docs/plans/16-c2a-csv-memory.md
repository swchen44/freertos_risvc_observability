# C2a CSV 記憶體續作

沿用已核准 plan14/15；RSS640MiB／ready25s／filter5s與完整CSV不變。起點7332782，Web全功能通過但完整CSV階段650.36MiB超限，離線536.05MiB通過。

1. 診斷harness加可選CSV階段標記、wall-clock RSS timestamps。只記數量／heap／Blob大小，不保存額外CSV副本。診斷run不取代未插樁驗收。
2. 比對CSV分塊接收、worker result、Blob URL與download時間點及RSS。先定位峰值，不能把page heap當worker或全程序記憶體。
3. 根據證據選單一修正實驗；候選是UTF-8可轉移buffer，避免跨thread文字複製。若沒有量測收益則不保留。禁止裁切事件、改精度、強制GC或放寬門檻。
4. Node測Unicode／CSV原bytes、轉移後sender detachment與request identity；完整A02 CSV逐byte與上版相符；維持取消／stale-result gate。
5. Web與offline各自重新跑完整agent-browser操作與curl；一次一session、finally close。保留失敗與中間檔、screenshots、review、README與push receipt。
6. 全部pilot容量通過後才擴大40／8HTML。C2b仍未開始。

## 對照結果與下一步

診斷原版RSS445248KiB，UTF-8 transfer452560KiB，未證明收益。完整74118680-byte CSV SHA相同。依第3點不保留產品改動，實驗原始碼與測試移到證據目錄；產品回到7332782。診斷heap值為粗粒度回報，不能推論allocation或leak。

預先固定3次原版完整Web重驗，逐次close，任何超限均保留並停止擴大。全部通過才確認當前pilot gate；歷史650.36MiB仍保留，不能稱已修正洩漏。離線原版既有3次與完整操作驗收仍有效，最終正式候選另驗。
