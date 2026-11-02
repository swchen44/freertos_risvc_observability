/* POC-only SDK markers. FreeRTOS and TraceRecorder source are unchanged. */
#include "clock_anchor.h"
#ifdef POC_CLOCK_ANCHORS
#include "case_api.h"

static TraceStringHandle_t channel, format;
static uint32_t marker_mode, marker_count;

void poc_clock_anchor_init(void) {
    char command[64] = {0};
    uint32_t length = 0;
    if (poc_sh_get_cmdline(command, sizeof command, &length) != 0 ||
        poc_clock_parse_mode(command, length, &marker_mode) != 0) {
        poc_console("C2b invalid marker mode\n");
        poc_finish(0);
    }
    configASSERT(xTraceStringRegister("C2B", &channel) == TRC_SUCCESS);
    configASSERT(xTraceStringRegister("C2Bv1|%u|%u|%u|%u", &format) == TRC_SUCCESS);
}

__attribute__((noinline, noclone, used))
void poc_clock_anchor_enter(uint32_t seq, uint32_t phase) {
    __asm__ volatile("nop" :: "r"(seq), "r"(phase) : "memory");
}

__attribute__((noinline, noclone, used))
void poc_clock_anchor_sampled(uint32_t seq, uint32_t phase, uint32_t lo, uint32_t hi) {
    __asm__ volatile("nop" :: "r"(seq), "r"(phase), "r"(lo), "r"(hi) : "memory");
}

__attribute__((noinline, noclone, used))
void poc_clock_anchor_leave(uint32_t seq, uint32_t phase) {
    __asm__ volatile("nop" :: "r"(seq), "r"(phase) : "memory");
}

void poc_clock_anchor(uint32_t phase) {
    if (!marker_mode) return;
    configASSERT(phase == marker_count + 1 && phase <= 5);
    uint32_t seq = marker_count + 1;
    poc_clock_anchor_enter(seq, phase);
    uint64_t sample = poc_mtime();
    poc_clock_anchor_sampled(seq, phase, (uint32_t)sample, (uint32_t)(sample >> 32));
    configASSERT(xTracePrintF4(channel, format, seq, phase,
                 (uint32_t)sample, (uint32_t)(sample >> 32)) == TRC_SUCCESS);
    marker_count = seq;
    poc_clock_anchor_leave(seq, phase);
}

uint32_t poc_clock_anchor_mode(void) { return marker_mode; }
uint32_t poc_clock_anchor_count(void) { return marker_count; }
#endif
