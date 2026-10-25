# C2b clock-anchor pilot：接續提案

狀態：**2026-10-25使用者已選A，具體書面規格已完成、等待審閱；尚無新增capture或guest修改。** [C2b v1設計規格](../design/c2b-clock-anchor-pilot-v1.md)提出同ELF markers、16-run pilot與分層驗收。C2a已完成40-run／8HTML與本機驗收；本計畫不把event index或累積model cost換成PSF timestamp。

## 2026-10-23 接續 checkpoint

- [x] 固定研究 QEMU 9.2 binary 與 A02 baseline／pbuf manifest SHA 相符；只做version／hash讀取。
- [x] QEMU API／callback／icount／applied安全前提來源盤點，見[能力表](../research/c2b-qemu-clock-capabilities.md)。任意instruction callback讀clock沒有安全保證；request clock須允許null。
- [x] SDK user-event／application-defined mtime與保存PSF重解析，見[SDK與pilot邊界](../research/c2b-sdk-anchor-capabilities.md)；來源及讀檔證據在[planning資料夾](../../artifacts/verification/clock-anchor/planning-20261023/)。這些不等於新runtime驗收。
- [x] 2026-10-25使用者選A：app／port加少量SDK markers、不改kernel／SDK；不再等待A／B選擇。
- [x] 完成並自我審閱具體anchor介面、最小pilot與錯誤／誤差判定，見[C2b v1書面規格](../design/c2b-clock-anchor-pilot-v1.md)。提出的數字仍待書面審閱。
- [ ] 使用者審閱書面規格後，建立逐項實作計畫及執行方式。
- [ ] 新capture、observer對照、誤差量測、Web／offline視圖與E2E；不得用本輪source audit勾成已完成。

## 目的與順序

1. 唯讀盤點現有QEMU版本/plugin headers、callback發生位置、實際CPU/hart配置、SDK hardware-port timer與PSF header frequency；記錄來源檔案、版本與可用／不可用能力。
2. 確認是否能在適當callback安全取得guest clock；不能預設plugin可直接讀CSR、mtime，或用host wall clock代替。讀不到就保留unavailable，提出最小替代實驗。
3. 盤點既有SDK user-event/port介面能否保留raw counter、marker sequence與clock-domain；優先使用現有hook，不先假定需要修改FreeRTOS kernel。
4. 根據實際能力寫出可審閱的request/applied anchor schema、clock domains與誤差量測方法，再確認pilot範圍後實作。
5. Pilot使用A02 baseline/pbuf；書面規格提出5筆SDK markers與16-run L/C/O/M對照，repeat=1，先做4次smoke。這些是待審閱設計，不宣稱使用者已核准次數；產品誤差預算沒有提供，先驗證clock關係並實測bounds，不自造ns門檻。

## 必須保留的證據

候選欄位為run identity、marker sequence、event index、raw counter、counter width、frequency、clock-domain、request/applied phase、source hashes、quality。這些仍是待能力確認的草案；unknown frequency不得強制轉ns。所有原PSF順序、origin、gap、wrap與未知事件都保留。

要測相同timestamp、非零origin、counter wrap、sequence gap、anchor缺失／重複／重排與clock domain不一致。只有有證據的映射才顯示可對齊；缺資料時維持兩軸獨立，不插值補造。

## 待決策

- 固定timer／hart配置已由來源核對，修改範圍A已確認；目前審閱點是具體書面規格。Pilot先量bounds，未提供產品解析度預算時回報unrated，不從100ns量化或舊200ns整窗條件推論通過門檻。
- C2b仍是相對模擬研究；實機PMU、SDK on/off code-size/CPU/IRQ latency、UART吞吐另需公司平台資料。
- 原單篇知識庫已在先前階段同步；本輪C2a新增資料以本repo為準，知識庫增補尚未同步，列後續而不冒稱完成。
- 跨機目標平台驗證依既有決定暫緩，不新增這個目標。

書面設計已完成；逐項實作計畫、build、captures與runtime驗收尚未開始，不能把來源研究或本文的已勾選設計項當成pilot成功。
