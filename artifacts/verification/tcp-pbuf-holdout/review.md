# T3c 自我 review

沒有獨立 reviewer；本 side conversation 不使用子代理。

- 變更限於新增 fragmented workload、callback shape receipt、oracle／analysis，以及文件；T3b pbuf 最佳化演算法本身未修改。
- fragment_request 將 104-byte 單一 IP packet 配成 53/0/51-byte pbuf，保留 headers 在首段；pbuf_cat 串接，舊暫存 pbuf 釋放；最後 lwIP pbuf_free 釋放 chain。兩版六個資源計數歸零。
- Callback 記錄真實 len/tot_len，不使用 command-line 值冒充觀測。兩版都支付觀測成本；receipt strict integer 拒絕 bool/float，已先紅後綠。
- 沒有改 TCP wire packets；16 次正式結果的 25 個封包逐 byte 相同。沒有用 chain 總長度正確代替內容驗證。
- 原型 probe 來源與正式版有差異，保留兩個 source snapshot，verify_probe.py 驗證 hash。正式版保持 linear 原輸出路徑。
- 兩個 linear regression 的 control/injection audit（含 trace SHA256）和 guest measurements 等於 T3b；新功能沒有改變已觀測的預設表現。
- 分段兩版各 control/injection 三次；hash repeatable，PSF/timer/cost conservation 通過。baseline 誤差 +43ns、pbuf -45ns。
- 分段三個函式 self instructions 的差等於全 trace 差 3992；memory costs 另受全域地址與 cache state 影響，不宣稱是純函式時間。
- D/L2 misses 下降而 rate 略升是分母變化，報告沒有隱藏。48.31% 是 request_rx 指令差，不是整體速度或 CPU loading。
- No NIC/DMA、IP fragmentation、跨 pbuf headers、多 connection、任意 request sizes。新 workload 的分配／複製屬 harness，不是推薦產品 zero-copy RX 作法。
- 所有 guest C build commands 為 -Os；references/ 與 third_party/ 未修改；JSON/CSV/maps/ELF/PSF/raw traces 均保存。
- 完整 suite 在 clean snapshot `c931bfb` 執行，224/224 通過，46.842 秒；Ruff 與 format 通過。見 full-tests.log 和 completion.json。
