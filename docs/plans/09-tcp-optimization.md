# TCP 最佳化實作與驗證

承接使用者「go，實際案例實作驗證最佳化」。沿用 lwIP 2.2.1 作實驗，不代表正式產品 stack 定案。

## 本輪驗收

- [x] 真實 lwIP IPv4/TCP state machine：SYN/SYN-ACK/ACK、4 段 1460-byte payload、逐 byte 與 checksum oracle。
- [x] 三個配置：checksum2+copy baseline；checksum3+copy；checksum3+no-copy。一次改一個因素。
- [x] 每配置附 ACK 遺失後的 retransmission 正確性檢查，no-copy buffer 直到 ACK 都不修改。
- [x] 擷取 TX 區段的 guest instruction/data trace，補齊 call path；L1I 16KiB / L1D16KiB / unified L2 64KiB。
- [x] 模型明示假設：64-byte line、4-way、LRU、write allocate、non-inclusive，僅 tag/locality，沒有 writeback traffic / cycles。
- [x] 每個隔離 TX 區段 cold-start replay，ACK 與驗證在區段外；不把未追蹤區段的 cache 狀態推估成 warm-cache。
- [x] 每配置3次重跑；保存 ELF、PSF、trace、JSON、source/tool hashes。
- [x] 新 TCP Web 與離線 HTML，篩選、SVG、sortable table、CSV；curl integration、agent-browser E2E、截圖。
- [ ] unittest/Ruff、review、README、還原來源與 Git push。

## 決策紀錄

沿用 lwIP 是因為 checksum 元件與 pinned source 已驗證。in-memory peer 用正確封包經 ip4_input 驅動 stack；不把 packet peer 稱為第二個完整 TCP stack。這輪不模擬 NIC、DMA、真實 RTT 或重現 ESP32-C3 Wi-Fi 的 Mbps。

上游 raw API 於單一 FreeRTOS task、NO_SYS=1 執行。RTOS SDK 不需修改；lwIP sys_arch/socket integration 不在這個 deterministic protocol testcase 範圍。

## 執行紀錄

- Cache model 與 packet oracle 的新測試先出現缺模組失敗，再通過。缺少9份capture的資料集也已加入拒絕測試。
- 三配置真TCP與全部45個TX區段已跑通；final code 重新擷取至 v2。
- Review：無 Important/Critical；Minor 為 trace 與 rdinstret 每phase固定11指令的邊界差，保留既有量測定義並在報告說明。
- 判定：NIC/DMA/真實RTT、第二個完整peer與長期連線清理不在本輪測試內，不以此阻擋 bounded testcase。代價是結果無法直接代表實機吞吐量。
- UI沿用現有ECharts/Tabulator風格；Web與離線實際操作皆由agent-browser驗證，API由curl驗證。
