/* Host register/API boundary harness; the helper itself is the production C file. */
#include <qemu-plugin.h>
#include "clock_anchor.h"
#include "../qemu/poc-clock-anchor-api.h"
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
static unsigned fault, reg_reads, reg_lists, seq=1;
GArray *qemu_plugin_get_registers(void) {
    GArray *a=g_array_new(FALSE,FALSE,sizeof(qemu_plugin_reg_descriptor));
    const char *names[]={"a0","a1","a2","a3"};
    reg_lists++;
    for(unsigned i=0;i<4;i++) {
        if(fault==1 && i==2) continue;
        qemu_plugin_reg_descriptor d={(struct qemu_plugin_register *)(uintptr_t)(i+1),names[i],NULL};
        g_array_append_val(a,d);
        if(fault==2 && i==0) g_array_append_val(a,d);
    }
    return a;
}
int qemu_plugin_read_register(struct qemu_plugin_register *h,GByteArray *b) {
    unsigned i=(unsigned)(uintptr_t)h-1;
    uint32_t v=i<2 ? seq : i==2 ? UINT32_C(0xfffffffe) : 1;
    reg_reads++;g_byte_array_set_size(b,4);
    for(unsigned j=0;j<4;j++) b->data[j]=(v>>(8*j))&255;
    if(fault==3 && i==2) {g_byte_array_set_size(b,3);return 3;}
    return 4;
}
bool qemu_plugin_poc_clock_configure(const void *handle,const PocClockConfig *c) {
    if(handle!=(void *)42 || fault==5) return false;
    printf("{\"configured\":true,\"observer\":%u,\"path_null\":%s}\n",
           c->observer_enabled,c->path?"false":"true");return true;
}
void qemu_plugin_poc_clock_note(const void *handle,const PocClockNote *n) {
    if(handle!=(void *)42) exit(3);
    printf("{\"kind\":%u,\"cursor\":%"PRIu64",\"pc\":%"PRIu64
           ",\"seq\":%u,\"phase\":%u,\"sample\":\"%"PRIu64"\",\"address\":%"PRIu64"}\n",
           n->kind,n->raw_cursor,n->pc,n->marker_seq,n->marker_phase,n->sample64,n->address);
}
void qemu_plugin_poc_add_ns_tagged(const void *h,uint64_t d,uint64_t id,uint64_t index) {
    (void)h;(void)d;(void)id;(void)index;exit(3);
}
bool qemu_plugin_poc_clock_finish(const void *handle,uint64_t rows) {
    if(handle!=(void *)42) return false;
    printf("{\"finished\":%"PRIu64",\"register_reads\":%u,\"register_lists\":%u}\n",
           rows,reg_reads,reg_lists);return true;
}
static void check(int status) {if(status) {fputs("helper rejected\n",stderr);exit(2);}}
int main(int argc,char **argv) {
    if(argc!=3) return 3;fault=(unsigned)strtoul(argv[2],NULL,10);
    check(clock_anchor_init(argv[1],(void *)42,0x80000000,0x80000004));
    printf("{\"needs_registers\":%s}\n",clock_anchor_needs_registers(0x80000010)?"true":"false");
    clock_anchor_vcpu_init(0,0);
    check(clock_anchor_before(0,0x80000000));
    uint64_t cursor=1;
    check(clock_anchor_after_row(fault==6?2:1,0x80000000,'I'));
    for(unsigned i=1;i<=5;i++) {
        seq=fault==4?i+1:i;
        check(clock_anchor_before(cursor,0x80000010));
        check(clock_anchor_after_row(++cursor,0x80000010,'I'));
        check(clock_anchor_before(cursor,0x80000020));
        check(clock_anchor_after_row(++cursor,0x80000020,'I'));
        check(clock_anchor_before(cursor,0x80000030));
        check(clock_anchor_after_row(++cursor,0x80000030,'I'));
    }
    check(clock_anchor_before(cursor,0x80000004));
    check(clock_anchor_mmio_success(cursor,0x80000080,0x0200bff8,4,0));
    return clock_anchor_finish(cursor);
}
