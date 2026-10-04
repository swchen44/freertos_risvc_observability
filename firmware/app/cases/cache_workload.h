#include "case_api.h"
#include "oracle.h"

/* Input and workload are identical; only traversal order changes. */
volatile uint32_t cache_matrix[64][64] __attribute__((aligned(64)));
__attribute__((noinline)) void cache_work(void) {
 for (unsigned pass=0; pass<2; pass++)
  for (unsigned outer=0; outer<64; outer++)
   for (unsigned inner=0; inner<64; inner++) {
#if CACHE_COLUMN
    cache_matrix[inner][outer] += 1;
#else
    cache_matrix[outer][inner] += 1;
#endif
   }
}
static void cache_task(void *arg) {
 (void)arg;
 for(unsigned i=0;i<64;i++)
  for(unsigned j=0;j<64;j++) cache_matrix[i][j]=i*64+j;
 poc_mark("CACHE_BEGIN",0);
 cache_work();
 poc_mark("CACHE_END",0);
 uint32_t checksum=0;
 for(unsigned i=0;i<64;i++)
  for(unsigned j=0;j<64;j++) checksum+=cache_matrix[i][j];
 configASSERT(checksum==8394752u);
 poc_sent[poc_sent_count++]=checksum;
 poc_received[poc_received_count++]=checksum;
 poc_oracle_finish();
}
void poc_case_run(void) {
 configASSERT(xTaskCreate(cache_task,"cache_work",1024,NULL,2,NULL)==pdPASS);
}
