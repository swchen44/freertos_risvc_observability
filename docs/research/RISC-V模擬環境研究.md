# RISC-V 模擬環境：已查證事實與實作提案

查核日期：2026-10-03。**以下是設計階段的研究，尚未安裝 QEMU、下載 FreeRTOS、編譯 firmware 或產生 RISC-V PSF。** 使用者已要求先用 `grilling` 釐清設計，本文的推薦仍待確認。

## 1. 推薦起點與替代方案

**提案：先使用官方 FreeRTOS 的 RV32 QEMU `virt` demo，固定 FreeRTOS 202411.00／Kernel V11.1.0，單 hart、M-mode，再接入本地 TraceRecorder v4.12.0。** 起點是可讀的 C／Makefile／啟動程式，不依賴 Eclipse。先跑原始 blinky，再新增正常／異常案例，避免把 demo 本身的全面壓力測試和案例故障混在一起。[官方 demo](https://github.com/FreeRTOS/FreeRTOS/blob/202411.00/FreeRTOS/Demo/RISC-V_RV32_QEMU_VIRT_GCC/Readme.md)、[官方 release](https://github.com/FreeRTOS/FreeRTOS/releases/tag/202411.00)

替代方案是同一 demo 的 Linux／容器建置，固定 OS image digest 和工具鏈 archive checksum。這有利於後續內部網路與 CI 重跑，但本機 Docker daemon 尚未可用，需要先選擇執行環境。舊 `sifive_e`／Freedom Studio demo 有官方維護者記錄的 QEMU 相容問題，不作第一個起點。[FreeRTOS 維護者的歷史說明](https://forums.freertos.org/t/freertos-blinky-demo-isnt-printing-to-qemu-console/10925)

## 2. 本機盤點

| 工具 | 已查到的狀態 | 對本次工作的意義 |
|---|---|---|
| `qemu-system-riscv32`／`qemu-system-riscv64` | PATH 中沒有 | 尚不能執行 RISC-V firmware |
| `riscv64-unknown-elf-gcc`／`riscv32-unknown-elf-gcc` | PATH 中沒有 | 官方 GCC demo 尚不能直接建置 |
| Apple clang | `/usr/bin/clang`，17.0.0 | 不等於已具有 embedded libc／完整連結環境 |
| Homebrew LLVM | `/opt/homebrew/opt/llvm/bin/clang`，23.1.1；有 `llvm-objcopy`／`llvm-size` | 先前 RV32 object-size 研究可用；完整 FreeRTOS image 尚未驗證 |
| Python | `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3`，3.13.2 | 可以建 harness 與 PSF parser |
| Docker | CLI 29.4.2，daemon 查詢失敗 | 不能只因 CLI 存在就宣稱容器方案可跑 |
| Homebrew／CMake／Make | Homebrew 7.0.6；CMake 4.3.4；系統 Make 3.81 | 具備部分前置工具；Make 相容性仍需建置驗證 |

盤點沒有輸出 token、個人環境變數或 Docker 私有設定。

## 3. 可固定的版本與原始碼

| 元件 | 候選固定值 | 必須另外保存的資訊 |
|---|---|---|
| FreeRTOS 完整 repo | tag `202411.00`；tag 指向 commit `152cf36d6775bce6026a791845af12201aae703d` | demo 與 Common source 的實際 commit、修改 diff |
| FreeRTOS Kernel submodule | `dbf70559b27d39c1fdb68dfb9a32140b6a6777a0`；`task.h` 標示 `V11.1.0` | 必須取得 submodule，只有父 repo ZIP 不保證包含 kernel |
| TraceRecorder | 本地 v4.12.0 | 本地 [source manifest](../../references/baseline/research/source-manifest.json) 與本次 port／config 修改 |
| QEMU | 候選 v8.2.2；目前官方 main demo README 記載曾用此版本測試 | 實際 executable 版本、package／source hash、machine／CPU options |
| macOS 工具鏈 | 候選 xPack RISC-V Embedded GCC `15.2.0-1`，有 darwin-arm64 archive | archive checksum、`-print-multi-lib`、`nano.specs`、sysroot、ISA／ABI |

202411.00 demo 的測試紀錄使用較舊 SiFive 工具，因此上述「QEMU 8.2.2＋xPack＋202411.00」組合是**待驗證提案**。目前 main demo 提供較新的 QEMU 測試紀錄，但包含 RV64／vector 等新分支；若改用 main，也必須固定 commit 和其 kernel submodule。[202411.00 demo](https://github.com/FreeRTOS/FreeRTOS/blob/202411.00/FreeRTOS/Demo/RISC-V_RV32_QEMU_VIRT_GCC/Readme.md)、[main demo](https://github.com/FreeRTOS/FreeRTOS/blob/main/FreeRTOS/Demo/RISC-V_RV32_QEMU_VIRT_GCC/Readme.md)、[固定 Kernel 的版本定義](https://github.com/FreeRTOS/FreeRTOS-Kernel/blob/dbf70559b27d39c1fdb68dfb9a32140b6a6777a0/include/task.h#L56)

Homebrew `riscv64-elf-gcc` formula 使用 `--without-headers`，不能把它當成已含 FreeRTOS demo 所需的 newlib-nano。xPack 官方文件提供 `nano.specs` 與 multilib 說明，但另要求 `medany`；demo 預設 `medlow`，選用時要核對並一致修改 compile／link options。`riscv-none-elf-` 與 demo 的 `riscv64-unknown-elf-` prefix 也需要明確映射。[Homebrew formula](https://github.com/Homebrew/homebrew-core/blob/HEAD/Formula/r/riscv64-elf-gcc.rb)、[xPack 使用指南](https://xpack-dev-tools.github.io/riscv-none-elf-gcc-xpack/docs/user/)、[xPack 15.2.0-1 release](https://github.com/xpack-dev-tools/riscv-none-elf-gcc-xpack/releases/tag/v15.2.0-1)

## 4. demo 的具體檔案與硬體模型

共同根目錄：`FreeRTOS/Demo/RISC-V_RV32_QEMU_VIRT_GCC/`。

| 項目 | 檔案／模型 | 已查到的設定 |
|---|---|---|
| 最小應用 | `main.c`、`main_blinky.c` | `mainCREATE_SIMPLE_BLINKY_DEMO_ONLY=1` 選簡單案例；目前 main 預設為 0，不能直接假設已選 blinky |
| 建置 | `build/gcc/Makefile` | `rv32imac`，較新 GCC 使用 `rv32imac_zicsr`；ABI `ilp32`；newlib-nano 或選配 picolibc |
| 啟動／trap | `build/gcc/start.S`、`vector.S` | M-mode、hart 0 執行；其他 harts 閒置，官方 `-smp 4` 不代表 FreeRTOS SMP |
| kernel port | `FreeRTOS/Source/portable/GCC/RISC-V/` | `chip_specific_extensions/RV32I_CLINT_no_extensions` |
| Linker memory | `build/gcc/fake_rom.ld` | ROM `0x80000000`、512 KiB；RAM `0x80080000`、512 KiB |
| Tick | `FreeRTOSConfig.h`、`riscv-virt.h` | CLINT base `0x02000000`；mtime `0x0200bff8`；mtimecmp `0x02004000` |
| UART | `ns16550.c`、`ns16550.h`、`riscv-virt.h` | NS16550 base `0x10000000`；輸出會 polling `LSR_THRE` |
| 簡單案例 | `main_blinky.c` | TX／RX queue；task 定期送訊息，software timer 也送訊息，RX 阻塞等待 |

檔案來源：[Makefile](https://github.com/FreeRTOS/FreeRTOS/blob/202411.00/FreeRTOS/Demo/RISC-V_RV32_QEMU_VIRT_GCC/build/gcc/Makefile)、[Linker script](https://github.com/FreeRTOS/FreeRTOS/blob/202411.00/FreeRTOS/Demo/RISC-V_RV32_QEMU_VIRT_GCC/build/gcc/fake_rom.ld)、[硬體地址](https://github.com/FreeRTOS/FreeRTOS/blob/202411.00/FreeRTOS/Demo/RISC-V_RV32_QEMU_VIRT_GCC/riscv-virt.h)、[NS16550 driver](https://github.com/FreeRTOS/FreeRTOS/blob/202411.00/FreeRTOS/Demo/RISC-V_RV32_QEMU_VIRT_GCC/ns16550.c)、[blinky source](https://github.com/FreeRTOS/FreeRTOS/blob/202411.00/FreeRTOS/Demo/RISC-V_RV32_QEMU_VIRT_GCC/main_blinky.c)

`main.c` 含另一組歷史 UART constants，不能只看名稱推導真正 console 地址。官方 GCC demo 的 `printf-stdarg.c` 實際呼叫 NS16550 driver。[printf 實作](https://github.com/FreeRTOS/FreeRTOS/blob/202411.00/FreeRTOS/Demo/RISC-V_RV32_QEMU_VIRT_GCC/build/gcc/printf-stdarg.c)

## 5. 必須先校正的兩個時鐘問題

### 5.1 FreeRTOS tick 與 QEMU mtime

已核對的 source：

1. demo 的 `configCPU_CLOCK_HZ=25000000`，`configTICK_RATE_HZ=1000`。[demo config，52–53 行](https://github.com/FreeRTOS/FreeRTOS/blob/202411.00/FreeRTOS/Demo/RISC-V_RV32_QEMU_VIRT_GCC/FreeRTOSConfig.h#L52)
2. Kernel RISC-V port 的 `uxTimerIncrementsForOneTick` 以 `configCPU_CLOCK_HZ / configTICK_RATE_HZ` 計算。[Kernel port，92 行](https://github.com/FreeRTOS/FreeRTOS-Kernel/blob/V11.1.0/portable/GCC/RISC-V/port.c#L92)
3. QEMU v8.2.2 ACLINT 定義 `RISCV_ACLINT_DEFAULT_TIMEBASE_FREQ=10000000`，`virt.c` 使用此值建立 timer。[ACLINT header，72 行](https://github.com/qemu/qemu/blob/v8.2.2/include/hw/intc/riscv_aclint.h#L72)、[virt timer 建立](https://github.com/qemu/qemu/blob/v8.2.2/hw/riscv/virt.c#L1403)

**推導：若照此設定且沒有其他 override，每個 RTOS tick 對應 25,000 個 mtime count，約 2.5 ms virtual time，等效 400 Hz。** 這是 source 算式推導，尚未跑模擬確認。測試方案需要用 mtime 與 RTOS tick 建獨立校正案例；不能以兩個共用錯誤設定的值互相證明正確。

### 5.2 TraceRecorder timestamp

本地 RV32 hardware port 用 `rdcycle`，`TRC_HWTC_FREQ_HZ` 固定 16 MHz。[trcHardwarePort.h，624／637／642 行](../../references/baseline/percepio/TraceRecorder/include/trcHardwarePort.h#L624)

**提案：使用 application-defined hardware port，從 QEMU mtime 取得 timestamp，明確記錄 timebase，並校正 FreeRTOS tick。** SDK 提供 application-defined 分支。[trcHardwarePort.h，717 行](../../references/baseline/percepio/TraceRecorder/include/trcHardwarePort.h#L717)

RV32 讀 64-bit mtime 必須處理兩次 32-bit read 的 rollover；也要測 recorder 的 32-bit counter wrap。這些是待實作與驗證點。即使 `rdcycle` 可在 QEMU 讀取，也不能直接把結果當成真實 silicon cycle 或保留固定 16 MHz 解碼。

## 6. FreeRTOS hook 整合與相容性

本地 port 有 `TRC_FREERTOS_VERSION_11_1_0` 選項，預設 `TRC_CFG_FREERTOS_VERSION` 尚未設定。[trcKernelPortConfig.h，52／54 行](../../references/baseline/percepio/TraceRecorder/kernelports/FreeRTOS/config/trcKernelPortConfig.h#L52)

**提案的整合範圍**是 `FreeRTOSConfig.h`、recorder config、build 的 include/source 清單、啟動初始化、自訂 timestamp／critical section／stream port。必須一起重編 FreeRTOS kernel，使 kernel 的 trace macros 生效。版本選項的存在不能代替編譯與執行相容性驗證。

SDK 以 `configUSE_TRACE_FACILITY` 控制 recorder，支援 task／queue 等 hooks；Timer／Event Group events 另有開關，case 所需事件必須明確啟用。[trcKernelPort.h，15／21 行](../../references/baseline/percepio/TraceRecorder/kernelports/FreeRTOS/include/trcKernelPort.h#L15)、[trcKernelPortConfig.h，57／67 行](../../references/baseline/percepio/TraceRecorder/kernelports/FreeRTOS/config/trcKernelPortConfig.h#L57)

先採單 hart，讓 critical section 與 timestamp 的驗證範圍明確；FreeRTOS SMP 要另列 test suite。本地 RV32 hardware port 的 M-mode interrupt mask 操作也需核對，不應以編譯成功代替正確性。[本地 critical section 實作](../../references/baseline/percepio/TraceRecorder/include/trcHardwarePort.h#L625)

## 7. PSF 收集與退出的方法選項

| 提案 | 資料路徑 | 優點 | 必須補上的工作與限制 |
|---|---|---|---|
| A. Semihosting binary file | recorder stream → semihosting open/write/close → host PSF | 可將 binary PSF 與 console 分開，適合自動 harness | 自訂 stream adapter 或完整 libc syscall；驗證 partial write、flush、close、失敗回報；semihosting 會存取 host filesystem，須限信任 firmware |
| B. 專用模擬 UART | recorder stream → NS16550 → QEMU file chardev → PSF | 走 MMIO／UART 路徑，接近後續 UART adapter 的 API 形狀 | 同一 UART 禁止混入 printf／monitor 字元；使用獨立 log 管道；模擬輸出速度不能證明實體 baud throughput |
| C. RingBuffer dump | recorder RAM ring → debugger／QMP memory dump → binary → PSF parser | 適合 snapshot／停止後取資料，可避開執行中持續 host I/O | 保存 header、entry table、timestamp、ring 位置；停止 CPU、處理 wrap 與截斷；不能把任意 RAM dump 直接改副檔名就當 PSF |

SDK File stream port 實際用 `fopen("wb")`、`fwrite`、`fclose`；bare-metal firmware 沒有 host filesystem bridge 時不能直接使用。[File stream 實作，98／138／173 行](../../references/baseline/percepio/TraceRecorder/streamports/File/trcStreamPort.c#L98)

SDK RingBuffer 的 layout 包含 start marker、header、timestamp、entry table、event buffer、end marker。[RingBuffer layout，64 行](../../references/baseline/percepio/TraceRecorder/streamports/RingBuffer/include/trcStreamPort.h#L64)

QEMU 支援 RISC-V semihosting；UART 可接 file chardev。QEMU v8.2.2 `virt` 的 UART0 與較新的雙 UART 模型要分開看，不能把最新文件的 UART1 地址套到舊版。[RISC-V semihosting 規格](https://docs.riscv.org/reference/semihosting/intro.html)、[QEMU semihosting](https://www.qemu.org/docs/master/about/emulation.html#semihosting)、[QEMU character backend](https://www.qemu.org/docs/master/system/qemu-manpage.html#character-device-options)、[v8.2.2 virt source](https://github.com/qemu/qemu/blob/v8.2.2/hw/riscv/virt.c)

退出可採 `virt` 的 SiFive Test finisher：MMIO base `0x00100000`；pass code `0x5555`，fail code `0x3333`。另可採 semihosting exit。應先 drain trace，再寫 completion 狀態、關閉檔案、退出；host 仍保留 timeout，將 hang／crash 與預期異常案例分開。[QEMU finisher 實作](https://github.com/qemu/qemu/blob/v8.2.2/hw/misc/sifive_test.c)、[finisher constants](https://github.com/qemu/qemu/blob/v8.2.2/include/hw/misc/sifive_test.h#L40)

## 8. 可重現性與量測邊界

**提案：單 hart、TCG single thread、固定 ISA／ABI／binary／case input／QEMU 版本；考慮固定 `icount` 模式，保存所有 command options。** `icount` 可把 instruction count 映射為 virtual time；`sleep=off` 的 idle 行為也必須保存，因為它會跳至下一個 timer deadline。[QEMU icount 原理](https://www.qemu.org/docs/master/devel/tcg-icount.html)、[QEMU invocation](https://www.qemu.org/docs/master/system/qemu-manpage.html)

| 模擬案例可以支持的結論 | 模擬結果不能直接支持的結論 |
|---|---|
| 指定輸入下 task／queue／mutex 行為，以及正常／異常差異 | 真實 RISC-V MCU 上的 CPU overhead 百分比 |
| 真正執行 SDK 產生的 PSF 可否被 Python parser 解碼 | silicon WCET、cache／pipeline／memory contention 成本 |
| event ordering、case payload、阻塞／喚醒與錯誤偵測 | 實體 UART DMA、線速、接收器與電氣限制 |
| 指定虛擬時鐘模型下的 response time／deadline | 真實板上的 ISR latency、DVFS／sleep 行為 |
| Buffer drop／截斷／parser 拒絕損毀檔的行為 | 規定之外的 PSF 版本／Tracealyzer 功能相容性 |
| 固定映像的 linked code/RAM size 與 A/B 差異 | 使用者產品完整韌體的大小與效能 |

QEMU 官方明確說明 `icount` 不是 cycle-accurate simulation。host CPU 百分比與 host wall time 只能用來衡量 harness 執行成本。若後續報告計算 guest task loading，名稱與輸出 metadata 應明示「指定 QEMU virtual-time model」。[QEMU 官方界線](https://www.qemu.org/docs/master/devel/tcg-icount.html)

## 9. Integration test 的失敗模式與驗收提案

| 失敗模式 | 不應誤判為 | 驗收方法提案 |
|---|---|---|
| Kernel submodule 空白、缺 nano.specs／libc | SDK 不相容 | preflight 核對 source／toolchain manifest，再跑未加 SDK 的 demo |
| Tick clock 或 PSF timestamp frequency 錯誤 | deadline miss／task loading 異常 | 獨立 mtime 對 RTOS tick 校正與已知延遲 case |
| 只重編 application、kernel hooks 未生效 | parser 看漏事件 | 檢查 kernel compile inputs；要求 task create／switch／queue events 出現 |
| Timer／Event Group event 未啟用 | firmware 沒執行功能 | 對 case 宣告 required event families，核對 SDK config |
| UART 混入 printf、stream 未 drain | PSF 格式不支援 | raw binary 與 console 分離；保存 byte count／hash／completion 狀態 |
| Trace buffer overflow、ring wrap | 系統沒有發生某事件 | 驗證 loss indicator／ring 範圍，不能只檢查有一份檔案 |
| Parser 以自己產生的 JSON 當期望值 | 文件已獲實證驗證 | 事先建立 case oracle；獨立 case payload／RTOS結果／PSF互相比對 |
| firmware hang／非預期 assert | 成功重現預期異常 | host timeout 與 case completion 要單獨記錄；預期異常也必須有通過標準 |

提案的最小階段是「原始 blinky 可跑 → 時鐘校正 → SDK 最小事件 → 一組正常／異常 queue case → PSF→JSON 與獨立 oracle → 更多案例與 dashboard」。這段為階段提案，尚未執行。

## 10. 尚待決定與尚待查驗

設計需要確定首版驗收範圍與部署限制。Agent 會依本機條件提出工具鏈、capture、stream／ring 與案例的具體推薦並查證；不要求使用者代查相容性或逐一選內部實作細節。若選擇會增加安裝環境、改變可交付功能、捨棄既有 PSF 支援，或改變成本／量測承諾，再依 `grilling` 提出產品取捨。模擬 A/B 指標需明確標示 virtual-time 模型。

Agent 後續需要自行查驗：候選工具鏈實際 multilib／sysroot、選定 QEMU CPU extension、完整 compile／link、原始 demo 執行、實際 timer frequency、SDK hooks 是否完整、PSF layout／event parameter 對照、capture partial-write／loss 行為、同一 case 重跑的一致性。這些是工作事項，無須要求使用者替 agent 查事實。
