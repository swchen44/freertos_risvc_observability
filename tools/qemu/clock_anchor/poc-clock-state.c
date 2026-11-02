/* Canonical host state machine; external adapter owns locking and clock reads. */
#include "poc-clock-state.h"
#include <inttypes.h>
#include <limits.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define PENDING_LIMIT 65536u
#define RAW_LIMIT UINT64_C(3000000)
enum Stage { CONFIGURED, ACTIVE, DRAINING, FINISHED, FAILED };
typedef struct Request { uint64_t id, index, delta; } Request;
struct PocState {
    enum Stage stage;
    PocSink sink;
    void *opaque;
    bool observer, injection, applying, io_pending, clock_seen;
    uint32_t marker_mode, marker_seq, marker_stage, head, pending, frequency;
    uint32_t last_op;
    uint64_t cursor, pc, requested_cursor, requests, applied, sequence;
    uint64_t device_io, plugin_io;
    int64_t before, target, last_clock;
    PocNativeIO io;
    Request *queue;
    char run_id[97], config[2], hashes[4][65], path[4097], error[128];
};

static bool copy_string(char *dest, size_t capacity, const char *src) {
    if (!src) return false;
    size_t n=0;
    while (n<capacity && src[n]) n++;
    if (n==0 || n==capacity) return false;
    memcpy(dest,src,n+1);
    return true;
}
static bool safe_id(const char *s) {
    for (size_t i=0;s[i];i++) {
        char c=s[i];
        bool alpha=(c>='A' && c<='Z') || (c>='a' && c<='z');
        bool digit=c>='0' && c<='9';
        if (!alpha && !digit && !(i && (c=='_' || c=='-' || c=='.'))) return false;
    }
    return true;
}
static bool hex_hash(const char *s) {
    if (strlen(s)!=64) return false;
    for (unsigned i=0;i<64;i++) if (!((s[i]>='0' && s[i]<='9') ||
                                                   (s[i]>='a' && s[i]<='f'))) return false;
    return true;
}
bool poc_state_fail(PocState *s, const char *reason) {
    if (s && s->stage!=FAILED) {
        snprintf(s->error,sizeof s->error,"%s",reason);
        s->stage=FAILED;
    }
    return false;
}
const char *poc_state_error(const PocState *s) { return s ? s->error : "no-state"; }
uint64_t poc_state_cursor(const PocState *s) { return s ? s->cursor : 0; }
void poc_state_free(PocState *s) { if(s) {free(s->queue);free(s);} }

static bool emit(PocState *s, const char *kind, const char *phase, const char *fmt, ...) {
    if (s->stage==FAILED) return false;
    if (!s->observer) return true;
    char extra[12288], line[16385];
    va_list ap;va_start(ap,fmt);
    int n=vsnprintf(extra,sizeof extra,fmt,ap);va_end(ap);
    if(n<0 || (size_t)n>=sizeof extra) return poc_state_fail(s,"line-limit");
    n=snprintf(line,sizeof line,
        "{\"schema\":\"clock-anchor-record-v1\",\"run_id\":\"%s\","
        "\"record_seq\":\"%"PRIu64"\",\"kind\":\"%s\",\"cpu\":\"0\","
        "\"raw_cursor\":\"%"PRIu64"\",\"phase\":\"%s\"%s}\n",
        s->run_id,s->sequence,kind,s->cursor,phase,extra);
    if(n<0 || n>16384) return poc_state_fail(s,"line-limit");
    if(!s->sink(s->opaque,line,(size_t)n)) return poc_state_fail(s,"sink-write");
    s->sequence++;
    return true;
}

PocState *poc_state_new(const PocClockConfig *c, PocSink sink, void *opaque) {
    if(!c || c->struct_size!=sizeof *c || c->abi_version!=1 ||
       c->observer_enabled>1 || c->injection_enabled>1 || c->marker_mode>1 ||
       c->expected_frequency_hz!=10000000 || (c->observer_enabled && !sink) ||
       (!c->observer_enabled && c->path)) return NULL;
    PocState *s=calloc(1,sizeof *s);
    if(!s) return NULL;
    s->queue=calloc(PENDING_LIMIT,sizeof *s->queue);
    if(!s->queue || !copy_string(s->run_id,sizeof s->run_id,c->run_id) || !safe_id(s->run_id) ||
       !copy_string(s->config,sizeof s->config,c->configuration) ||
       !strchr("LCOM",s->config[0]) ||
       (c->observer_enabled && !copy_string(s->path,sizeof s->path,c->path))) goto bad;
    const char *hashes[]={c->qemu_sha256,c->elf_sha256,c->profile_sha256,c->plugin_sha256};
    for(unsigned i=0;i<4;i++)
        if(!copy_string(s->hashes[i],sizeof s->hashes[i],hashes[i]) ||
           !hex_hash(s->hashes[i])) goto bad;
    s->observer=c->observer_enabled;s->injection=c->injection_enabled;
    s->marker_mode=c->marker_mode;s->sink=sink;s->opaque=opaque;
    if(!emit(s,"header","configured",
        ",\"abi_version\":\"1\",\"configuration\":\"%s\",\"injection_enabled\":%s,"
        "\"observer_enabled\":%s,\"marker_mode\":\"%u\",\"expected_frequency_hz\":\"10000000\","
        "\"qemu_sha256\":\"%s\",\"elf_sha256\":\"%s\",\"profile_sha256\":\"%s\","
        "\"plugin_sha256\":\"%s\",\"clock_domains\":{\"virtual\":\"qemu_virtual_ns\","
        "\"mtime\":\"aclint_mtime64\",\"psf\":\"mtime_low32\"}",
        s->config,s->injection?"true":"false",s->observer?"true":"false",s->marker_mode,
        s->hashes[0],s->hashes[1],s->hashes[2],s->hashes[3])) goto bad;
    return s;
bad:
    poc_state_free(s);return NULL;
}

static bool clock_point(PocState *s, int64_t ns) {
    if(ns<0 || (s->clock_seen && ns<s->last_clock)) return poc_state_fail(s,"clock-reversal");
    s->clock_seen=true;s->last_clock=ns;return true;
}

bool poc_state_request(PocState *s, uint64_t id, uint64_t index, uint64_t delta) {
    if(!s || s->stage==FAILED) return false;
    if(s->stage!=ACTIVE) return poc_state_fail(s,"request-state");
    if(!s->injection) return poc_state_fail(s,"request-disabled");
    if(id!=s->requests+1 || !s->cursor || index!=s->cursor-1 ||
       s->requested_cursor==s->cursor || !delta || delta>INT64_MAX)
        return poc_state_fail(s,"request-order");
    if(s->pending==PENDING_LIMIT) return poc_state_fail(s,"pending-limit");
    s->queue[(s->head+s->pending)%PENDING_LIMIT]=(Request){id,index,delta};
    s->pending++;s->requests++;s->requested_cursor=s->cursor;
    return emit(s,"cost_request",s->last_op==POC_CLOCK_RAW_I?"instruction_before":
        "memory_after_success",",\"request_id\":\"%"PRIu64"\",\"request_event_index\":\"%"PRIu64
        "\",\"delta_ns\":\"%"PRIu64"\",\"request_clock_ns\":null,\"pc\":\"%"PRIu64"\"",
        id,index,delta,s->pc);
}

bool poc_state_apply_begin(PocState *s, uint64_t id, int64_t before,
                           uint64_t cursor, int64_t *target) {
    if(!s || s->stage==FAILED) return false;
    if(s->applying) return poc_state_fail(s,"apply-in-progress");
    Request *r=s->pending ? &s->queue[s->head] : NULL;
    if((s->stage!=ACTIVE && s->stage!=DRAINING) || !r || r->id!=id ||
       cursor!=s->cursor || !target || before<0 || r->delta>INT64_MAX ||
       (uint64_t)before>(uint64_t)INT64_MAX-r->delta)
        return poc_state_fail(s,"apply-order-or-range");
    if(!clock_point(s,before)) return false;
    s->before=before;s->target=before+(int64_t)r->delta;
    s->applying=true;*target=s->target;return true;
}
bool poc_state_apply_end(PocState *s, uint64_t id, int64_t returned,
                         int64_t after, uint64_t cursor) {
    if(!s || s->stage==FAILED) return false;
    if(!s->applying || !s->pending || s->queue[s->head].id!=id || cursor!=s->cursor)
        return poc_state_fail(s,"apply-order-or-range");
    if(!emit(s,"cost_applied","cpu_async_outside_exec",
        ",\"request_id\":\"%"PRIu64"\",\"before_ns\":\"%"PRId64
        "\",\"requested_target_ns\":\"%"PRId64"\",\"advance_return_ns\":\"%"PRId64
        "\",\"after_ns\":\"%"PRId64"\"",id,s->before,s->target,returned,after)) return false;
    if(returned!=s->target || after!=s->target) return poc_state_fail(s,"applied-mismatch");
    if(!clock_point(s,after)) return false;
    s->applying=false;s->head=(s->head+1)%PENDING_LIMIT;s->pending--;s->applied++;
    return true;
}

static bool emit_io(PocState *s, const char *source) {
    const PocNativeIO *io=&s->io;
    const char *kind=io->kind==1?"mtime_read":"mtimecmp_write";
    const char *phase=!strcmp(source,"device")?"device_mmio":"memory_after_success";
    char fields[1024];
    if(io->kind==1) {
        if(!strcmp(source,"device"))
            snprintf(fields,sizeof fields,",\"virtual_ns\":\"%"PRId64
                "\",\"timebase_hz\":\"%u\",\"time_delta\":\"%"PRIu64
                "\",\"mtime64\":\"%"PRIu64"\",\"value32\":\"%"PRIu64"\"",
                io->virtual_ns,io->timebase_hz,io->time_delta,io->mtime64,io->value32);
        else strcpy(fields,",\"virtual_ns\":null,\"timebase_hz\":null,\"time_delta\":null,"
                           "\"mtime64\":null,\"value32\":null");
    } else {
        if(!strcmp(source,"device"))
            snprintf(fields,sizeof fields,",\"value32\":\"%"PRIu64"\"",io->value32);
        else strcpy(fields,",\"value32\":null");
    }
    return emit(s,kind,phase,",\"source\":\"%s\",\"native_io_seq\":\"%"PRIu64
        "\",\"address\":\"%"PRIu64"\",\"size\":\"4\",\"pc\":\"%"PRIu64"\"%s",
        source,s->device_io,io->address,s->pc,fields);
}

bool poc_state_native_io(PocState *s, const PocNativeIO *io) {
    if(!s || s->stage==FAILED || !io) return false;
    if(s->stage==CONFIGURED) return true; /* Before capture: no observed epoch yet. */
    if(s->stage!=ACTIVE && s->stage!=DRAINING) return poc_state_fail(s,"io-state");
    if(io->kind==3) {
        const char *reasons[]={"", "mtime_write", "reset", "device_changed", "frequency_changed"};
        if(io->epoch_reason<1 || io->epoch_reason>4) return poc_state_fail(s,"epoch-reason");
        if(!emit(s,"epoch_change","device_epoch",",\"reason\":\"%s\","
                 "\"old_value\":null,\"new_value\":null",reasons[io->epoch_reason])) return false;
        return poc_state_fail(s,"epoch-change");
    }
    if(s->io_pending) return poc_state_fail(s,"native-io-pending");
    if(io->epoch_reason || io->size!=4 || io->value32>UINT32_MAX ||
       (io->kind!=1 && io->kind!=2) || io->is_store!=(io->kind==2))
        return poc_state_fail(s,"native-layout");
    if(io->kind==1) {
        if(io->address!=0x0200bff8 && io->address!=0x0200bffc)
            return poc_state_fail(s,"native-address");
        if(!clock_point(s,io->virtual_ns)) return false;
        if(!io->timebase_hz || (s->frequency && io->timebase_hz!=s->frequency))
            return poc_state_fail(s,"frequency-change");
        s->frequency=io->timebase_hz;
        uint64_t ns=(uint64_t)io->virtual_ns;
        uint64_t tick=(ns/1000000000)*io->timebase_hz +
                     (ns%1000000000)*io->timebase_hz/1000000000 + io->time_delta;
        uint32_t word=io->address==0x0200bffc ? (uint32_t)(tick>>32) : (uint32_t)tick;
        if(tick!=io->mtime64 || word!=io->value32) return poc_state_fail(s,"native-value");
    } else if(io->address!=0x02004000 && io->address!=0x02004004)
        return poc_state_fail(s,"native-address");
    s->io=*io;s->io_pending=true;s->device_io++;
    return emit_io(s,"device");
}

bool poc_state_note(PocState *s, const PocClockNote *n) {
    if(!s || s->stage==FAILED) return false;
    if(!n || n->struct_size!=sizeof *n || n->pc>UINT32_MAX)
        return poc_state_fail(s,"note-layout");
    bool marker=n->kind>=POC_CLOCK_ENTER && n->kind<=POC_CLOCK_LEAVE;
    if ((!marker && (n->marker_seq || n->marker_phase)) ||
        (n->kind!=POC_CLOCK_SAMPLED && n->sample64) ||
        (n->kind!=POC_CLOCK_MMIO_SUCCESS && (n->address || n->access_size || n->is_store)))
        return poc_state_fail(s,"note-layout");
    if(n->kind==POC_CLOCK_BEGIN) {
        if(s->stage!=CONFIGURED || n->raw_cursor) return poc_state_fail(s,"begin-state");
        s->stage=ACTIVE;return emit(s,"capture_begin","before_guest_instruction","");
    }
    if(n->kind>=POC_CLOCK_RAW_I && n->kind<=POC_CLOCK_RAW_W) {
        if(s->stage!=ACTIVE || n->raw_cursor!=s->cursor+1) return poc_state_fail(s,"raw-cursor");
        if(n->raw_cursor>RAW_LIMIT) return poc_state_fail(s,"raw-limit");
        if(s->injection && s->requested_cursor!=s->cursor) return poc_state_fail(s,"missing-request");
        s->cursor=n->raw_cursor;s->pc=n->pc;s->last_op=n->kind;return true;
    }
    if(n->raw_cursor!=s->cursor) return poc_state_fail(s,"note-cursor");
    if(n->kind==POC_CLOCK_END) {
        if(s->stage!=ACTIVE || (s->injection && s->requested_cursor!=s->cursor))
            return poc_state_fail(s,"end-state");
        s->stage=DRAINING;return emit(s,"capture_end","before_guest_instruction","");
    }
    if(n->kind==POC_CLOCK_MMIO_SUCCESS) {
        if((s->stage!=ACTIVE && s->stage!=DRAINING) || !s->io_pending ||
           n->address!=s->io.address || n->access_size!=s->io.size ||
           n->is_store!=s->io.is_store) return poc_state_fail(s,"mmio-pair");
        s->plugin_io++;s->io_pending=false;return emit_io(s,"plugin");
    }
    if(n->kind>=POC_CLOCK_ENTER && n->kind<=POC_CLOCK_LEAVE) {
        uint32_t stage=n->kind-POC_CLOCK_ENTER;
        if(s->stage!=ACTIVE || !s->observer || !s->marker_mode ||
           stage!=s->marker_stage || n->marker_seq!=s->marker_seq+1 ||
           n->marker_phase!=n->marker_seq || n->marker_seq>5 ||
           (stage!=1 && n->sample64)) return poc_state_fail(s,"marker-order");
        const char *kinds[]={"marker_enter","marker_sampled","marker_leave"};
        char sample[32];
        if(stage==1) snprintf(sample,sizeof sample,"\"%"PRIu64"\"",n->sample64);
        else strcpy(sample,"null");
        if(!emit(s,kinds[stage],"hook_before_guest_instruction",
            ",\"marker_seq\":\"%u\",\"marker_phase\":\"%u\",\"sample64\":%s,\"pc\":\"%"PRIu64"\"",
            n->marker_seq,n->marker_phase,sample,n->pc)) return false;
        if(stage==2) {s->marker_seq++;s->marker_stage=0;} else s->marker_stage++;
        return true;
    }
    return poc_state_fail(s,"note-kind");
}

bool poc_state_finish(PocState *s, uint64_t expected_rows) {
    if(!s || s->stage==FAILED) return false;
    if(s->stage!=DRAINING || s->cursor!=expected_rows) return poc_state_fail(s,"finish-state");
    if(s->pending || s->applying || s->requests!=s->applied) return poc_state_fail(s,"finish-pending");
    if(s->io_pending || s->device_io!=s->plugin_io) return poc_state_fail(s,"finish-io");
    if(s->observer && s->marker_mode && (s->marker_seq!=5 || s->marker_stage))
        return poc_state_fail(s,"finish-markers");
    if(!emit(s,"footer","finished",",\"complete\":true,\"raw_rows\":\"%"PRIu64
        "\",\"requests\":\"%"PRIu64"\",\"applied\":\"%"PRIu64"\",\"pending\":\"0\","
        "\"device_io\":\"%"PRIu64"\",\"plugin_io\":\"%"PRIu64"\",\"record_count\":\"%"PRIu64"\"",
        s->cursor,s->requests,s->applied,s->device_io,s->plugin_io,s->sequence+1)) return false;
    s->stage=FINISHED;return true;
}
