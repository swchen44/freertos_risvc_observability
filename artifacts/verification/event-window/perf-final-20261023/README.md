# 大run分析成本對照

`paired-node.json`完整A08查詢3組before/after，result_sha256全部相同；`paired-python.json`在每組清空manifest parse cache，再讀同20 chunks，payload SHA全部一致。Node與Python結果只代表本機分析器，不是嵌入式SDK效能。

`before.mjs/after.mjs`與`before.py/after.py`是對照source快照；benchmark需在POC根目錄執行，資料在正式40-run集。第一次Python paired driver漏設PYTHONPATH，沒有產生有效量測，補設後才採認paired-python.json。canonical newline試驗原先就通過，未改regex。

架構、完整保真與後續條件見docs/plans/18-c2a-large-run-cost.md。
