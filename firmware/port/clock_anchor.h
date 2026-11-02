#pragma once
#include <stdint.h>
#include <string.h>

/* Caller supplies length bytes plus a readable NUL terminator. No fallback. */
static inline int poc_clock_parse_mode(const char *text, uint32_t length,
                                      uint32_t *mode) {
    if (!text || !mode || length != 13 || memcmp(text, "c2b-markers=", 12) != 0 ||
        (text[12] != '0' && text[12] != '1') || text[13] != '\0') return -1;
    *mode = (uint32_t)(text[12] - '0');
    return 0;
}

#ifdef POC_CLOCK_ANCHORS
void poc_clock_anchor_init(void);
void poc_clock_anchor(uint32_t phase);
uint32_t poc_clock_anchor_mode(void);
uint32_t poc_clock_anchor_count(void);
void poc_clock_anchor_enter(uint32_t seq, uint32_t phase);
void poc_clock_anchor_sampled(uint32_t seq, uint32_t phase, uint32_t lo, uint32_t hi);
void poc_clock_anchor_leave(uint32_t seq, uint32_t phase);
#endif
