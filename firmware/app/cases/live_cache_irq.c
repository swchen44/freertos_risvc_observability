/* Live-cost IRQ probe: high priority observer wakes during fixed worker work. */
#include "case_api.h"
#include "oracle.h"
#include "stream_io.h"
#include <stdio.h>
static volatile uint32_t data[10240] __attribute__((aligned(64)));
static volatile unsigned woke,observer_tick,observer_mtime;
static char output[1000];
__attribute__((noinline)) void live_cache_begin(void) {__asm__ volatile("nop":::"memory");}
__attribute__((noinline)) void live_cache_end(void) {__asm__ volatile("nop":::"memory");}
static void observer(void *arg) {
 (void)arg;vTaskDelay(2);
 observer_tick=xTaskGetTickCount();observer_mtime=(uint32_t)poc_mtime();woke=1;
 poc_mark("IRQ_OBSERVER",observer_tick);vTaskSuspend(NULL);
}
static void worker(void *arg) {
 (void)arg;unsigned work=0;
 for(unsigned i=0;i<10240;i++) data[i]=i;
 poc_mark("IRQ_CACHE_BEGIN",0);
 uint32_t mask=poc_irq_save();
 uint32_t tick=xTaskGetTickCount(),before=(uint32_t)poc_mtime();
 live_cache_begin();poc_irq_restore(mask);
 for(unsigned round=0;round<64;round++) {
  for(unsigned i=0;i<10240;i+=16) {unsigned v=data[i];work+=v;data[i]=v+1;}
 }
 mask=poc_irq_save();live_cache_end();
 for(volatile unsigned k=0;k<32;k++) __asm__ volatile("nop":::"memory");
 uint32_t after=(uint32_t)poc_mtime(),ticks=xTaskGetTickCount()-tick;
 unsigned captured_woke=woke,captured_tick=observer_tick,captured_mtime=observer_mtime;
 poc_irq_restore(mask);poc_mark("IRQ_CACHE_END",0);
 configASSERT(work==210677760);
 int n=snprintf(output,sizeof output,
  "{\"case\":\"live_cache_irq\",\"before\":%u,\"after\":%u,\"before_tick\":%u,\"ticks\":%u,\"work\":%u,\"woke\":%u,\"observer_tick\":%u,\"observer_mtime\":%u}\n",
  before,after,tick,ticks,work,captured_woke,captured_tick,captured_mtime);
 configASSERT(n>0&&n<(int)sizeof output);
 int fd=poc_sh_open("live-cache.json");
 configASSERT(fd>=0&&poc_write_all(fd,output,n)==0&&poc_sh_close(fd)==0);
 poc_oracle_finish();
}
void poc_case_run(void) {
 configASSERT(xTaskCreate(observer,"cache_observer",1024,NULL,3,NULL)==pdPASS);
 configASSERT(xTaskCreate(worker,"cache_worker",2048,NULL,2,NULL)==pdPASS);
}
