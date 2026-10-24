/* Execute the exact resident C implementation with native calls mocked. */
#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <setjmp.h>
static int log_mock(const char*,...);
struct map_desc;
static void create_mock(struct map_desc*);
static void cpu_mock(unsigned,const void*,unsigned);
static void clock_mock(int);
static void uart_mock(const void*,int);
static int reserve_mock(unsigned,unsigned);
static unsigned gate_read_mock(unsigned);
static void gate_write_mock(unsigned,unsigned);
static void gate_stop_mock(void);
static unsigned control_mock(void);
static int noalign_mock(char*);
static unsigned ram_read_mock(unsigned);
#define RAM_READ ram_read_mock
static unsigned control_value,noalign_calls,fatal_masks,align_logs,progress_logs,fatal_logs;
#define CONTROL_READ control_mock
#define NOALIGN noalign_mock
#define FATAL_MASK() do {fatal_masks++;} while(0)
#define FAULT_READ(a,b) do {a=0x801;b=0xc018b027;} while(0)
#define RESIDENT_TEST
#define LOG log_mock
#define CREATE create_mock
#define CPU cpu_mock
#define CLOCK clock_mock
#define UART uart_mock
#define RESERVE reserve_mock
#define GATE_READ gate_read_mock
#define GATE_WRITE gate_write_mock
#define GATE_STOP gate_stop_mock
#define GATE_POLL_LIMIT 8u
#include "resident.c"
static int mode,state,count,board_count,reserved;
static unsigned reads,writes,stops,reg_value,request,gate_index;
static int acknowledge,keeps,returned,timeouts,invalids;
static jmp_buf stop_env;
static struct map_desc *base;
static const char *board_logs[]={"CPU_MAP BEGIN","CPU_MAP RETURNED","CLOCK BEGIN","CLOCK RETURNED","UART BEGIN","UART RETURNED"};
void original_fb_reserve(void) {assert(mode==1 && reserved==0);reserved=1;}
static int reserve_mock(unsigned p,unsigned n)
{assert(reserved==1 && p==0x03e00000 && n==0x100000);reserved=2;return 0;}
static int log_mock(const char *fmt,...)
{
    char s[256];va_list a;va_start(a,fmt);vsnprintf(s,sizeof(s),fmt,a);va_end(a);
    if(mode==1)assert(reserved==2 && strstr(s,"reserved"));
    else if(mode==2) {
        if(strstr(s,"BEGIN")) {assert(state==0);state=1;}
        else {assert(strstr(s,"RETURNED") && state==2);state=0;count++;}
    } else if(mode==3) {
        if(strstr(s,"T4_ALIGN")) {assert(board_count==0);align_logs++;}
        else if(strstr(s,"T4_MEMSET")) assert(board_count==0);
        else {assert(strstr(s,board_logs[board_count]));board_count++;}
    } else if(mode==5) {
        assert(strstr(s,"T4_ALIGN"));align_logs++;
    } else if(mode==6) {
        assert(strstr(s,"T4_INIT"));progress_logs++;
    } else if(mode==7) {
        assert(strstr(s,"T4_FIRST_FATAL") || strstr(s,"T4_REG") || strstr(s,"T4_SLAB"));fatal_logs++;
        if(fatal_logs==2) assert(strstr(s,"PC=c0135ce0 LR=c0010e04 CPSR=600001d3"));
    }
    else {
        assert(mode==4);
        if(strstr(s,"KEEP_DISPLAY"))keeps++;
        if(strstr(s,"RETURNED"))returned++;
        if(strstr(s,"TIMEOUT"))timeouts++;
        if(strstr(s,"INVALID"))invalids++;
    }
    return (int)strlen(s);
}
static void create_mock(struct map_desc *p) {assert(mode==2 && state==1 && p==base+count);state=2;}
static void cpu_mock(unsigned id,const void *p,unsigned n)
{assert(mode==3 && board_count==1 && id==0x8930 && (uintptr_t)p==0xc0019e88 && n==1);}
static void clock_mock(int n) {assert(mode==3 && board_count==3 && n==24000000);}
static void uart_mock(const void *p,int n)
{assert(mode==3 && board_count==5 && (uintptr_t)p==0xc0019ea4 && n==4);}
static unsigned gate_read_mock(unsigned n) {assert(mode==4 && n==gate_index);reads++;return reg_value;}
static void gate_write_mock(unsigned n,unsigned v)
{
    assert(mode==4 && n==gate_index);writes++;request=v;reg_value=v;
    if(acknowledge)reg_value=(v&~0xf0u)|((v&15u)<<4);
}
static void gate_stop_mock(void) {assert(mode==4 || mode==5 || mode==7);stops++;longjmp(stop_env,1);}
static unsigned control_mock(void) {return control_value;}
static int noalign_mock(char *p) {assert(!p);noalign_calls++;control_value&=~2u;return 1;}
static unsigned ram_read_mock(unsigned p)
{
    assert(ram_words(p,4));
    if(p==0xc0100000)return 0xc0101000;
    return p;
}
static void reset_gate(unsigned n)
{
    reads=writes=stops=0;keeps=returned=timeouts=invalids=0;
    gate_index=n;reg_value=0x1234abc5;acknowledge=1;
}
int main(void)
{
    struct map_desc maps[17];struct map_desc original[17];int i;
    mode=1;resident_reserve();assert(reserved==2);
    for(i=0;i<17;i++)maps[i]=(struct map_desc){0xfc000000u+(unsigned)i*0x10000,0x82500u+(unsigned)i,0x1000,0};
    memcpy(original,maps,sizeof(maps));base=maps;mode=2;
    resident_iotable(maps,17);assert(count==17 && state==0);
    assert(!memcmp(maps,original,sizeof(maps)));
    resident_iotable(maps,0);assert(count==17);
    control_value=0x10c5387f;
    mode=3;resident_board_map();assert(board_count==6 && align_logs==1);
    assert(control_value==0x10c5387d && noalign_calls==1);
    mode=5;resident_alignment();assert(control_value==0x10c5387d && noalign_calls==2);
    control_value=0x1085387f;
    if(!setjmp(stop_env)) {resident_alignment();assert(!"U=0 must stop");}
    assert(noalign_calls==2 && control_value==0x1085387f);
    mode=6;for(i=0;i<4;i++)resident_progress((unsigned)i);
    resident_progress(4);assert(progress_logs==4);
    mode=7;
    {
        unsigned regs[18]={0};regs[15]=0xc0135ce0;regs[14]=0xc0010e04;regs[16]=0x600001d3;
        if(!setjmp(stop_env)) {resident_fatal("alignment",regs,0x801);assert(!"fatal did not stop");}
        assert(fatal_masks==1 && fatal_logs==7);
        if(!setjmp(stop_env)) {resident_fatal("nested",regs,5);assert(!"recursive fatal did not stop");}
        assert(fatal_masks==2 && fatal_logs==7);
        assert(ram_words(0xc0000000,4) && ram_words(0xcffffffc,4));
        assert(!ram_words(0xcffffffc,8) && !ram_words(0xd0000000,4));
        assert(!ram_words(0x30363a34,4) && !ram_words(0xfc000000,4));
        assert(!ram_words(0xc0000001,4));
        fatal_cache(0xc0100000,0x30363a34,0);assert(fatal_logs==10);
        fatal_cache(0xfc000000,0xc0102000,0);assert(fatal_logs==12);
    }
    mode=4;
    for(i=0;i<64;i++) {
        int keep=(i==0xb || i==0xf || i==0x11 || i==0x12);
        reset_gate((unsigned)i);resident_gate(i,0);
        if(keep)assert(keeps==1 && reads==0 && writes==0 && reg_value==0x1234abc5);
        else assert(keeps==0 && writes==1 && reads==2 && request==0x1234abc0 && returned==1);
        reset_gate((unsigned)i);resident_gate(i,1);
        assert(keeps==0 && writes==1 && reads==2 && request==0x1234abcf && returned==1);
    }
    reset_gate(2);acknowledge=0;
    if(!setjmp(stop_env)) {resident_gate(2,1);assert(!"timeout did not stop");}
    assert(stops==1 && timeouts==1 && writes==1 && reads==1+GATE_POLL_LIMIT && returned==0);
    reset_gate(0);
    if(!setjmp(stop_env)) {resident_gate(64,1);assert(!"invalid index did not stop");}
    assert(stops==1 && invalids==1 && writes==0 && reads==0);
    reset_gate(0);
    if(!setjmp(stop_env)) {resident_gate(-1,1);assert(!"negative index did not stop");}
    assert(stops==1 && invalids==1 && writes==0 && reads==0);
    puts("RESIDENT_SEMANTICS_PASSED: same 17 descriptors/call order, begin/return pairing, reserve before use, original board parameters");
    puts("CLOCK_POLICY_PASSED: all 64 gates on/off; four protected OFF paths perform no MMIO; original masks retained; bounded timeout and invalid-index stop");
    puts("ALIGNMENT_AND_FATAL_PASSED: native noalign clears only A; U=0 refused; milestones; first fault frozen and recursion blocked");
    return 0;
}
