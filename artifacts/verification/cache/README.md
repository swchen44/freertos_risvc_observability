# M4.1 cache plugin 載入實驗

2026-10-04：QEMU 11.1.2／plugin API 7，macOS Apple Silicon。官方 `v11.1.2/contrib/plugins/cache.c` 配本機 header 建置成功，RV32 FreeRTOS Queue baseline 正常結束，exit code 0。使用 `l2=on`，其餘 cache 參數為該 source 預設值；這不是產品平台設定。

| 統計 | accesses | misses |
|---|---:|---:|
| L1D | 9,119,873 | 2,894 |
| L1I | 16,312,105 | 228 |
| L2 | 3,122 | 2,810 |

- L2 accesses = L1D misses + L1I misses：3,122 = 2,894 + 228。
- guest `oracle.json` 與原 Queue baseline 完全相同。
- [manifest](plugin-smoke.json) 記錄 source／plugin／QEMU／ELF SHA-256、compiler、build 與 QEMU 命令；[原始統計](cache-stats.log)、[建置 log](plugin-build.log)、[stderr](qemu-plugin.stderr) 可複查。
- 本機 source、dylib、PSF 在 `artifacts/local/cache/`，不提交平台二進位檔；PSF hash 保存在 manifest。重跑請使用獨立目錄，避免覆寫原 run。

## 已知限制

這是單次載入 smoke，沒有完成手算 oracle、cache A/B 或硬體校驗。

1. 統計包含啟動、清零、recorder 及整段 firmware 工作，不能當成指定 task 或區間結果。
2. 上游 source 在 system emulation 用 `qemu_plugin_insn_haddr()` 當 instruction cache 與 miss table 位址；raw log 的地址不能直接丟給 guest ELF 的 addr2line。後續需釐清 host／guest address 空間與 L2 共用位址一致性，才能宣稱模型已校驗。
3. Data callback 使用 guest physical address 並排除 I/O；本次輸出沒有分開 read／write miss，也不能宣稱涵蓋 DMA、writeback 或 bus contention。
4. 沒有把 miss penalty 回灌至 guest 時間，PSF 排程時間不能解讀成 cache timing 改善。
5. L2 miss rate 分母是 L2 accesses，不是所有 CPU 記憶體存取；不要把 90.0064% 說成整體 miss rate。

來源：[固定版本 cache.c](https://github.com/qemu/qemu/blob/v11.1.2/contrib/plugins/cache.c)、[官方 plugin 說明](https://www.qemu.org/docs/master/about/emulation.html)。
