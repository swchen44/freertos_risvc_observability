# T3c：guest pbuf chain holdout 計畫

延續 T3b 已列出的 guest 多段 pbuf 缺口。本輪維持 -Os、8/8/32 KiB、既有固定 TCP wire workload，變更 request 在記憶體中的表示法。

- [x] 起始 root/POC clean，基準 POC a896de7。
- [x] 新增 fragmented workload：IP+TCP headers 留在首段；callback payload chain 是 13 + 0 + 51 bytes。
- [x] 在 callback 讀取並記錄實際 len/tot_len，host oracle 必須確認兩個 request 的 chain 形狀；拒絕遺漏、單段冒充、長度／tot_len 錯誤。
- [x] baseline 與 pbuf variant，各 control/injection 三次；wire bytes 相同、PSF/timer/cost、buffer lifetime 與資源歸零。
- [x] linear 預設回歸，兩個 variant 各一組 control/injection；舊結果完全相等。
- [x] 統計 miss／3C、指令、完整與 stack window 成本、request_rx phase 指令、size；phase 可能含 IRQ，明列限制。
- [x] 文件、Mermaid、JSON/CSV、ELF/PSF/maps/raw traces 與重跑命令。
- [x] Ruff、完整 unittest、self-review、commit/push 證據。

Ruling: 選 pbuf 作下一個有限實驗，因為它在 T3b 改善最大而 chain correctness 仍只有 host tests。這裡的 fragmentation 是 pbuf 記憶體 chain，不是 IP fragmentation、TCP segmentation 或 NIC/DMA。

Ruling: 不修改預設，不修改 lwIP，不疊加 checksum/layout。PSF 延續現有排程事件；chain shape 保存在 session.json，沒有另造 PSF event 格式。沿用既有實驗分支並保持 artifacts 可還原；本 side conversation 不使用子代理，self-review。

執行：16 次正式 run、2 次 probe 通過；兩個 linear variant 的 audit SHA256 與 guest measurements 等於 T3b。分段 baseline 2,489,000 ns，pbuf 2,468,700 ns。正式比較中的 wire bytes 全部相同。

Ruling: 探索 probe 保留早期 source snapshot。正式程式將 receipt 輸出限制於 fragmented 分支，維持 linear 路徑；oracle 增加 strict integer 檢查，避免 bool/float 等值比較造成誤接受。

驗收：clean snapshot `c931bfb` 上 224/224 tests 通過，46.842 秒；Ruff、format 與文件 links 驗證通過。completion.json 保存 commit、log hash 與跨 T3b 封包比較。
