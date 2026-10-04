#include "case_api.h"
#include "oracle.h"

/* 16 KiB in every variant. Two hot fields and fourteen unchanged cold fields. */
#if CACHE_LAYOUT == 0
struct Record { uint32_t x, y, cold[14]; };
volatile struct Record cache_records[256] __attribute__((aligned(64)));
#define X(i) cache_records[i].x
#define Y(i) cache_records[i].y
#define COLD(i,j) cache_records[i].cold[j]
#elif CACHE_LAYOUT == 1
volatile struct { uint32_t x[256], y[256], cold[256][14]; }
 cache_records __attribute__((aligned(64)));
#define X(i) cache_records.x[i]
#define Y(i) cache_records.y[i]
#define COLD(i,j) cache_records.cold[i][j]
#else
struct Hot { uint32_t x, y; };
volatile struct { struct Hot hot[256]; uint32_t cold[256][14]; }
 cache_records __attribute__((aligned(64)));
#define X(i) cache_records.hot[i].x
#define Y(i) cache_records.hot[i].y
#define COLD(i,j) cache_records.cold[i][j]
#endif
_Static_assert(sizeof(cache_records)==16384, "same allocated bytes required");

__attribute__((noinline)) void cache_work(void) {
 for(unsigned pass=0;pass<2;pass++)
  for(unsigned i=0;i<256;i++) { X(i)+=1; Y(i)+=1; }
}
static void cache_task(void *arg) {
 (void)arg;
 for(unsigned i=0;i<256;i++) {
  X(i)=i;Y(i)=3*i;
  for(unsigned j=0;j<14;j++) COLD(i,j)=i*16+j;
 }
 poc_mark("CACHE_BEGIN",0);
 cache_work();
 poc_mark("CACHE_END",0);
 uint32_t hot_checksum=0,cold_checksum=0;
 for(unsigned i=0;i<256;i++) {
  configASSERT(X(i)==i+2 && Y(i)==3*i+2);
  hot_checksum+=X(i)+Y(i);
  for(unsigned j=0;j<14;j++) {
   configASSERT(COLD(i,j)==i*16+j);
   cold_checksum+=COLD(i,j);
  }
 }
 configASSERT(hot_checksum==131584u && cold_checksum==7334656u);
 poc_sent[poc_sent_count++]=hot_checksum;
 poc_sent[poc_sent_count++]=cold_checksum;
 poc_received[poc_received_count++]=hot_checksum;
 poc_received[poc_received_count++]=cold_checksum;
 poc_oracle_finish();
}
void poc_case_run(void) {
 configASSERT(xTaskCreate(cache_task,"cache_work",1024,NULL,2,NULL)==pdPASS);
}
