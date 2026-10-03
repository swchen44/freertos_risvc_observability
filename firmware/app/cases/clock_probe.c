#include "case_api.h"
#include "oracle.h"
#include "recorder_port.h"
static void probe(void *arg) {
 (void)arg;
 uint32_t outer=poc_irq_save(),inner=poc_irq_save();poc_irq_restore(inner);
 uint32_t now;__asm__ volatile("csrr %0,mstatus":"=r"(now));
 poc_irq_restore_ok=(now&8)==0;poc_irq_restore(outer);
 uint32_t tick=xTaskGetTickCount();uint64_t start=poc_mtime();
 vTaskDelay(100);
 poc_delta_ticks=xTaskGetTickCount()-tick;poc_delta_mtime=(uint32_t)(poc_mtime()-start);
 poc_oracle_finish();
}
void poc_case_run(void) {configASSERT(xTaskCreate(probe,"clock_probe",1024,NULL,5,NULL)==pdPASS);}
