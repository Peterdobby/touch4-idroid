/* Execute the exact resident C implementation with native calls mocked. */
#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static int log_mock(const char*,...);
struct map_desc;
static void create_mock(struct map_desc*);
static void cpu_mock(unsigned,const void*,unsigned);
static void clock_mock(int);
static void uart_mock(const void*,int);
static int reserve_mock(unsigned,unsigned);
#define RESIDENT_TEST
#define LOG log_mock
#define CREATE create_mock
#define CPU cpu_mock
#define CLOCK clock_mock
#define UART uart_mock
#define RESERVE reserve_mock
#include "resident.c"
static int mode,state,count,board_count,reserved;
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
    } else {assert(mode==3 && strstr(s,board_logs[board_count]));board_count++;}
    return (int)strlen(s);
}
static void create_mock(struct map_desc *p) {assert(mode==2 && state==1 && p==base+count);state=2;}
static void cpu_mock(unsigned id,const void *p,unsigned n)
{assert(mode==3 && board_count==1 && id==0x8930 && (uintptr_t)p==0xc0019e88 && n==1);}
static void clock_mock(int n) {assert(mode==3 && board_count==3 && n==24000000);}
static void uart_mock(const void *p,int n)
{assert(mode==3 && board_count==5 && (uintptr_t)p==0xc0019ea4 && n==4);}
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
    puts("RESIDENT_SEMANTICS_PASSED: same 17 descriptors/call order, begin/return pairing, reserve before use, original board parameters");
    return 0;
}
