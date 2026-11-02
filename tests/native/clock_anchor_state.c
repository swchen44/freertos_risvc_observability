/* Host-only harness: exercises the actual canonical core, not a Python model. */
#include "poc-clock-state.h"
#include <inttypes.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned writes, fail_write;
static bool sink(void *opaque, const char *data, size_t length) {
    (void)opaque;
    writes++;
    if (writes == fail_write) {
        if (length > 1) fwrite(data, 1, length - 1, stdout);
        return false;
    }
    return fwrite(data, 1, length, stdout) == length;
}
static PocClockNote note(uint32_t kind, uint64_t cursor) {
    PocClockNote n = {.struct_size=sizeof n, .kind=kind, .raw_cursor=cursor};
    if (kind == POC_CLOCK_RAW_I || kind == POC_CLOCK_RAW_R || kind == POC_CLOCK_RAW_W ||
        kind == POC_CLOCK_ENTER || kind == POC_CLOCK_SAMPLED || kind == POC_CLOCK_LEAVE)
        n.pc = UINT32_C(0x80000000);
    return n;
}
#define DO(x) do { if (!(x)) goto done; } while (0)

int main(int argc, char **argv) {
    if (argc != 2) return 3;
    const char *c = argv[1];
    char run_id[40] = "native-O-1";
    PocClockConfig config = {
        .struct_size=sizeof config, .abi_version=1, .observer_enabled=1,
        .injection_enabled=1, .marker_mode=0, .expected_frequency_hz=10000000,
        .path="unused.jsonl", .run_id=run_id, .configuration="O",
        .qemu_sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        .elf_sha256="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        .profile_sha256="cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        .plugin_sha256="dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
    };
    if (!strcmp(c,"off") || !strcmp(c,"capacity") || !strcmp(c,"raw-limit")) {
        config.observer_enabled=0; config.path=NULL; config.configuration="C";
    }
    if (!strcmp(c,"no-injection") || !strncmp(c,"mmio",4) || !strcmp(c,"markers") ||
        !strcmp(c,"raw-limit")) config.injection_enabled=0;
    if (!strcmp(c,"markers") || !strcmp(c,"missing-marker") || !strcmp(c,"invalid-marker"))
        config.marker_mode=1;
    if (!strcmp(c,"bad-abi")) config.abi_version=2;
    if (!strcmp(c,"bad-size")) config.struct_size--;
    if (!strcmp(c,"bad-id")) config.run_id="unsafe\"run";
    if (!strcmp(c,"sink")) fail_write=3;
    if (!strcmp(c,"footer-sink")) fail_write=6;
    PocState *s=poc_state_new(&config,sink,NULL);
    if (!s) { fputs("configure\n",stderr); return 2; }
    strcpy(run_id,"caller-mutated"); /* Core must have copied identity strings. */
    int status=1; int64_t target=0;
    PocClockNote n=note(POC_CLOCK_BEGIN,0); DO(poc_state_note(s,&n));
    if (!strcmp(c,"capacity") || !strcmp(c,"raw-limit")) {
        uint64_t limit=!strcmp(c,"capacity") ? 65537 : 3000001;
        for(uint64_t i=1;i<=limit;i++) {
            n=note(POC_CLOCK_RAW_I,i); DO(poc_state_note(s,&n));
            if (config.injection_enabled) DO(poc_state_request(s,i,i-1,2));
        }
        status=0; goto done;
    }
    n=note(POC_CLOCK_RAW_I,1);
    if (!strcmp(c,"note-unused")) n.marker_seq=1;
    DO(poc_state_note(s,&n));
    if (!strcmp(c,"cursor")) {n=note(POC_CLOCK_RAW_I,0); DO(poc_state_note(s,&n));}
    if (!strcmp(c,"wrong-note-size")) {n=note(POC_CLOCK_END,1);n.struct_size--;DO(poc_state_note(s,&n));}
    if (!strcmp(c,"no-injection")) {DO(poc_state_request(s,1,0,2));status=0;goto done;}
    if (config.injection_enabled) {
        DO(poc_state_request(s,1,0,2));
        if (!strcmp(c,"duplicate")) DO(poc_state_request(s,1,0,2));
        if (!strcmp(c,"skip")) DO(poc_state_request(s,3,0,2));
    }
    if (!strncmp(c,"mmio",4)) {
        PocNativeIO io={.kind=1,.size=4,.address=0x0200bff8,.virtual_ns=1007,
                       .timebase_hz=10000000,.mtime64=10,.value32=10};
        if (!strcmp(c,"mmio-value")) io.value32=11;
        DO(poc_state_native_io(s,&io));
        if (!strcmp(c,"mmio-repeat")) DO(poc_state_native_io(s,&io));
        n=note(POC_CLOCK_MMIO_SUCCESS,1); n.address=io.address;n.access_size=4;
        if (!strcmp(c,"mmio-mismatch")) n.address+=4;
        if (!strcmp(c,"mmio-missing")) goto end;
        DO(poc_state_note(s,&n));
        io.kind=2;io.is_store=1;io.address=0x02004000;io.value32=100;
        DO(poc_state_native_io(s,&io));
        n.address=io.address;n.is_store=1;DO(poc_state_note(s,&n));
    }
    if (!strcmp(c,"disabled-marker") || !strcmp(c,"invalid-marker")) {
        n=note(!strcmp(c,"disabled-marker")?POC_CLOCK_ENTER:POC_CLOCK_SAMPLED,1);
        n.marker_seq=1;n.marker_phase=1;DO(poc_state_note(s,&n));
    }
    if (!strcmp(c,"markers")) {
        for(unsigned i=1;i<=5;i++) {
            n=note(POC_CLOCK_ENTER,1);n.marker_seq=i;n.marker_phase=i;
            DO(poc_state_note(s,&n));
            n.kind=POC_CLOCK_SAMPLED;n.sample64=100+i;DO(poc_state_note(s,&n));
            n.kind=POC_CLOCK_LEAVE;n.sample64=0;DO(poc_state_note(s,&n));
        }
    }
    if (!strcmp(c,"epoch")) {PocNativeIO io={.kind=3,.epoch_reason=2};DO(poc_state_native_io(s,&io));}
    if (!strcmp(c,"deferred")) {
        n=note(POC_CLOCK_RAW_R,2);DO(poc_state_note(s,&n));DO(poc_state_request(s,2,1,4));
    }
end:
    n=note(POC_CLOCK_END,poc_state_cursor(s));DO(poc_state_note(s,&n));
    if (!strcmp(c,"end-request")) DO(poc_state_request(s,2,0,2));
    if (!strcmp(c,"pending")) {DO(poc_state_finish(s,1));status=0;goto done;}
    if (config.injection_enabled) {
        DO(poc_state_apply_begin(s,!strcmp(c,"order")?2:1,
                                !strcmp(c,"overflow")?INT64_MAX:100,
                                poc_state_cursor(s),&target));
        if (!strcmp(c,"nested")) DO(poc_state_apply_begin(s,1,100,poc_state_cursor(s),&target));
        DO(poc_state_apply_end(s,1,target,!strcmp(c,"mismatch")?target+1:target,
                              poc_state_cursor(s)));
        if (!strcmp(c,"deferred")) {
            DO(poc_state_apply_begin(s,2,102,2,&target));
            DO(poc_state_apply_end(s,2,106,106,2));
        }
    }
    DO(poc_state_finish(s,poc_state_cursor(s))); status=0;
done:
    fprintf(stderr,"%s; writes=%u\n",poc_state_error(s),writes);
    poc_state_free(s);
    return status;
}
