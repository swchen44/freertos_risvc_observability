#include "case_api.h"
#include "oracle.h"
#include "queue.h"
static QueueHandle_t queue;
static void producer(void *arg) {
 (void)arg;
 for(unsigned i=0;i<16;i++) {
  configASSERT(xQueueSend(queue,&i,100)==pdPASS);
  poc_sent[poc_sent_count++]=i;poc_mark("SEND",i);
  vTaskDelay(1);
 }
 vTaskSuspend(NULL);
}
static void consumer(void *arg) {
 (void)arg;unsigned value;
 for(unsigned i=0;i<16;i++) {
  configASSERT(xQueueReceive(queue,&value,100)==pdPASS);
  poc_received[poc_received_count++]=value;poc_mark("RECEIVE",value);
 }
 vTaskSuspend(NULL);
}
static void supervisor(void *arg) {
 (void)arg;
 for(unsigned i=0;i<100;i++) {
  vTaskDelay(1);
  if(poc_sent_count==16 && poc_received_count==16) poc_oracle_finish();
 }
 poc_console("queue deadline\n");poc_finish(0);
}
void poc_case_run(void) {
 queue=xQueueCreate(4,sizeof(unsigned));configASSERT(queue);
 vQueueAddToRegistry(queue,"messages");
 configASSERT(xTaskCreate(producer,"producer",512,NULL,2,NULL)==pdPASS);
 configASSERT(xTaskCreate(consumer,"consumer",512,NULL,3,NULL)==pdPASS);
 configASSERT(xTaskCreate(supervisor,"supervisor",1024,NULL,5,NULL)==pdPASS);
}
