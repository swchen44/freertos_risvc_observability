# C2b Task 3：原生 observer core

2026-11-02，來源87766959。6個unittest methods驅動真C核心，覆蓋正常FIFO、end後applied、observer-off不呼叫sink、marker-off仍計成本、三個marker phases、MMIO成對及27個拒絕案例。完整348個Python測試通過；全庫format的10個既有舊檔仍列未通過。

保留缺module RED、未使用欄位錯誤RED、GREEN與完整回歸logs；native-cases.tar.gz包含實際cc命令、來源hash、host binaries、所有stdout／stderr與exit。Host binary只供相同host複查，其他host須由repo的C原始碼重編。

這是原生狀態機與wire互通證據；尚未接QEMU adapter，也沒有新clock-alignment或正式TCP pilot成果。
