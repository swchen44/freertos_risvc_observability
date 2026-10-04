# T2b 執行紀錄

- 範圍：獨立 QEMU v9.2.0 baseline／clock setter 候選、既有 0／1／5 ms guest probe。先完成此門檻，再決定 cache 與 dashboard 接合。
- Ruling：依使用者要求，所有實驗位於 poc；第三方來源／build 放忽略的 `.tools/qemu-time-control`，patch、命令、hash、原始 evidence 放受 Git 管理的資料夾。全域 QEMU 不變。
- Ruling：此側邊對話禁止 subagent，改為本人逐項 review，不宣稱獨立 reviewer。
- 已知失敗：安裝版 QEMU 11.1.2 的 1／5 ms 注入逾時。需先在 v9.2.0 重現，才能歸因 patch 效果。

- API 4 首次編譯失敗，修正 callback 相容後 API 4／7 均通過。
- configure 首次因相對 Ninja 路徑失敗；改絕對路徑後成功，保存兩份 log。
- Baseline：0 ns 3 次完成，正延遲 6 次逾時。
- Setter-only：全部完成，5 ms 僅前進約 1 ms；oracle 拒絕。
- Timer fallback：九次完成，全部驗收通過；5 ms 前進 5 ticks，observer 醒來。
- Ruling：本次完成固定時間注入門檻；連續注入／WFI／IRQ 邊界另列待辦，不能提前宣稱逐次 cache stall 完成。
