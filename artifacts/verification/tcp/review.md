# TCP checksum 獨立 review

Reviewer：tcp_checksum_review，2026-10-04。

- Important 1：共享 build 目錄切換 toolchain 可能沿用舊 object。已改成每次全新 output 下的獨立 OUT，manifest 保存 build command。
- Important 2：來源 provenance 遺漏 kernel、SDK、startup 與 linker script。已讀 GCC .d 保存實際相依檔雜湊，另外保存 linker script 與 repo/kernel revisions。
- 複查：45 個 .d 可解析；119 個 dependency hashes 與 9 次執行產物全部吻合。沒有新增 Important/Critical。
- 本輪 scope 是 checksum component，非完整 TCP 吞吐量、硬體 cycles 或 cache 模擬。
