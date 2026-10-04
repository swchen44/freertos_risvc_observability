/* Fixed cold-window cache probe. Runs before scheduler/timer startup. */
#include "case_api.h"
#include "oracle.h"
#include "stream_io.h"
#include <stdio.h>
static volatile uint32_t data[10240] __attribute__((aligned(64)));
static char output[600];
__attribute__((noinline)) void live_cache_begin(void) {__asm__ volatile("nop":::"memory");}
__attribute__((noinline)) void live_cache_end(void) {__asm__ volatile("nop":::"memory");}
void poc_case_run(void) {
 unsigned work=0;
 for(unsigned i=0;i<10240;i++) data[i]=i;
 poc_mark("CACHE_BEGIN",0);
 uint32_t tick=xTaskGetTickCount(),before=(uint32_t)poc_mtime();
 live_cache_begin();
 for(unsigned round=0;round<4;round++) {
  for(unsigned i=0;i<10240;i+=16) {unsigned v=data[i];work+=v;data[i]=v+1;}
 }
 live_cache_end();
 /* Drain pending async callbacks outside the charged window. */
 for(volatile unsigned k=0;k<32;k++) __asm__ volatile("nop":::"memory");
 uint32_t after=(uint32_t)poc_mtime(),ticks=xTaskGetTickCount()-tick;
 poc_mark("CACHE_END",0);
 configASSERT(work==13090560);
 int n=snprintf(output,sizeof output,
  "{\"case\":\"live_cache\",\"before\":%u,\"after\":%u,\"ticks\":%u,\"work\":%u}\n",
  before,after,ticks,work);
 configASSERT(n>0&&n<(int)sizeof output);
 int fd=poc_sh_open("live-cache.json");
 configASSERT(fd>=0&&poc_write_all(fd,output,n)==0&&poc_sh_close(fd)==0);
 poc_oracle_finish();
}
