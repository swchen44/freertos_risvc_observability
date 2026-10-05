# 獨立 review 收據

Review 範圍：7b4e16d 起的 A 實作；source checkpoint 9292ae8，測試修正 8c1f8dd。

- Plugin digest 與 build contract 未核對：已修正，保存每組 plugin hash；不要求含 build UUID 的 Mach-O bytes 跨組完全相同。
- Source/artifact hash map 可省略必要 key：已要求核心 source、ELF/symbols/PSF/raw/session/封包。
- Dashboard hash 清單不完整仍顯示已核對：已要求全部 report/profile keys。
- 同 id 的不同 workload 可混用 baseline：已要求同組完整 workload 相同。
- Batch sibling logs 未 ignore 會使 clean gate 拒絕：已加入預檢與 unittest。
- macOS temp /var 與 /private/var：測試 root 改為 resolve；完整 251 tests 通過。

Reviewer 核對協定 seq/ACK、實際 chain receipt、原 IRQ guard、24 列 pin、16 組96次 report、Web/offline assertions 與報告數值，未發現其餘 Important source 問題。B/C 未被宣稱完成。
