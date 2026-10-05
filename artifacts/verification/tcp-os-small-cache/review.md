# T3b 自我 review

沒有獨立 reviewer；本 side conversation 禁止子代理。

- 原 cache 預設的 control/injection access stream hash、成本與 guest measurements 和前次 T3a 完全相同，見 default-regression.json。
- 新 geometry 用真正 C plugin 巨集和 Python profile 驗證；先觀察 2 個 native tests fail，再修正至 pass。
- 三種改法獨立編譯，compile commands 僅 -Os；三個 variant 各六次，baseline 六次，standard 兩次。來源與產物 hashes、封包 byte identity、PSF/timer、成本守恆通過。
- checksum v1 的 signed division 雖在簡化模型較快，仍以反組譯發現後排除；新增先紅後綠的 RV32 binary test。v1 原始碼與六次探索保存，正式採 v2。主機 correctness oracle 不等同 guest 全長度／對齊矩陣，報告明列界線。
- pbuf 沒有移除內容驗證、沒有額外 copy，仍接受 chain 與空段並拒絕錯誤長度；guest 本輪只驗證原本單 pbuf request。
- 3C 分類依每層實際查詢、同容量 FA LRU；跨 line 分開計數，寫入的 L1 misses 沒有用 L2 cost 倒推。
- layout 降 conflict 卻增加 capacity/L2 misses 的負面結果保留；沒有切換成預設。
- 分析僅量函式 self cost；stack window 含 preemption；沒有聲稱獨占 CPU usage 或硬體速度。
- 調整了程式碼後的地址與跨 line fetch 成本仍是混合因素。checksum v2 self cost 增加，報告未只挑總時間改善。
- 舊 references 不變。新 map/assembly/ELF/trace 都保留；v1 需使用 archived source；新 profile 可重跑，未宣稱完整離線 host toolchain 套件。
- 完整 suite：clean Git snapshot `b21d040`，220/220 通過；Ruff 及修改 Python 檔案 format 通過。見 completion.json 和 full-tests.log。

未做：實機 PMU、不同流量與多段 guest pbuf workload、三改法疊加、linker 多排列搜尋、Dashboard view。這些不阻擋本輪三個獨立實驗的結論。
