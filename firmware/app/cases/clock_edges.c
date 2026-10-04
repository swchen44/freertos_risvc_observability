/* Boundary probe: no timer, repeated/stale targets, IRQ mask and WFI. */
#include "case_api.h"
#include "oracle.h"
#include "stream_io.h"
#include <stdio.h>

static struct { uint32_t before_mtime,after_mtime,before_tick,after_tick; } phases[5];
static volatile unsigned observer_woke;
static unsigned pending,restored_ticks,restored_observer,wfi_time,wfi_ticks;
static char output[2048];
/* Four explicit RV32 ABI arguments, consumed by the plugin at function entry. */
__attribute__((noinline)) void clock_edge_request(uint32_t low,uint32_t high,uint32_t delay,unsigned id) {
 __asm__ volatile("nop" :: "r"(low),"r"(high),"r"(delay),"r"(id) : "memory");
}
static void settle(void) {
 for(volatile unsigned i=0;i<512;i++) __asm__ volatile("nop" ::: "memory");
}
static void measure(unsigned id,unsigned delay) {
 poc_mark("CLOCK_EDGE_BEGIN",id);
 phases[id].before_tick=xTaskGetTickCount();
 uint64_t t=poc_mtime();phases[id].before_mtime=(uint32_t)t;
 uint64_t ns=t*100;
 clock_edge_request((uint32_t)ns,(uint32_t)(ns>>32),delay,id);
 settle();
 phases[id].after_mtime=(uint32_t)poc_mtime();
 phases[id].after_tick=xTaskGetTickCount();
 poc_mark("CLOCK_EDGE_END",id);
}
static void observer(void *arg) {
 (void)arg;vTaskDelay(2);observer_woke=1;vTaskSuspend(NULL);
}
static void worker(void *arg) {
 (void)arg;
 uint32_t mask=poc_irq_save();
 unsigned tick=xTaskGetTickCount();
 measure(3,3000000);
 uint32_t mip;__asm__ volatile("csrr %0,mip":"=r"(mip));pending=(mip&128)!=0;
 poc_irq_restore(mask);settle();
 restored_ticks=xTaskGetTickCount()-tick;restored_observer=observer_woke;
 poc_mark("CLOCK_WFI_BEGIN",0);
 tick=xTaskGetTickCount();uint64_t before=poc_mtime();
 __asm__ volatile("wfi" ::: "memory");settle();
 wfi_time=(uint32_t)(poc_mtime()-before);wfi_ticks=xTaskGetTickCount()-tick;
 poc_mark("CLOCK_WFI_END",0);
 measure(4,1000000);
 int n=snprintf(output,sizeof output,"{\"case\":\"clock_edges\",\"phases\":[");
 for(unsigned i=0;i<5;i++) n+=snprintf(output+n,sizeof(output)-n,
  "%s{\"id\":%u,\"before_mtime\":%u,\"after_mtime\":%u,\"before_tick\":%u,\"after_tick\":%u}",
  i?",":"",i,phases[i].before_mtime,phases[i].after_mtime,phases[i].before_tick,phases[i].after_tick);
 n+=snprintf(output+n,sizeof(output)-n,"],\"masked_pending\":%s,\"restored_tick_delta\":%u,\"observer_after_restore\":%s,\"wfi_delta_mtime\":%u,\"wfi_tick_delta\":%u}\n",
  pending?"true":"false",restored_ticks,restored_observer?"true":"false",wfi_time,wfi_ticks);
 configASSERT(n>0&&n<(int)sizeof output);
 int fd=poc_sh_open("clock-edges.json");configASSERT(fd>=0&&poc_write_all(fd,output,n)==0&&poc_sh_close(fd)==0);
 poc_oracle_finish();
}
void poc_case_run(void) {
 /* Before scheduler startup, no FreeRTOS timer is armed. */
 measure(0,1000000);measure(1,2000000);measure(2,0);
 configASSERT(xTaskCreate(observer,"edge_observer",1024,NULL,3,NULL)==pdPASS);
 configASSERT(xTaskCreate(worker,"edge_worker",1024,NULL,2,NULL)==pdPASS);
}
