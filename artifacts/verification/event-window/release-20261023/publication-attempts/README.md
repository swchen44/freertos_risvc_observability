# 發布過程與傳輸邊界

兩次整批推送未完成，遠端仍停在7332782；第二次保存的分類為HTTP408。dry-run通過，全部新增blob皆小於100MiB；這些都不等於實際發布成功。

分批fast-forward後，小批次及150,686,252 bytes原始blobs的579ceaf批次成功；3a85228批次以原設定回408，遠端仍停579ceaf。本機離線pack量測7.63秒開始輸出、33.65秒完成，共38,468,511 bytes。這是打包量測，不是網路速率。

同一批次只對該次命令加`-c http.postBuffer=67108864`，成功推送並以ls-remote核對；其後c423354、f78cd70與main payload也成功。未改全域設定，未reset/rebase/force-push。此結果證明這次傳送方式可用；尚不足以歸因到特定proxy、HTTP版本或GitHub內部服務。

檔案只保留結構化狀態、數字、SHA與不含憑證的命令腳本；原始Git transport stdout/stderr未存入repo。錯誤輸出含up-to-date字樣不能替代remote SHA。publication.json固定記錄已核對的payload commits，後續metadata commits不自我引用；重查目前兩分支時，需再核對各自HEAD、git ls-remote與git status。
