/* T2a: controlled virtual-time jump with interrupts and scheduling enabled. */
#include "case_api.h"
#include "oracle.h"
#include "stream_io.h"
#include <stdio.h>

static volatile unsigned observer_woke;
static volatile uint32_t work;
static uint64_t observer_mtime;
static char output[1024];

__attribute__((noinline)) void time_probe_charge(void) { __asm__ volatile("nop":::"memory"); }
static void observer(void *arg) {
 (void)arg;vTaskDelay(2);
 observer_mtime=poc_mtime();observer_woke=1;vTaskSuspend(NULL);
}
static void worker(void *arg) {
 (void)arg;poc_mark("TIME_PROBE_BEGIN",0);
 uint32_t tick=xTaskGetTickCount();uint64_t before=poc_mtime();
 time_probe_charge();
 uint64_t immediate=poc_mtime();
 for(unsigned i=0;i<1024;i++) { work+=i; __asm__ volatile("nop":::"memory"); }
 uint64_t after=poc_mtime();uint32_t ticks=xTaskGetTickCount()-tick;
 unsigned woke=observer_woke;
 poc_mark("TIME_PROBE_END",0);
 int n=snprintf(output,sizeof output,"{\"case\":\"time_control_probe\",\"mtime_hz\":10000000,\"tick_hz\":1000,\"delta_mtime\":%u,\"immediate_mtime\":%u,\"delta_ticks\":%u,\"observer_woke\":%s,\"observer_mtime\":%u,\"before_mtime\":%u,\"work\":%u}\n",
  (unsigned)(after-before),(unsigned)(immediate-before),ticks,woke?"true":"false",(unsigned)observer_mtime,(unsigned)before,(unsigned)work);
 configASSERT(n>0&&n<(int)sizeof output&&work==523776);
 int fd=poc_sh_open("time-probe.json");configASSERT(fd>=0&&poc_write_all(fd,output,n)==0&&poc_sh_close(fd)==0);
 poc_oracle_finish();
}
void poc_case_run(void) {
 configASSERT(xTaskCreate(observer,"time_observer",1024,NULL,3,NULL)==pdPASS);
 configASSERT(xTaskCreate(worker,"time_worker",1024,NULL,2,NULL)==pdPASS);
}
