# 640 MiB RSS 門檻重驗 · 2026-10-14

使用者明確核准將RSS驗收上限由512改為640 MiB。只變更RSS上限；25s載入、5s篩選、128MiB page heap及512圖表bins保持原設定。歷史收據不改写。

| 測試 | RSS MiB | ready s | filter s | 結果 |
|---|---:|---:|---:|---|
| server-full | 432.08 | 25.83 | 4.74 | RSS通過；時間門檻未全通過 |
| server-recheck | 377.17 | 22.87 | 5.93 | RSS通過；時間門檻未全通過 |
| offline-full | 545.05 | 5.82 | 4.26 | 通過 |

server-full及offline-full均包含完整互動、430324列CSV下載與取消／重試。server-recheck只重驗容量範圍，不能取代完整互動。每次專用browser皆close成功、無剩餘PID，offline測試前server已停止並阻擋HTTP/HTTPS。

RSS門檻變更已完成；整體C2a驗收尚未完成，正式40runs／8HTML未擴大。Web時間波動保留為後續待辦，不能用RSS通過掩蓋。

獨立review已確認commit8d86979門檻一致，未修改其他條件或舊artifacts。每份receipt保存harness SHA與source commit；harness.py、commands.json、RSS採樣、CSV與screenshots均保留。
