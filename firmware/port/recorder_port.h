#pragma once
#include "clock.h"
static inline uint32_t poc_irq_save(void) {
 uint32_t old; __asm__ volatile("csrrci %0,mstatus,8" : "=r"(old) :: "memory"); return old;
}
static inline void poc_irq_restore(uint32_t old) {
 if(old&8) __asm__ volatile("csrsi mstatus,8" ::: "memory");
 else __asm__ volatile("csrci mstatus,8" ::: "memory");
}
#define TRC_HWTC_TYPE TRC_FREE_RUNNING_32BIT_INCR
#define TRC_HWTC_COUNT ((uint32_t)poc_mtime())
#define TRC_HWTC_PERIOD 0
#define TRC_HWTC_DIVISOR 1
#define TRC_HWTC_FREQ_HZ 10000000UL
#define TRC_IRQ_PRIORITY_ORDER 1
#define TRC_CFG_ALLOC_CRITICAL_SECTION() uint32_t poc_saved_irq;
#define TRC_CFG_ENTER_CRITICAL_SECTION() do { poc_saved_irq=poc_irq_save(); } while(0)
#define TRC_CFG_EXIT_CRITICAL_SECTION() do { poc_irq_restore(poc_saved_irq); } while(0)
