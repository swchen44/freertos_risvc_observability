# 2026-11-03 空間盤點

使用者要求確認artifacts／runs是否有不需要的資料；目前只讀盤點，removed_files=0。

`audit.json`包含四組archive的逐檔比較、舊clone狀態、可重建物件cache數量及保留清單。四組共946個檔案全部相同，合計94,133,469 bytes。不是只用資料夾名稱或大小判斷已備份。

`inventory.json`核對本資料夾各檔SHA。詳細範圍在docs/storage-cleanup.md；等待使用者選擇保守清理、擴大封存清理或僅保留清單。
