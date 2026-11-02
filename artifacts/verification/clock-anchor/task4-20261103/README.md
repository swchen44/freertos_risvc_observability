# C2b Task 4：QEMU build、ABI與回歸

2026-11-03：第三個新隔離build完成，來源797d8c7c；10個ABI情境無失敗／timeout／skip，六份新舊binary的nano／burst／edges driver通過；完整352個Python測試通過。全庫Ruff check、本輪12個Python檔format通過；全庫format仍有10個既有舊檔未通過。

成功build-manifest在accepted資料夾；binary SHA、工具package與CLI版本分開記錄。Ninja distribution為1.13.2，實際CLI為1.13.2.git.kitware.jobserver-pipe-1。

保留三次build logs、patch版本、metadata修復命令與結果、失敗ABI timeout及macOS sample。sample直接顯示持鎖exit→plugin atexit→poc_clock_finish再次等鎖；修成解鎖後退出，並用missing-mmio反例證明直接拒絕而不掛住。第二次binary曾編譯成功但manifest版本檢查失敗，修復只重新產生metadata，沒有冒稱當時已通過ABI。

abi-accepted.tar.gz含10個情境的實際命令、PSF／oracle／console／exit；abi-failed.tar.gz保留前次120s失敗。clock-regressions.tar.gz保留六份driver的全部中間build、ELF、maps、原始PSF、命令與結果；一份driver包含多個guest測試，不能稱只有六次guest capture。

**驗證邊界：** 新ABI匯出、configure／CPU環境拒絕、native MMIO成功配對與原clock語意已驗證。新tagged request／applied的真guest因果關係尚待Task5／6，正式16-run仍為0；沒有PSF時間對齊或Dashboard新功能完成宣告。完整QEMU source／binary／離線依賴與分卷還原包由Task8交付，本checkpoint保留所有已做步驟與失敗證據。

歷史patch snapshots以.patch.gz逐byte壓縮，避免Git把合法diff空白context當成新原始碼的trailing whitespace；patch-snapshots.json保存解壓後大小與SHA，沒有刪除或修改原patch內容。
