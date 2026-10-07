#ifndef POC_LIVE_CONTEXT_H
#define POC_LIVE_CONTEXT_H
#include <qemu-plugin.h>
#include <stdint.h>
int context_init(const char *config, const char *output);
void context_vcpu_init(qemu_plugin_id_t id, unsigned cpu);
void context_before_instruction(uint64_t raw_index, uint64_t pc);
void context_after_instruction(uint64_t raw_index, uint64_t pc);
int context_needs_registers(uint64_t pc);
int context_finish(uint64_t raw_events);
#endif
