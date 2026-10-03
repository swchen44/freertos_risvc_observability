#include "trcRecorder.h"
#include "semihost.h"
#include "stream_io.h"
static int fd=-1;
int poc_transport_ok=1;
static void failed(void) {poc_transport_ok=0;poc_console("capture transport failure\n");poc_finish(0);}
traceResult xTraceStreamPortInitialize(TraceStreamPortBuffer_t *p) {p->fd=-1; return TRC_SUCCESS;}
traceResult xTraceStreamPortOnTraceBegin(void) {fd=poc_sh_open("trace.psf");if(fd<0) failed();return TRC_SUCCESS;}
traceResult xTraceStreamPortOnTraceEnd(void) {if(fd>=0 && poc_sh_close(fd)!=0) failed();fd=-1;return TRC_SUCCESS;}
traceResult xTraceStreamPortWriteData(void *data,uint32_t size,uint32_t channel,int32_t *written) {
 *written=0;
 if(channel!=0 || fd<0 || poc_write_all(fd,data,size)!=0) failed();
 *written=(int32_t)size;return TRC_SUCCESS;
}
traceResult xTraceStreamPortReadData(void *p,uint32_t size,int32_t *read) {(void)p;(void)size;*read=0;return TRC_SUCCESS;}
