/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef POC_LIVE_TIMING_H
#define POC_LIVE_TIMING_H
#include <stdint.h>
/* Fixed sysram-10 profile: 16K/16K/64K, 64B lines, 4-way LRU, WT+WA.
 * Output order: l1i, l1d, l2, ram_read, ram_write; single vCPU only. */
void timing_reset(void);
int timing_access(uint64_t address, unsigned size, char operation, uint64_t costs[5]);
#endif
