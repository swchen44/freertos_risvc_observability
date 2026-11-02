/* Capability smoke, before scheduler start. Not part of the TCP pilot. */
#include "case_api.h"
#include "clock_anchor.h"
#include "oracle.h"

void poc_case_run(void) {
    for (uint32_t phase = 1; phase <= 5; phase++) poc_clock_anchor(phase);
    poc_oracle_finish();
}
