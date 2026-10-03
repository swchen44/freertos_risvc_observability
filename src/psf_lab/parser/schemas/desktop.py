"""my_krnl-v1.0.0.xml and the bundled GCC demo's trcKernelPort.h."""

KEY = (0x1FF1, "my_krnl", "1.0.0", 8)
KINDS = {
    0x00: "null",
    0x01: "trace_start",
    0x02: "timestamp_config",
    0x03: "object_name",
    0x04: "task_priority",
    0x10: "task_create",
    0x11: "task_delete",
    0x20: "task_ready",
    0x21: "isr_begin",
    0x22: "isr_resume",
    0x23: "task_switch",
    0x24: "task_switch",
    0x25: "task_switch",
    0x60: "mutex_create",
    0x61: "mutex_take",
    0x62: "mutex_give",
}
USER_BASE = 0x50
FIXED_BASE = 0x58
