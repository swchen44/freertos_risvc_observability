# PSF 格式與解析研究

查核日期：2026-10-03。範圍：本地 TraceRecorder v4.12.0、桌面 SDK demo 自帶 recorder，以及既有 `desktop-demo.psf`。

> **已確認：PSF 能從公開 recorder 的寫入程式推導並自行解析。現有桌面檔案有 309 個事件，包含 50 次完整的示範序列。**
>
> **尚未完成：產品用 Python decoder、RISC-V／FreeRTOS 新案例、harness、JSON schema、互動 Dashboard，以及與其他 decoder 的執行結果比對。**本節使用一次性的唯讀 `struct` 探測；沒有購買或使用 Tracealyzer GUI。

## 1. PSF 是什麼，這次證明了什麼

PSF 是 Percepio Streaming Format。Recorder 把事件編碼成 binary stream，再交給 stream port 保存或傳送。官方桌面 SDK demo 的 FILE port 會建立 `.psf`；官方 SDK repository 提供建立自訂 kernel／API 事件的範例。[Percepio SDK demos](https://github.com/percepio/Tracealyzer-SDK-demos)

本次使用已存在的 [桌面 PSF](../../references/baseline/research/cases/desktop-demo.psf)，核對檔頭、metadata、entry、事件 framing、counter、timestamp，以及與 [main.c](../../references/baseline/Tracealyzer-SDK-demos/GCC_MinGW_x86_64/main.c) 的 50 輪事件序列是否一致。這可以作為 parser 的第一份固定輸入。

這個桌面程式手動呼叫 recorder API，以 `sleep_ms` 拉開事件間隔。`main.c` 第 91–98 行的 mutex lock／unlock 只產生事件，沒有真實 mutex；第 101–118 行的 critical section functions 也是 placeholder。此 trace 可驗證編碼與既有範例的事件順序，不能驗證真實 FreeRTOS 排程、priority inheritance、deadlock 或 RISC-V CPU loading。

| 問題 | 本次答案 | 尚需補強的證據 |
|---|---|---|
| 能否了解這份 binary？ | 能，讀到 header／metadata／309 個完整事件 | 做正式 decoder，處理不可信或不完整輸入 |
| 它是否與桌面範例相符？ | 50 次序列與 Counter 0～49 全部相符 | 更多正常、異常、重啟與長時間案例 |
| 同樣 format version 就能共用事件表？ | 不行，kernel schema 不同 | 按 platform／schema version 派送 |
| 能否解析產品 FreeRTOS trace？ | 本次尚未產生產品 trace | 實際 FreeRTOS hook、ELF、設定與 simulator trace |
| 有沒有免費 parser 可參考？ | 有 Apache-2.0 Rust parser | 它的 32-bit FreeRTOS 範圍須與我們需求對照 |

## 2. 資料來源與版本邊界

本地 source 是本文 layout 的主要依據。線上 `main` 或 `latest` 可能與本地 v4.12.0 不同，正式驗證應固定 SDK hash／commit。

| 來源 | 具體檔案與行號 | 用途 |
|---|---|---|
| 主 SDK v4.12.0 | [trcStreamingRecorder.c](../../references/baseline/percepio/TraceRecorder/trcStreamingRecorder.c)，第 24–59 行 | header 與 format version |
| 桌面 recorder | [trcStreamingRecorder.c](../../references/baseline/Tracealyzer-SDK-demos/GCC_MinGW_x86_64/TraceRecorder/trcStreamingRecorder.c)，第 31–66 行 | 桌面相同 header／format 14；檔案註解標示 v4.8.2 |
| Base type | [主 trcTypes.h](../../references/baseline/percepio/TraceRecorder/include/trcTypes.h)，第 22–32 行；[桌面 trcConfig.h](../../references/baseline/Tracealyzer-SDK-demos/GCC_MinGW_x86_64/TraceRecorder/config/trcConfig.h)，第 342–359 行 | 預設 32-bit；桌面指定 `int64_t` 與 timer |
| FreeRTOS schema | [trcKernelPort.h](../../references/baseline/percepio/TraceRecorder/kernelports/FreeRTOS/include/trcKernelPort.h)，第 90–114、388、523–647 行 | platform／config version／event IDs |
| 桌面 schema | [trcKernelPort.h](../../references/baseline/Tracealyzer-SDK-demos/GCC_MinGW_x86_64/TraceRecorder/include/trcKernelPort.h)，第 54–57、134–193 行；[XML](../../references/baseline/Tracealyzer-SDK-demos/GCC_MinGW_x86_64/my_krnl-v1.0.0.xml) | 自訂 `my_krnl` 事件語意 |
| 原始案例 | [main.c](../../references/baseline/Tracealyzer-SDK-demos/GCC_MinGW_x86_64/main.c)，第 40–98 行 | 可獨立核對的預期序列 |
| 既有 build／run 證據 | [desktop-demo-evidence.json](../../references/baseline/research/cases/desktop-demo-evidence.json)、[build log](../../references/baseline/research/cases/desktop-demo-build.log) | 輸入檔案來源與既有編譯條件 |
| Source hashes | [source-manifest.json](../../references/baseline/research/source-manifest.json) | 本次研究來源的檔案識別 |

本文只證明本地兩套 writer 都宣告 `TRACE_FORMAT_VERSION = 0x000E`。沒有宣稱此布局適用所有 PSF 版本。

## 3. Header：32 bytes

主 SDK [trcStreamingRecorder.c](../../references/baseline/percepio/TraceRecorder/trcStreamingRecorder.c) 第 24–36 行定義 `TraceHeader_t`；第 56–59 行定義版本與 endianness identifier。

| Offset | Bytes | 欄位 | 解讀 |
|---:|---:|---|---|
| 0 | 4 | `uiPSF` | 數值 `0x50534600`，用來辨識 byte order |
| 4 | 2 | `uiVersion` | 本次 `0x000E`，decimal 14 |
| 6 | 2 | `uiPlatform` | Kernel／platform ID |
| 8 | 4 | `uiOptions` | IRQ priority、test mode、base-width 等旗標 |
| 12 | 4 | `uiNumCores` | Core count 與 stream 模式旗標 |
| 16 | 4 | `isrTailchainingThreshold` | ISR tail-chaining threshold |
| 20 | 2 | `uiPlatformCfgPatch` | Schema patch version |
| 22 | 1 | `uiPlatformCfgMinor` | Schema minor version |
| 23 | 1 | `uiPlatformCfgMajor` | Schema major version |
| 24 | 8 | `platformCfg` | 最多 8 bytes 的 platform config 名稱 |

### 3.1 Endianness

檔頭原始 bytes：

```text
little-endian: 00 46 53 50
big-endian:    50 53 46 00
```

`PSF` 的字母順序不一定直接可見。先辨識 raw bytes，接著對 header、metadata、event 的數字欄位使用同一 byte order。字串保持原始 byte 順序。

### 3.2 Options 與 core flags

實際寫入見主 SDK 同檔第 328–347 行：

| 欄位 | Bits | 本次 writer 的意義 |
|---|---|---|
| `uiOptions` | bit 0 | `TRC_IRQ_PRIORITY_ORDER` |
| `uiOptions` | bit 2 | `TRC_CFG_TEST_MODE` |
| `uiOptions` | bit 3 | `TraceUnsignedBaseType_t` 為 64-bit |
| `uiNumCores` | 低位 core count；現有 reader 使用低 8 bits | Core count |
| `uiNumCores` | bits 8–9 | 有 `TRC_STREAM_PORT_MULTISTREAM_SUPPORT` 時寫入 `2`，否則 `3` |

桌面檔案 `uiOptions = 9`，64-bit flag 為 1；`uiNumCores = 0x301` 表示 1 core，加上 stream flags。不能把 `769` 當成 769 個 core。

32／64-bit 是 trace base type／handle 寬度，timestamp 在一般 event header 中仍是 32-bit。實作還要核對 C ABI、pointer 寬度與 recorder 編譯設定；不能把 host 的 Python／C 型別大小直接套入檔案。

## 4. Stream metadata、entry 與 string

### 4.1 寫入順序

主 SDK [trcStreamingRecorder.c](../../references/baseline/percepio/TraceRecorder/trcStreamingRecorder.c) 第 571–626 行：

```text
Header 32 bytes
    ↓
Timestamp metadata
    ↓
Entry table header：3 × base-width
    ↓
Used entry records
    ↓
TraceStart event
    ↓
一般事件、物件名稱、應用事件……
```

主 SDK 以 raw blocking write 保存 header／metadata。這些 raw blocks 也會遞增 event counter，見 [trcEvent.c](../../references/baseline/percepio/TraceRecorder/trcEvent.c) 第 278–294 行。因此第一筆 event 的 counter 不是必然從 1 開始。

### 4.2 Timestamp metadata

定義在 [trcTimestamp.h](../../references/baseline/percepio/TraceRecorder/include/trcTimestamp.h) 第 35–44 行。

| 順序 | 型別 | 欄位 |
|---:|---|---|
| 1 | `uint32_t` | `type` |
| 2 | `uint32_t` | `period` |
| 3 | base-width unsigned integer | `frequency` |
| 4 | `uint32_t` | `wraparounds` |
| 5 | `uint32_t` | `osTickHz` |
| 6 | `uint32_t` | `latestTimestamp` |
| 7 | `uint32_t` | `osTickCount` |

在本次布局下，32-bit base type 為 28 bytes，64-bit 為 32 bytes。這是本地格式 14 的 field order；舊格式可能不同。

### 4.3 Entry table

Stream table header 為三個 base-width 整數：`used_entry_count`、`symbol_size`、`state_count`，見主 SDK writer 第 593–607 行。

Entry 定義見 [trcEntryTable.h](../../references/baseline/percepio/TraceRecorder/include/trcEntryTable.h) 第 43–81 行：

```text
address / object handle
3 × base-width states
uint32 options
symbol_size bytes 的名稱
```

`symbol_size` 已依 base-width 與 options 欄位做對齊，不應硬寫成所有檔案固定 28。配置不同就會不同。

初始表只包含 recording 開始時已登記的物件；之後的 ObjectName／create／delete 會繼續維護物件資訊。現有桌面表只有 `main`，其後才出現 `Logging`、`IDLE`、`Task2`、`mutex1`。

### 4.4 Strings、格式字串與 ELF

一般名稱事件包含 handle 與 inline string。固定格式 User Event 可使用 string handle；compact logging 則可能依編譯產物中的字串位址解析，應保存正確 ELF／build ID。不能假定每份 `.psf` 都自帶所有可讀文字。

桌面 [XML](../../references/baseline/Tracealyzer-SDK-demos/GCC_MinGW_x86_64/my_krnl-v1.0.0.xml) 第 52–129 行區分 inline 與 handle 型 User Event，也標示 `PrintfArgStart`。XML 提供語意，binary framing 還是要由 writer source 解讀。

**字串停止於第一個 NUL。**現有檔案在 padding 中可見 `IDLE\0Tas`、`Task2\0mu`、`Counter: %d\0%s: `。這些尾端 bytes 不屬於名稱或 message，不保證為零。正式 decoder 宜保留 raw payload，但不能把尾端資料顯示成文字內容。

Padding 的觀察本身不能證明是哪一個記憶體安全問題。若要判斷 out-of-bounds read 或資料外洩，應另用 sanitizer／writer source review 驗證；本次沒有執行此項驗證。

## 5. Event framing 與 kernel schema

### 5.1 一般 event

定義見 [trcEvent.h](../../references/baseline/percepio/TraceRecorder/include/trcEvent.h) 第 33–49 行；bits 與大小公式見 [trcEvent.c](../../references/baseline/percepio/TraceRecorder/trcEvent.c) 第 44–80 行。

| Offset | Bytes | 欄位 |
|---:|---:|---|
| 0 | 2 | `EventID`，高 4 bits 是 payload word count，低 12 bits 是 event ID |
| 2 | 2 | `EventCount` |
| 4 | 4 | `TS`，raw timer timestamp |
| 8 | `N × base_width` | Payload，包括數值、handle、inline string 等 |

```text
semantic_id = EventID & 0x0FFF
payload_words = (EventID >> 12) & 0x0F
event_bytes = 8 + payload_words * base_width
```

Payload word count 不等於業務參數個數。例如桌面 `Counter: %d` 的 event 包含 channel handle、整數與 inline 格式字串，總共 4 個 64-bit words。

實際 writer 還有 `TRC_MAX_BLOB_SIZE` 與截斷／對齊政策，見 [trcRecorder.h](../../references/baseline/percepio/TraceRecorder/include/trcRecorder.h) 第 67 行、[trcEvent.c](../../references/baseline/percepio/TraceRecorder/trcEvent.c) 第 301–335 行。未來 parser 應驗證允許的大小與欄位，不應只相信 header。

### 5.2 Counter 與 core ID

單核心使用 16-bit counter。多核心將 core ID 放在高 4 bits，該 core 的 modulo counter 放在低 12 bits。來源：`trcEvent.c` 第 51–55 行。

分析 sequence gap 前，要先選對 16-bit／12-bit modulo，並依 core 分開。不能把 interleaved cores 的不同 counters 當成 loss。

### 5.3 相同數字，不同事件

| Event ID | 桌面 `my_krnl 1.0.0` | 主 SDK FreeRTOS `1.2.0` |
|---|---|---|
| `0x10` | TaskCreate | TaskCreate |
| `0x20` | TaskReady | TaskDelete |
| `0x25` | SwitchToTask／TaskActivate | EventGroupDelete |
| `0x52` | User Event，有一個 printf argument | MutexGive |
| `0x60` | 自訂 mutex create | QueueReceive |
| `0x61` | 自訂 mutex lock | SemaphoreTake |
| `0x62` | 自訂 mutex unlock | MutexTake |
| `0x90` | 不能套用為桌面 User Event | FreeRTOS User Event 起始 ID |

來源：[桌面 trcKernelPort.h](../../references/baseline/Tracealyzer-SDK-demos/GCC_MinGW_x86_64/TraceRecorder/include/trcKernelPort.h) 第 134–193 行；[FreeRTOS trcKernelPort.h](../../references/baseline/percepio/TraceRecorder/kernelports/FreeRTOS/include/trcKernelPort.h) 第 523–647 行。桌面 [XML](../../references/baseline/Tracealyzer-SDK-demos/GCC_MinGW_x86_64/my_krnl-v1.0.0.xml) 第 8–47 行補上 service／object class 語意。

因此 parser 的 schema key 至少要包含 format version、platform ID、platform config 名稱與版本。無法辨識 schema 時，可以保存 raw event，不能自動套用 FreeRTOS 的事件表。

本地 schema 的具體識別：桌面為 `0x1FF1 / my_krnl / 1.0.0`；主 FreeRTOS 為 `0x1AA1 / FreeRTOS / 1.2.0`。依據為上表的 kernel port headers；這些是目前 source 的值，不代表所有 SDK 版本相同。

## 6. 現有桌面 PSF 的實際核對結果

### 6.1 Header、metadata、offset

| 欄位 | 讀出的值 |
|---|---|
| 檔案 | `research/cases/desktop-demo.psf` |
| Bytes | `7152` |
| SHA-256 | `32f6421362bda37e3b91411afedb5df0c29741f99fe1df08389cf76e56f79d47` |
| Endianness | little-endian |
| Format | 14 |
| Platform ID | `0x1FF1` |
| Options | `0x00000009` |
| Core 欄位 | `0x00000301`，core count 1 |
| Tail-chaining threshold | 0 |
| Config | `my_krnl`，1.0.0 |
| Timer type | 1，free-running increment |
| Frequency | 1,000,000 Hz |
| Period | 0 |
| Initial wraparounds | 0 |
| OS tick Hz | 1 |
| Initial latestTimestamp／osTickCount | 0／0 |
| Entry count／symbol size／state count | 1／28／3 |
| Entry | `main`；handle `4376166696`；states `[1,0,0]`；options 0 |
| Header offset | 0，大小 32 |
| Timestamp offset | 32，大小 32 |
| Entry header offset | 64，大小 24 |
| 第一個 entry offset | 88，大小 64 |
| 第一個 event offset | 152 |
| 最後一個 event offset | 7128，大小 24 |
| 下一個 event offset | 7152，剛好 EOF |

### 6.2 309 events 與 50 次序列

| Event ID | 桌面語意 | 數量 |
|---|---|---:|
| `0x01` | TraceStart | 1 |
| `0x03` | ObjectName | 4 |
| `0x10` | TaskCreate | 2 |
| `0x60` | 自訂 mutex create | 1 |
| `0x20` | TaskReady | 51 |
| `0x25` | TaskSwitch／activate | 100 |
| `0x61` | 自訂 mutex lock | 50 |
| `0x52` | `Counter: %d` User Event | 50 |
| `0x62` | 自訂 mutex unlock | 50 |
| 合計 |  | **309** |

前 9 筆事件為：

```text
TraceStart
Logging 名稱
IDLE 名稱
IDLE create
Task2 名稱
Task2 create
mutex1 名稱
mutex1 create
IDLE ready
```

其後 300 筆完全符合以下 pattern，重複 50 次：

```text
Task2 ready
→ switch Task2，handle 2
→ mutex1 lock，handle 3
→ Counter: 0、1、2、……、49
→ mutex1 unlock，handle 3
→ switch IDLE，handle 1
```

實際檢查結果：

```text
counter_0_to_49: True
50_cycles_event_pattern: True
event_count: 309
full_eof: True
switch_handles: {2: 50, 1: 50}
mutex_handles: {3: 100}
sequence_gaps: []
timestamp_regressions: []
```

Sequence 為 5～313。第一個 event raw timestamp 是 190，最後是 5,763,892；同一 event timestamp 可以相同，不能要求嚴格遞增。上述時間來自桌面計時，沒有換算成板上 CPU overhead。

### 6.3 本次使用的唯讀 probe

條件：在此研究根目錄執行 Python 3；只使用標準函式庫；只讀既有 PSF；不寫入檔案、不開啟 simulator、不重新產生 trace。因為先從 source 與 header 確認了本檔為 64-bit／little-endian，因此 probe 明確固定 `<` 與 `Q`。

這段是**單一檔案的研究探測方法**，沒有宣稱可處理任意 PSF、截斷、corrupt、其他 kernel、其他 format version、snapshot 或 SMP。

```python
from pathlib import Path
import collections
import hashlib
import struct

data = Path("research/cases/desktop-demo.psf").read_bytes()
print("bytes", len(data))
print("sha256", hashlib.sha256(data).hexdigest())
print("header", struct.unpack_from("<IHHIIIHBB8s", data, 0))
print("timestamp", struct.unpack_from("<IIQIIII", data, 32))
print("entry_header", struct.unpack_from("<QQQ", data, 64))
print("first_entry", struct.unpack_from("<QQQQI28s", data, 88))

offset = 152
events = []
while offset < len(data):
    assert offset + 8 <= len(data)
    wire_id, count, timestamp = struct.unpack_from("<HHI", data, offset)
    words = wire_id >> 12
    event_size = 8 + words * 8
    assert offset + event_size <= len(data)
    payload = data[offset + 8:offset + event_size]
    params = struct.unpack("<" + "Q" * words, payload)
    events.append({
        "offset": offset,
        "id": wire_id & 0x0FFF,
        "count": count,
        "timestamp": timestamp,
        "params": params,
        "payload_hex": payload.hex(),
    })
    offset += event_size

counter_values = [e["params"][1] for e in events if e["id"] == 0x52]
cycle = [0x20, 0x25, 0x61, 0x52, 0x62, 0x25]
sequence_gaps = [
    (a["count"], b["count"])
    for a, b in zip(events, events[1:])
    if (b["count"] - a["count"]) % 65536 != 1
]
timestamp_regressions = [
    (a["timestamp"], b["timestamp"])
    for a, b in zip(events, events[1:])
    if b["timestamp"] < a["timestamp"]
]

print("event_count", len(events))
print("ids", dict(collections.Counter(hex(e["id"]) for e in events)))
print("full_eof", offset == len(data))
print("counter_0_to_49", counter_values == list(range(50)))
print("50_cycles_event_pattern", [e["id"] for e in events[9:]] == cycle * 50)
print("sequence_gaps", sequence_gaps)
print("timestamp_regressions", timestamp_regressions)
```

Probe 的無 gap／無倒退結論只適用這份 trace；它沒有測過 counter wrap 或 timestamp wrap。正式 parser 不應把一般事件是否倒退直接當作檔案毀損。

主代理重跑的完整輸出保存於 [desktop-psf-probe.log](desktop-psf-probe.log)，另有獨立 reviewer 執行同一探測方法；審查範圍見 [review 紀錄](review-record.md)。

## 7. Timestamp、loss 與 object lifecycle

### 7.1 Timestamp 的可用與不可用範圍

Timer types 1～6 見 [trcDefines.h](../../references/baseline/percepio/TraceRecorder/include/trcDefines.h) 第 17–22 行。實際讀取見 [trcTimestamp.c](../../references/baseline/percepio/TraceRecorder/trcTimestamp.c) 第 54–75 行。

| Timer | Writer 行為 | Parser 要注意 |
|---|---|---|
| Free-running／custom increment | 新值小於舊值時 wrap++ | 一次事件間隔跨多個 wrap 時不能僅靠比較完整還原 |
| Free-running／custom decrement | 新值大於舊值時 wrap++ | 方向不同，不能用 increment 公式 |
| OS timer | 低 24-bit counter 加上低 8-bit OS tick，wrap 欄位使用 OS tick count | 必須拆解 timer／tick，不能直接全部以 `TS / frequency` 換算 |

1 MHz 的 32-bit timer 約每 71.58 分鐘 wrap。Frequency 必須是實際 counter frequency；其正確性不能只靠 header 證明。Sleep、DVFS、重啟、SMP 的 clock domain／同步，需要額外 metadata 或受限假設。

如果遺失了會釐清時間或執行狀態的事件，衍生統計應標記 unknown interval。每秒 CPU 圖的分母應是有效觀測窗口，並說明 ISR、idle、startup、trace gaps 如何分類。

### 7.2 Loss／corruption

一般 event 沒有每筆 CRC 或 magic，長度依 EventID 高 bits 推導。Sequence gap 可協助發現 loss，但以下情況不能保證辨識：

- Bit flip 後仍是合法 EventID、參數或 timestamp。
- 正好移除整個 counter modulo 的事件數。
- 檔尾少了完整事件，剩餘檔案仍落在合法 event boundary。
- 收到有效檔頭，但停止時沒有送出預期尾端事件。

因此未來 harness 應由 test case 提供預期事件數、application end marker 或結果檔，並記錄 capture bytes／hash／正常退出狀態。不能只用「parser 沒報錯」作為資料完整的驗收。

同時區分 recorder buffer skip／overwrite、transport loss、host capture truncation。RAM event buffer 的定義包含 `uiDroppedEvents`，見 [trcEventBuffer.h](../../references/baseline/percepio/TraceRecorder/include/trcEventBuffer.h) 第 47–60 行；欄位存在本身不能證明所有路徑都正確累計。正式驗證還要核對初始化、累加路徑與 overflow 注入結果。

### 7.3 Object lifecycle

物件地址可能在 delete 後重用。Parser 宜以 session、handle 與生命週期一起識別物件，保留每次 create／delete／rename 的時間，而不是永遠把相同地址當成同一個 task。

主 SDK [trcObject.c](../../references/baseline/percepio/TraceRecorder/trcObject.c) 第 119–151 行先視配置送名稱，再送 delete event，最後刪除 entry。RingBuffer 設定 `TRC_SEND_NAME_ONLY_ON_DELETE=1`，會把仍存活的名稱放在 snapshot table，把已刪除的名稱補進 event history。Parser 要處理名字較晚出現、delete event 遺失、初始表與過去 event 名稱版本不同的狀況。

Unknown object 應保留 handle 與 unresolved 狀態。不能憑名稱猜測是哪個 task、queue 或 mutex。

## 8. Streaming PSF、RingBuffer dump 與 legacy snapshot

本次已確認桌面檔案是線性的 streaming file。RAM dump 的封裝不同。

| 輸入 | 結構 | 第一版 parser 的建議邊界 |
|---|---|---|
| Raw streaming file | header／timestamp／used entries／events | 可作第一個實作目標，需決定 32／64-bit 和 kernel schema |
| UART raw stream | 可能只是上述 bytes，被分段接收 | Collector 必須組合 bytes，保持 packet 與 event 邊界的區別；不要混入文字 log |
| ITM／SWO encoded stream | 多一層 transport 編碼 | 先做該 transport 解碼，不能直接當 raw PSF |
| RingBuffer memory dump | markers／header／timestamp／完整 table／每 core buffer controls／events | 需要另一個 frontend，解析有效範圍與 ring 順序 |
| Legacy snapshot protocol | 另一套 snapshot recorder／format | 不因副檔名相似就套入 format 14 streaming decoder |

主 SDK [RingBuffer header](../../references/baseline/percepio/TraceRecorder/streamports/RingBuffer/include/trcStreamPort.h) 第 25–74 行定義：

```text
reserved0
START_MARKERS[12]
TraceHeaderBuffer
TraceTimestampData
完整 TraceEntryTable
TraceMultiCoreBuffer：size + raw buffer area
END_MARKERS[12]
reserved1
```

每 core 的 event buffer control block 位於 raw buffer area，來源：[trcMultiCoreEventBuffer.c](../../references/baseline/percepio/TraceRecorder/trcMultiCoreEventBuffer.c) 第 27–42 行。Control block 的 head、tail、size、free/slack、pointer、timer wraps 見 [trcEventBuffer.h](../../references/baseline/percepio/TraceRecorder/include/trcEventBuffer.h) 第 47–60 行。

因此要依 snapshot 的 base-width、ABI、core count、buffer size、head/tail/slack 重排有效 events。START／END markers 可以協助定位；marker 出現不等於 snapshot 在寫入期間一致，還要凍結或建立一致性驗證。

現有 Auxon README 的「snapshot v7」與「stream v14」是分開的協議能力。不能推論它自然支援我們 v4.12.0 RingBuffer memory dump。

## 9. 既有免費 parser 與來源限制

### 9.1 Auxon trace-recorder-parser

[Repository](https://github.com/auxoncorp/trace-recorder-parser)；[固定 commit README](https://github.com/auxoncorp/trace-recorder-parser/blob/21f8914dc55e45a7f96bf07cc56a51f6cdc01af9/README.md)。查核 commit：`21f8914dc55e45a7f96bf07cc56a51f6cdc01af9`。

README 宣告 Apache-2.0，支援 FreeRTOS snapshot v7 與 streaming v10、v12～v14。這是作者聲明的範圍，沒有在本次執行它。

**其 source 明確假設 32-bit，不能直接作為目前桌面 64-bit 自訂 kernel 的 oracle。**[Timestamp reader](https://github.com/auxoncorp/trace-recorder-parser/blob/21f8914dc55e45a7f96bf07cc56a51f6cdc01af9/src/streaming/timestamp_info.rs#L29) 的兩個 version 分支都註明 32-bit；[entry reader](https://github.com/auxoncorp/trace-recorder-parser/blob/21f8914dc55e45a7f96bf07cc56a51f6cdc01af9/src/streaming/entry_table.rs#L140) 讀取 32-bit entry header／address／states。

它有 header、timestamp、entry、event、error 模組，可作為獨立實作參考。主要限制還包括 FreeRTOS event semantics、部分 unknown events 與 format 差異。後續可以評估用它對照 RV32 FreeRTOS stream，仍需固定版本並查驗 v4.12.0 的新增事件。[Header reader](https://github.com/auxoncorp/trace-recorder-parser/blob/21f8914dc55e45a7f96bf07cc56a51f6cdc01af9/src/streaming/header_info.rs)、[event reader](https://github.com/auxoncorp/trace-recorder-parser/blob/21f8914dc55e45a7f96bf07cc56a51f6cdc01af9/src/streaming/event/parser.rs)

### 9.2 trace-recorder-to-ctf

[作者 repository](https://github.com/jonlamb-gh/trace-recorder-to-ctf) 說明將 FreeRTOS streaming trace 轉成 LTTng-shaped CTF，再由 Trace Compass／babeltrace2 顯示；授權為 MIT。它映射部分 scheduler 與 ISR events，其他事件可能保留 UNKNOWN。這提供另一種免費觀察路徑，但不等於全部 Tracealyzer 功能，也未證明適用桌面 `my_krnl` 或本次 RingBuffer dump。

### 9.3 官方公開來源

- [Percepio TraceRecorderSource](https://github.com/percepio/TraceRecorderSource)：recorder source 入口；本文具體 layout 仍以本地 v4.12.0 為準。
- [Percepio SDK demos](https://github.com/percepio/Tracealyzer-SDK-demos)：桌面自訂事件與 XML 的來源。
- [TraceRecorder API Reference](https://percepio.github.io/TraceRecorderSource/)：API 查詢入口，需對照本地版本。
- [TraceRecorder Integration Guide](https://percepio.com/TracealyzerSDK/TraceRecorder_Integration_Guide.pdf)：官方整合資料；binary layout 的精確來源仍是 writer source。
- [XMOS Tracealyzer example](https://www.xmos.com/documentation/XM-014926-PC/html/doc/programming_guide/tutorials/freertos/examples/tracealyzer.html)：官方稱 `.psf` 為 Percepio Streaming Format，範例顯示 format `0x000A` 與 header／timestamp 欄位，提醒舊版本另有布局。

沒有找到可取代版本化 writer source 的通用、完整 PSF 規格文件。因此不宣稱本文是所有版本的官方格式規範。

## 10. Parser 與 unittest 的建議驗收

以下為**待實作的測試需求**，不是已執行的測試結果。應先經設計確認，再建立正式 decoder／harness。

| 類別 | 應覆蓋的輸入 | 預期驗收 |
|---|---|---|
| Header | little／big endian、32／64-bit、未知版本、未知 platform、錯誤 magic | 正確派送；不支援時回傳具體錯誤／限制 |
| Metadata | frequency 0、異常 symbol size／entry count、states count、截斷欄位 | 有長度與配置上限；不無限制配置記憶體 |
| Event framing | 0／1／多 word、inline string、最大 blob、非法參數數量 | Offset 與原始 bytes 可追查；欄位依 schema 驗證 |
| Truncation | Header、timestamp、entry、8-byte event header、payload 各位置截斷 | 區分乾淨 EOF 與 partial record，指出 offset |
| Counter | 16-bit wrap、12-bit per-core wrap、gap、counter reset | 正確 modulo；按 core／session 解讀 |
| Timestamp | 相同 TS、increment／decrement、一次 wrap、多 wrap 的未知間隔、OS timer | 合法情況不誤報；缺乏證據時標記不確定 |
| Sessions | 重啟 header、多 session concatenation、garbage prefix | 依已確認策略分段；不把 restart 混入排程 |
| Objects | Rename、delete、地址重用、名稱晚到、未知 handle | 保留生命週期；不混淆歷史名稱與物件 |
| User Events | inline／fixed／compact，負值、格式字串、缺少 string handle／ELF | 不執行輸入內容；未解決的參數保留 raw |
| Unknown／corrupt | 未知合法 ID、长度誤寫、參數 bit flip、完整事件遺失 | 保留 raw／品質狀態；不宣稱可偵測所有 corruption |
| Snapshot | 若納入：head/tail、slack、wrap、skip/overwrite、SMP、markers、ABI | 先建立獨立 snapshot frontend 的 oracle |
| JSON | 64-bit handle、長時間 timestamp、raw／derived 欄位 | JavaScript 不損失整數精度；schema version 固定 |

JavaScript 一般 Number 無法精確表達全部 64-bit 整數。若 JSON 要輸入 HTML Dashboard，64-bit handle 宜採明確的十六進位／十進位字串，或另訂 BigInt 解碼契約。這是設計建議，尚未決定 schema。

### 10.1 獨立 oracle

至少分成三層，避免 decoder 自己產生 expected JSON，再拿自己驗證自己：

1. **現有桌面 source oracle：**`main.c`、XML、50 次 cycle、Counter 0～49、309 events、EOF 7152。這份檔案可作 decoder regression fixture。
2. **第三方固定 fixtures：**Auxon [tests/streaming.rs](https://github.com/auxoncorp/trace-recorder-parser/blob/21f8914dc55e45a7f96bf07cc56a51f6cdc01af9/tests/streaming.rs) 與 [fixtures](https://github.com/auxoncorp/trace-recorder-parser/tree/21f8914dc55e45a7f96bf07cc56a51f6cdc01af9/test_resources/fixtures/streaming) 包含 v10／v12／v13／v14、逐事件 counter／timestamp 預期，以及 garbage prefix／restart 案例。它們提供獨立 binary 輸入，32-bit／FreeRTOS 條件仍需明示。
3. **新 FreeRTOS 應用 oracle：**test case 在 trace 以外記錄 message ID、producer／consumer 計數、成功／timeout、deadline、正常結束結果。再對照 PSF，不用 PSF 當唯一真相。

Simulator 可驗證 event order、FreeRTOS API 行為與資料管線。真實 UART throughput、板上 interrupt latency、DMA成本與 CPU overhead 仍需實體板驗證。

## 11. 工程建議與設計範圍

| 分支 | 已知事實 | 建議選項，尚未視為已同意 |
|---|---|---|
| 第一版格式 | 主 SDK 與桌面都是 v14，base-width／kernel 不同 | 先 RV32 FreeRTOS stream；桌面 64-bit 當另一個明確 schema |
| Snapshot | RAM dump 需要額外 ring／ABI／core 重排 | 第一階段延後，另立 snapshot decoder 驗收 |
| 錯誤策略 | 缺漏會影響排程與 CPU 衍生統計 | Harness 使用 strict；Dashboard 可有明示缺漏的 partial view |
| JSON | raw／semantic／derived 需要不同可信度 | 保留 offset／raw bytes／schema／品質狀態，衍生統計附有效窗口 |
| 差異比對 | Auxon 適合部分 32-bit FreeRTOS stream | 固定 commit 作獨立比對；不套用桌面 schema |
| CPU 統計目的 | 模擬 timing 與實體 CPU overhead 不同 | 模擬驗證解析與行為；板上成本另量測 |

具體範圍集中於 [POC 設計規格](../design/PSF-Lab-設計規格.md)。工程選擇由 agent 提出並驗證。目前文件中的具體 layout 與 probe 結果可以接續使用，沒有把尚未執行的設計當作完成結果。
