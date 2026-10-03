#pragma once
#include <stdint.h>
extern unsigned poc_sent[16],poc_received[16],poc_sent_count,poc_received_count;
extern uint32_t poc_delta_ticks,poc_delta_mtime;
extern int poc_irq_restore_ok;
void poc_oracle_finish(void);
