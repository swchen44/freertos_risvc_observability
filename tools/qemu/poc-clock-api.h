/* POC-only extension declared by 0003-experimental-relative-clock-cost.patch.
 * This is NOT an upstream QEMU plugin API. Requires the matching patched binary.
 */
#pragma once
#include <stdint.h>
void qemu_plugin_poc_add_ns(const void *handle, uint64_t delta_ns);
