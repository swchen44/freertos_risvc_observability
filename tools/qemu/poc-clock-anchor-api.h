#ifndef POC_CLOCK_ANCHOR_API_H
#define POC_CLOCK_ANCHOR_API_H
#include <stdint.h>
#include <stdbool.h>

/* POC host ABI v1, separate from upstream QEMU plugin API version 4. */
typedef struct PocClockConfig {
    uint32_t struct_size, abi_version, observer_enabled, injection_enabled;
    uint32_t marker_mode, expected_frequency_hz;
    const char *path, *run_id, *configuration;
    const char *qemu_sha256, *elf_sha256, *profile_sha256, *plugin_sha256;
} PocClockConfig;
typedef struct PocClockNote {
    uint32_t struct_size, kind;
    uint64_t raw_cursor, pc;
    uint32_t marker_seq, marker_phase;
    uint64_t sample64, address;
    uint32_t access_size, is_store;
} PocClockNote;
enum PocClockNoteKind {
    POC_CLOCK_BEGIN=1, POC_CLOCK_RAW_I=2, POC_CLOCK_RAW_R=3, POC_CLOCK_RAW_W=4,
    POC_CLOCK_ENTER=5, POC_CLOCK_SAMPLED=6, POC_CLOCK_LEAVE=7,
    POC_CLOCK_END=8, POC_CLOCK_MMIO_SUCCESS=9
};
bool qemu_plugin_poc_clock_configure(const void *, const PocClockConfig *);
void qemu_plugin_poc_clock_note(const void *, const PocClockNote *);
void qemu_plugin_poc_add_ns_tagged(const void *, uint64_t, uint64_t, uint64_t);
bool qemu_plugin_poc_clock_finish(const void *, uint64_t);
#endif
