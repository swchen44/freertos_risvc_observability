#ifndef POC_PLUGIN_CLOCK_ANCHOR_H
#define POC_PLUGIN_CLOCK_ANCHOR_H
#include <qemu-plugin.h>
#include <stdbool.h>
#include <stdint.h>
int clock_anchor_init(const char *, const void *, uint64_t, uint64_t);
bool clock_anchor_needs_registers(uint64_t);
void clock_anchor_vcpu_init(qemu_plugin_id_t, unsigned);
int clock_anchor_before(uint64_t, uint64_t);
int clock_anchor_after_row(uint64_t, uint64_t, char);
int clock_anchor_mmio_success(uint64_t, uint64_t, uint64_t, unsigned, unsigned);
int clock_anchor_finish(uint64_t);
#endif
