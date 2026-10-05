# -Os 小 Cache 最佳化實驗計畫與執行紀錄

需求：L1I/L1D 各 8 KiB、L2 32 KiB，依序驗證 TCP 程式排列、checksum 迴圈、pbuf 單次走訪。所有 guest C 保持 -Os。

## 設計與驗收

- 保留 16/16/64 KiB 預設；新增 8/8/32 KiB profile，其他 latency、line、ways、write policy、500 MHz cost conversion 不變。
- 原生 C plugin 必須與 Python 模型逐筆一致；小 cache 的 geometry 必須真的影響 native 模型。
- 四個獨立版本 baseline、layout、checksum、pbuf；每個版本 control/injection 各 3 次。改法不疊加。
- 一次完整 TCP 建連、兩輪 request/response、ACK、FIN；保留封包保存和所有驗證。封包內容必須逐 byte 一致，資源須釋放，PSF scheduler/clock 守恆驗證須通過。
- 比較 full-window、stack-window（含 preemption）、函式 self costs、I/D/L2 miss、code/data/BSS size；不把 harness 改善當 TCP stack 改善。
- 3C 分類：首次看到該層 line = compulsory；其他 miss 與同容量 fully associative LRU shadow 比較。此分類不推論真實硬體。
- checksum 加上長度、alignment、carry、odd-tail 的獨立 oracle 測試；pbuf 加上分段、空段及錯誤內容測試。
- 保存 ELF、PSF、trace gzip、map、symbols、manifest、JSON/CSV、assembly、驗證紀錄與重跑命令。
- Ruff、unit/integration suite、自我 review；本 side conversation 不使用子代理，沒有獨立 reviewer。

## 執行紀錄

- [x] 使用者確認 8/8/32 KiB 與三種改法。
- [x] 起始 root/POC working tree clean；POC 位於既有 feat/psf-lab 分支。
- [x] 小 cache native/Python 模型與分析測試。
- [x] 新 baseline 與舊 cache 對照。
- [x] layout 獨立實驗。
- [x] checksum 獨立實驗。
- [x] pbuf 獨立實驗。
- [ ] 結果報告、完整測試、Git 證據。

Ruling: 使用既有 POC 實驗分支，保留預設行為，以選項隔離本輪；不另切換目前 workspace 分支。縮小 cache 是壓力情境，不能將改善幅度推論成產品效能。

Ruling: checksum v1 的 signed 除法會被未校準的 instruction timing 掩蓋；保留六次探索與原始 source snapshot，正式比較改用無 div/rem 的 v2。三種改法不疊加，沒有獨立 reviewer。

執行：26 次正式 QEMU、6 次探索完成，所有封包相同；layout 變慢也保留。完整 suite 待 clean snapshot 後執行。
