/* 1000 repeated requests per delay, before scheduler/timer startup. */
#include "case_api.h"
#include "oracle.h"
#include "stream_io.h"
#include <stdio.h>
static const unsigned delays[5]={10,20,50,100,1000};
static uint32_t before[5],after[5],ticks[5];
static char output[1200];
__attribute__((noinline)) void clock_nano_request(uint32_t low,uint32_t high,unsigned delay,unsigned id) {
 __asm__ volatile("nop" :: "r"(low),"r"(high),"r"(delay),"r"(id) : "memory");
}
__attribute__((noinline)) void clock_nano_begin(unsigned id) {__asm__ volatile("nop" :: "r"(id) : "memory");}
__attribute__((noinline)) void clock_nano_end(unsigned id) {__asm__ volatile("nop" :: "r"(id) : "memory");}
void poc_case_run(void) {
 for(unsigned id=0;id<5;id++) {
  poc_mark("NANO_BEGIN",id);
  unsigned tick=xTaskGetTickCount();
  clock_nano_begin(id);before[id]=(uint32_t)poc_mtime();
  for(unsigned n=0;n<1000;n++) {
   uint64_t ns=poc_mtime()*100;
   clock_nano_request((uint32_t)ns,(uint32_t)(ns>>32),delays[id],id);
   /* A bounded loop gives async work a chance to run before the next request. */
   for(volatile unsigned k=0;k<16;k++) __asm__ volatile("nop" ::: "memory");
  }
  after[id]=(uint32_t)poc_mtime();clock_nano_end(id);
  ticks[id]=xTaskGetTickCount()-tick;poc_mark("NANO_END",id);
 }
 int n=snprintf(output,sizeof output,"{\"case\":\"clock_nano\",\"phases\":[");
 for(unsigned i=0;i<5;i++) n+=snprintf(output+n,sizeof(output)-n,
  "%s{\"id\":%u,\"delay_ns\":%u,\"repeats\":1000,\"before\":%u,\"after\":%u,\"ticks\":%u}",
  i?",":"",i,delays[i],before[i],after[i],ticks[i]);
 n+=snprintf(output+n,sizeof(output)-n,"]}\n");configASSERT(n>0&&n<(int)sizeof output);
 int fd=poc_sh_open("clock-nano.json");configASSERT(fd>=0&&poc_write_all(fd,output,n)==0&&poc_sh_close(fd)==0);
 poc_oracle_finish();
}
