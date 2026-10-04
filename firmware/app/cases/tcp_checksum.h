#include "case_api.h"
#include "oracle.h"
#include "stream_io.h"
#include "lwip/inet_chksum.h"
#include "lwip/def.h"
#include <stdio.h>

static uint8_t payload[8196] __attribute__((aligned(64)));
static char report[8192];
static volatile unsigned checksum_sink;
static inline uint32_t instructions(void) {
 uint32_t value;
 __asm__ volatile("rdinstret %0" : "=r"(value) :: "memory");
 return value;
}
static uint16_t reference_sum(const uint8_t *p,unsigned length) {
 uint32_t sum=0;
 for(unsigned i=0;i<length;i+=2) sum+=((uint32_t)p[i]<<8)+(i+1<length?p[i+1]:0);
 while(sum>>16) sum=(sum&65535)+(sum>>16);
 return (uint16_t)~sum;
}
static void checksum_task(void *arg) {
 (void)arg;
 const unsigned lengths[]={20,64,511,1460,1461,8192};
 for(unsigned i=0;i<sizeof payload;i++) payload[i]=(uint8_t)(i*17+31);
 int n=snprintf(report,sizeof report,"{\"algorithm\":%u,\"repetitions\":32,\"metric\":\"qemu_instret_delta\",\"measurements\":[",LWIP_CHKSUM_ALGORITHM);
 unsigned id=0;
 for(unsigned k=0;k<6;k++) for(unsigned offset=0;offset<2;offset++) {
  unsigned length=lengths[k];
  uint16_t expected=reference_sum(payload+offset,length);
  configASSERT(lwip_ntohs(inet_chksum(payload+offset,length))==expected);
  poc_mark("CHECKSUM_BEGIN",id);
  taskENTER_CRITICAL();
  uint32_t begin=instructions();
  for(unsigned r=0;r<32;r++) checksum_sink=inet_chksum(payload+offset,length);
  uint32_t elapsed=instructions()-begin;
  taskEXIT_CRITICAL();
  poc_mark("CHECKSUM_END",id);
  unsigned actual=lwip_ntohs((uint16_t)checksum_sink);
  configASSERT(actual==expected);
  poc_sent[poc_sent_count++]=expected;
  poc_received[poc_received_count++]=actual;
  n+=snprintf(report+n,sizeof(report)-n,"%s{\"length\":%u,\"offset\":%u,\"checksum\":%u,\"instructions\":%u}",id?",":"",length,offset,actual,elapsed);
  id++;
 }
 n+=snprintf(report+n,sizeof(report)-n,"]}\n");
 configASSERT(n>0 && n<(int)sizeof(report));
 int fd=poc_sh_open("tcp.json");
 configASSERT(fd>=0 && poc_write_all(fd,report,n)==0 && poc_sh_close(fd)==0);
 poc_oracle_finish();
}
void poc_case_run(void) {
 configASSERT(xTaskCreate(checksum_task,"checksum",1024,NULL,2,NULL)==pdPASS);
}
