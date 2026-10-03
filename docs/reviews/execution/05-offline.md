# 離線 HTML 執行 ledger

Base b4462ce；原專用 feat/psf-lab 工作目錄，未改 main 上的產品程式。

- T1 完成：資料契約、既有畫面基準與 Python parity fixtures。
- T2 完成：c781e84，7 個新增 unit tests，含七真實案例、BigInt、Unicode、安全封裝、CSV、empty／density。
- T3 完成：curl 5 integration；agent-browser Server／offline 各完整流程；停止 Server、offline on、網路 route abort、無請求。補 hover、分母、快速 filters、partial、10,000-event download；20 PNG 與 hashes。
- T4／T5：使用者 2B 整項暫緩。
- T6 完成：README 六張精選圖、指南二十張圖與重跑命令，舊狀態標歷史。
- T7 完成：知識庫 83fd7d4、root cce0e68、POC 5594d73 已核對 remote；completion.json 保存發布 snapshot。後續僅追加此收尾文件。

Ruling：離線單 trace 不內嵌 registry／oracle comparison，Server 保留；代價是離線兩份資料分開閱讀。
Ruling：curl integration 寫成 Python unittest 呼叫真實 curl，利於精確斷言；沒有以 mock 取代 HTTP。
Ruling：agent-browser 對畫面外元素先 scrollIntoView 再實際互動，以結果 assertions 防止假成功。
Ruling：CSV fraction 使用數值比較，允許等價科學記號／十進位表示，其餘欄位精確比對。
Final review：gpt-6-astra，Critical 0、Important 1 為 E2E 覆蓋缺口，已補實跑；兩項 Minor 文件／證據屬原任務內工作並完成，沒有延後功能性缺陷。
