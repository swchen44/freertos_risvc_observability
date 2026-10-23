# C2b clock-anchor pilot：接續提案

狀態：**提案，尚未開始、沒有新增capture或修改guest。** C2a已完成40-run／8HTML與本機驗收；本計畫不把event index或累積model cost換成PSF timestamp。

## 目的與順序

1. 唯讀盤點現有QEMU版本/plugin headers、callback發生位置、實際CPU/hart配置、SDK hardware-port timer與PSF header frequency；記錄來源檔案、版本與可用／不可用能力。
2. 確認是否能在適當callback安全取得guest clock；不能預設plugin可直接讀CSR、mtime，或用host wall clock代替。讀不到就保留unavailable，提出最小替代實驗。
3. 盤點既有SDK user-event/port介面能否保留raw counter、marker sequence與clock-domain；優先使用現有hook，不先假定需要修改FreeRTOS kernel。
4. 根據實際能力寫出可審閱的request/applied anchor schema、clock domains與誤差量測方法，再確認pilot範圍後實作。
5. Pilot先使用可對照的A02 baseline/pbuf；observer off/on的capture次數、計時誤差預算和是否新增marker，須在能力盤點後明確決定，不能猜數字。

## 必須保留的證據

候選欄位為run identity、marker sequence、event index、raw counter、counter width、frequency、clock-domain、request/applied phase、source hashes、quality。這些仍是待能力確認的草案；unknown frequency不得強制轉ns。所有原PSF順序、origin、gap、wrap與未知事件都保留。

要測相同timestamp、非零origin、counter wrap、sequence gap、anchor缺失／重複／重排與clock domain不一致。只有有證據的映射才顯示可對齊；缺資料時維持兩軸獨立，不插值補造。

## 待決策

- 實際timer與hart配置、可接受修改範圍、pilot誤差預算；先用source盤點回答能回答的部分，再提出使用者必須決定的選項。
- C2b仍是相對模擬研究；實機PMU、SDK on/off code-size/CPU/IRQ latency、UART吞吐另需公司平台資料。
- 原單篇知識庫已在先前階段同步；本輪C2a新增資料以本repo為準，知識庫增補尚未同步，列後續而不冒稱完成。
- 跨機目標平台驗證依既有決定暫緩，不新增這個目標。

本提案尚未完成正式實作規格；實作前須帶著API能力表與具體實驗方案再審閱。
