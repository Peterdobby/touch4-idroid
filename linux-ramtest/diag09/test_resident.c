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
    } else if(mode==3) {assert(strstr(s,board_logs[board_count]));board_count++;}
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
static void gate_stop_mock(void) {assert(mode==4);stops++;longjmp(stop_env,1);}
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
    mode=3;resident_board_map();assert(board_count==6);
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
    return 0;
}
