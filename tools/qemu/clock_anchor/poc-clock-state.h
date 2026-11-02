#ifndef POC_CLOCK_STATE_H
#define POC_CLOCK_STATE_H
#include "poc-clock-anchor-api.h"
#include <stddef.h>

typedef struct PocState PocState;
typedef bool (*PocSink)(void *, const char *, size_t);
typedef struct PocNativeIO {
    uint32_t kind, size, is_store;
    uint32_t epoch_reason;
    uint64_t address, time_delta, mtime64, value32;
    int64_t virtual_ns;
    uint32_t timebase_hz;
} PocNativeIO;
PocState *poc_state_new(const PocClockConfig *, PocSink, void *);
void poc_state_free(PocState *);
uint64_t poc_state_cursor(const PocState *);
const char *poc_state_error(const PocState *);
bool poc_state_fail(PocState *, const char *);
bool poc_state_note(PocState *, const PocClockNote *);
bool poc_state_request(PocState *, uint64_t, uint64_t, uint64_t);
bool poc_state_apply_begin(PocState *, uint64_t, int64_t, uint64_t, int64_t *);
bool poc_state_apply_end(PocState *, uint64_t, int64_t, int64_t, uint64_t);
bool poc_state_native_io(PocState *, const PocNativeIO *);
bool poc_state_finish(PocState *, uint64_t);
#endif
