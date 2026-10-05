/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "live_timing.h"
#include <string.h>
typedef struct { uint64_t block; unsigned valid; } Line;
#ifdef POC_SMALL_CACHE
#define L1_SETS 32
#define L2_SETS 128
#else
#define L1_SETS 64
#define L2_SETS 256
#endif
static Line l1i[L1_SETS][4], l1d[L1_SETS][4], l2[L2_SETS][4];
void timing_reset(void) {
 memset(l1i,0,sizeof l1i);memset(l1d,0,sizeof l1d);memset(l2,0,sizeof l2);
}
/* MRU at slot zero. Empty slots sort after valid entries. */
static int access_line(Line cache[][4], unsigned sets, uint64_t block) {
 Line *set=cache[block%sets];
 unsigned pos=0;
 while(pos<4 && !(set[pos].valid && set[pos].block==block)) pos++;
 int hit=pos<4;
 if(!hit) pos=3;
 for(unsigned i=pos;i>0;i--) set[i]=set[i-1];
 set[0]=(Line){block,1};return hit;
}
int timing_access(uint64_t address,unsigned size,char op,uint64_t costs[5]) {
 memset(costs,0,5*sizeof *costs);
 /* Preflight full range before changing cache state. */
 if(!size || size>4096 || (op!='I'&&op!='R'&&op!='W') ||
    address<0x80000000ULL || address>=0x88000000ULL ||
    size>0x88000000ULL-address) return -1;
 uint64_t end=address+size;
 for(uint64_t start=address;start<end;) {
  uint64_t next=(start/64+1)*64;
  if(next>end) next=end;
  unsigned length=(unsigned)(next-start);
  unsigned level=op=='I'?0:1;
  costs[level]++;
  int hit=access_line(op=='I'?l1i:l1d,L1_SETS,start/64);
  if(!hit || op=='W') {
   costs[2]+=8;
   if(!access_line(l2,L2_SETS,start/64)) costs[3]+=18;
  }
  if(op=='W') costs[4]+=10+(length+7)/8;
  start=next;
 }
 return 0;
}
