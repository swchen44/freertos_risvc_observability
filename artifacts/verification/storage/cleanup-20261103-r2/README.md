# 保守清理執行收據

2026-11-03，使用者「OK, contine jobs」確認前次建議的保守範圍。每組archive重新逐檔比對後才移除副本；正式tracked artifacts／runs未刪，實際使用中的guest probe、relative及新QEMU binary hash皆重新核對。

receipt.json保存移除檔案數、logical bytes、實測可用空間前後及每類動作。觀測到的free-space delta可能包含同期間其他系統活動，不把它當成每個目錄的精確物理回收量。四組共946個trace／build副本有已push的tar備份，沒有刪唯一trace。

archive-verification.json列還原來源；tar root可先解壓到新目錄。舊clone沒有獨有worktree修改，只含可重建pyc；其舊Git歷史及先前移除的研究ZIP不重新打包上傳。removed-objects.json.gz保存3305個可重建物件的原大小／SHA；三組compdb與ninja/config metadata保存重編輸入，物件本體未封存，不宣稱bit-identical還原。

execution.py／execution.log.gz是本次一次性操作紀錄；不要當作可對任意目錄執行的清理工具。第一次前置檢查因舊Ninja路徑不同而停止，沒有刪除；第一次紀錄在同層cleanup-20261103。
