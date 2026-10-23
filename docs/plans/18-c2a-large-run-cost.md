# C2a 大 run 續作記錄

沿用plan15/17與既定25s/5s/640MiB門檻。唯一session新一輪A08載入26.55s/filter5.70s超限，冷B2切換也碰到50s工具等待上限；保留失敗，不以顯示完成文字取代通過。

## 受控改善

- Python只對type精確為str的canonical "0"/"1"直接回int常數；其他值、str subclass仍走原regex/int。沒有放寬schema或跳過hash。
- JS在同一numeric parse中做row identity/dictionary bounds，chunk start與dictionary length只轉一次BigInt，避免重複逐列轉換。
- 無context/function篩選且整塊落在選區時，重用decode已逐列加總並與descriptor核對過的totals；部分塊/有篩選仍逐列加總。逐列hash/schema/operation/3C守恆全部保留，function groups/bins/page/CSV仍處理完整選區。
- 三組A08 Node對照3.42–3.54s→2.74–2.84s，完整JSON hash一致；Python20 chunks三組0.312–0.318s→0.247–0.259s，全部gzip bytes hash一致。這是host分析成本，不是MCU SDK CPU百分比。
- 新增全塊/同集合context/部分塊的結果一致性；canonical數字含尾端換行試驗原先即拒絕，因此沒有修改JS regex。保留這筆原本就通過的試驗，不當RED宣稱。
- 非gate互動/命令外層等待由50改120s；原生下載完成等待180s不變，ready25/filter5/RSS640/heap128/bins512不變。

## 後續驗證

新source完整Python/Node/Ruff/review；重建8HTML，容量期間不跑generator；新API先確認ready，唯一session序列重跑A02/A08與其餘workload；force-failure驗finally-close；所有失敗保留。舊8HTML已在3a852284的Git歷史，沒有覆寫或遺失它們。
