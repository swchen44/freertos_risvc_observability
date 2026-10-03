#pragma once
#include <trcTypes.h>
#include "trcStreamPortConfig.h"
typedef struct {int fd;} TraceStreamPortBuffer_t;
traceResult xTraceStreamPortInitialize(TraceStreamPortBuffer_t *);
traceResult xTraceStreamPortWriteData(void *, uint32_t, uint32_t, int32_t *);
traceResult xTraceStreamPortReadData(void *, uint32_t, int32_t *);
traceResult xTraceStreamPortOnTraceBegin(void);
traceResult xTraceStreamPortOnTraceEnd(void);
#define xTraceStreamPortOnEnable(option) ((void)(option), TRC_SUCCESS)
#define xTraceStreamPortOnDisable() TRC_SUCCESS
extern int poc_transport_ok;
