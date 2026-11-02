# C2b Task 2：同 ELF SDK marker probe

2026-11-02：在固定 relative QEMU 上，mode0／mode1使用相同ELF，oracle回報0／5筆markers，PSF實際解析也為0／5筆；缺參數、過長、mode2與額外參數全部拒絕。這是development capability probe，沒有計入正式16-run。

Host C parser測試、兩個啟用的QEMU整合測試及完整342個Python測試通過，無skip。全庫Ruff check通過，新檔format通過；全庫format檢查仍有10個舊檔未通過，baseline-format-debt.json證明其與9c3c9aef完全相同，不宣稱全庫format成功。

`guest-probe.tar.gz`保存完整build中間檔、ELF／map、反組譯、symbols、實際PSF、oracle、console、拒絕路徑與命令。`probe-files.json`為解壓後相對guest-probe的逐檔SHA；已實際解壓至新的ignored資料夾並全部核對。內網可先驗inventory，再解壓核對逐檔；runtime-tests.json中的本機絕對路徑需依還原位置調整，重新執行須使用相符工具與來源。

Task3～8、新QEMU observer、因果對照、時間bounds、Web／offline接合尚未完成。沒有修改FreeRTOS kernel或SDK source。
