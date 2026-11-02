/* SPDX-License-Identifier: GPL-2.0-or-later
 * No clock getters: only argument-register snapshots and successful row/IO notes.
 */
#include "clock_anchor.h"
#include "../qemu/poc-clock-anchor-api.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char *keys[]={"version","observer","injection","marker_mode","run_id",
    "configuration","qemu_sha256","elf_sha256","profile_sha256","plugin_sha256",
    "sidecar","enter_pc","sampled_pc","leave_pc"};
static char values[14][4097];
static const void *handle;
static uint64_t begin_pc,end_pc,markers[3],cursor;
static unsigned observer,marker_mode,last_seq,marker_stage;
static bool initialized,started,ended,ready;
static struct qemu_plugin_register *registers[4];
static GByteArray *bytes;

static int error(const char *message) {
    fprintf(stderr,"clock_anchor: %s\n",message);return -1;
}
static void fatal(const char *message) {error(message);exit(2);}
static bool number(const char *s,uint32_t *out) {
    if(!*s || (s[0]=='0' && s[1])) return false;
    uint64_t n=0;
    for(;*s;s++) {
        if(*s<'0' || *s>'9') return false;
        n=n*10+(unsigned)(*s-'0');
        if(n>UINT32_MAX) return false;
    }
    *out=(uint32_t)n;return true;
}
static bool valid_id(const char *s) {
    size_t n=strlen(s);
    if(!n || n>96) return false;
    for(size_t i=0;i<n;i++) {
        char c=s[i];bool alnum=(c>='a'&&c<='z') || (c>='A'&&c<='Z') || (c>='0'&&c<='9');
        if(!alnum && !(i && (c=='_' || c=='-' || c=='.'))) return false;
    }
    return true;
}
static bool valid_sha(const char *s) {
    if(strlen(s)!=64) return false;
    for(unsigned i=0;i<64;i++) if(!((s[i]>='0'&&s[i]<='9') || (s[i]>='a'&&s[i]<='f'))) return false;
    return true;
}

int clock_anchor_init(const char *path,const void *owned_handle,uint64_t begin,uint64_t end) {
    if(initialized || !owned_handle || !path || strchr(path,',') || strchr(path,'\n') ||
       begin==end || begin>UINT32_MAX || end>UINT32_MAX || (begin&1) || (end&1) || !begin || !end)
        return error("init arguments");
    FILE *f=fopen(path,"r");if(!f) return error("config open");
    char line[8192];bool seen[14]={0};bool bad=false;
    while(fgets(line,sizeof line,f)) {
        size_t n=strlen(line);
        if(!n || line[n-1]!='\n' || strchr(line,'\r')) {bad=true;break;}
        line[n-1]=0;char *value=strchr(line,'=');
        if(!value) {bad=true;break;}
        *value++=0;
        unsigned i=0;while(i<14 && strcmp(line,keys[i])) i++;
        if(i==14 || seen[i] || !*value || strlen(value)>4096) {bad=true;break;}
        seen[i]=true;strcpy(values[i],value);
    }
    if(ferror(f)) bad=true;
    if(fclose(f)) bad=true;
    for(unsigned i=0;i<14;i++) if(!seen[i]) bad=true;
    if(bad || strcmp(values[0],"1")) return error("config fields");
    uint32_t flags[3];
    for(unsigned i=0;i<3;i++) if(!number(values[i+1],&flags[i]) || flags[i]>1) return error("config flags");
    observer=flags[0];marker_mode=flags[2];
    if(!valid_id(values[4]) || strlen(values[5])!=1 || !strchr("COM",values[5][0]))
        return error("config identity");
    if((values[5][0]=='C' && (observer || !marker_mode)) ||
       (values[5][0]=='O' && (!observer || !marker_mode)) ||
       (values[5][0]=='M' && (!observer || marker_mode))) return error("config mode");
    for(unsigned i=6;i<10;i++) if(!valid_sha(values[i])) return error("config SHA");
    if(strchr(values[10],',') || (!observer && strcmp(values[10],"-")) ||
       (observer && !strcmp(values[10],"-"))) return error("config sidecar");
    for(unsigned i=0;i<3;i++) {
        uint32_t pc;
        if(!number(values[11+i],&pc) || (pc&1) || pc<0x80000000 || pc>=0x88000000 ||
           pc==begin || pc==end) return error("config marker PC");
        markers[i]=pc;
        for(unsigned j=0;j<i;j++) if(markers[j]==pc) return error("duplicate marker PC");
    }
    PocClockConfig c={.struct_size=sizeof c,.abi_version=1,.observer_enabled=observer,
        .injection_enabled=flags[1],.marker_mode=marker_mode,.expected_frequency_hz=10000000,
        .path=observer?values[10]:NULL,.run_id=values[4],.configuration=values[5],
        .qemu_sha256=values[6],.elf_sha256=values[7],.profile_sha256=values[8],.plugin_sha256=values[9]};
    if(!qemu_plugin_poc_clock_configure(owned_handle,&c)) return error("configure rejected");
    handle=owned_handle;begin_pc=begin;end_pc=end;initialized=true;return 0;
}

bool clock_anchor_needs_registers(uint64_t pc) {
    return initialized && observer && marker_mode &&
           (pc==markers[0] || pc==markers[1] || pc==markers[2]);
}
void clock_anchor_vcpu_init(qemu_plugin_id_t id,unsigned cpu) {
    (void)id;if(cpu) fatal("requires CPU0");
    if(!observer || !marker_mode) return;
    GArray *all=qemu_plugin_get_registers();
    if(!all) fatal("register enumeration");
    const char *names[]={"a0","a1","a2","a3"};
    unsigned counts[4]={0};
    for(unsigned i=0;i<all->len;i++) {
        qemu_plugin_reg_descriptor *d=&g_array_index(all,qemu_plugin_reg_descriptor,i);
        for(unsigned j=0;j<4;j++) if(d->name && !strcmp(names[j],d->name)) {
            registers[j]=d->handle;counts[j]++;
        }
    }
    g_array_free(all,TRUE);
    for(unsigned i=0;i<4;i++) if(counts[i]!=1 || !registers[i]) fatal("missing/duplicate register");
    bytes=g_byte_array_new();ready=true;
}
static uint32_t read_register(unsigned n) {
    g_byte_array_set_size(bytes,0);
    if(qemu_plugin_read_register(registers[n],bytes)!=4 || bytes->len!=4) fatal("short register read");
    uint32_t value=0;
    for(unsigned i=0;i<4;i++) value|=(uint32_t)bytes->data[i]<<(8*i);
    return value;
}
int clock_anchor_before(uint64_t rows,uint64_t pc) {
    if(!initialized || rows!=cursor) return error("before cursor");
    PocClockNote n={.struct_size=sizeof n,.raw_cursor=cursor,.pc=pc};
    if(pc==begin_pc) {
        if(started || cursor) return error("duplicate begin");
        n.kind=POC_CLOCK_BEGIN;qemu_plugin_poc_clock_note(handle,&n);started=true;return 0;
    }
    if(pc==end_pc) {
        if(!started || ended) return error("unmatched end");
        n.kind=POC_CLOCK_END;qemu_plugin_poc_clock_note(handle,&n);ended=true;return 0;
    }
    if(!started || ended || !clock_anchor_needs_registers(pc)) return 0;
    if(!ready) return error("registers not ready");
    unsigned stage=pc==markers[0]?0:pc==markers[1]?1:2;
    n.marker_seq=read_register(0);n.marker_phase=read_register(1);
    if(stage!=marker_stage || n.marker_seq!=last_seq+1 ||
       n.marker_phase!=n.marker_seq || n.marker_seq>5) return error("marker sequence");
    n.kind=POC_CLOCK_ENTER+stage;
    if(stage==1) n.sample64=(uint64_t)read_register(2) | ((uint64_t)read_register(3)<<32);
    qemu_plugin_poc_clock_note(handle,&n);
    if(stage==2) {last_seq++;marker_stage=0;} else marker_stage++;
    return 0;
}
int clock_anchor_after_row(uint64_t rows,uint64_t pc,char op) {
    if(!started || ended || rows!=cursor+1 || (op!='I' && op!='R' && op!='W')) return error("row cursor");
    PocClockNote n={.struct_size=sizeof n,.kind=op=='I'?POC_CLOCK_RAW_I:
        op=='R'?POC_CLOCK_RAW_R:POC_CLOCK_RAW_W,.raw_cursor=rows,.pc=pc};
    qemu_plugin_poc_clock_note(handle,&n);cursor=rows;return 0;
}
int clock_anchor_mmio_success(uint64_t rows,uint64_t pc,uint64_t address,unsigned size,unsigned store) {
    if(!started) return 0;
    if(rows!=cursor || size!=4 || store>1) return error("MMIO fields");
    PocClockNote n={.struct_size=sizeof n,.kind=POC_CLOCK_MMIO_SUCCESS,.raw_cursor=rows,
                   .pc=pc,.address=address,.access_size=size,.is_store=store};
    qemu_plugin_poc_clock_note(handle,&n);return 0;
}
int clock_anchor_finish(uint64_t rows) {
    if(!initialized || !started || !ended || rows!=cursor ||
       (observer && marker_mode && (last_seq!=5 || marker_stage))) return error("incomplete capture");
    bool ok=qemu_plugin_poc_clock_finish(handle,rows);
    if(bytes) g_byte_array_free(bytes,TRUE);
    initialized=false;return ok?0:error("finish rejected");
}
