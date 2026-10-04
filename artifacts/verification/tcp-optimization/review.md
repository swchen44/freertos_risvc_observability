# TCP 最佳化完整分支 review

2026-10-04，獨立 reviewer tcp_optimization_review。

沒有 Critical / Important。9組captures 全數重播，18筆summary與results一致；Python新測試8/8、JS新增測試2/2。No-copy immutable buffer ownership、遺失ACK後packet sequence/payload/checksum，split L1 / shared L2 與 cold-per-phase 均確認。

Minor：trace比rdinstret每phase多11條 instrumentation指令。本輪保留兩種邊界；報告已明示，未統一指標分母。

v1定量擷取後增加的驗證/UI程式碼，已在固定final code後重新擷取v2，並核對capture sources目前一致。

NIC/DMA/實機RTT、第二個完整peer、長期並行連線不在bounded testcase範圍，不用這些結果宣稱實機Mbps。Browser由主流程用agent-browser獨立驗證。
