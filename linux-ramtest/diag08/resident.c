/* Native kernel-context diagnostics. Same mappings and board calls as cpu.c.
 * Lives in explicitly reserved RAM; no OpeniBoot/helper aliases are used.
 */
typedef unsigned u32;
struct map_desc {u32 virtual,pfn,length,type;};
#ifndef RESIDENT_TEST
#define LOG ((int (*)(const char*,...))0xc01358f8)
#define CREATE ((void (*)(struct map_desc*))0xc000c720)
#define CPU ((void (*)(u32,const void*,u32))0xc000da74)
#define CLOCK ((void (*)(int))0xc000db38)
#define UART ((void (*)(const void*,int))0xc000dc20)
#define RESERVE ((int (*)(u32,u32))0xc00790b4)
#endif
extern void original_fb_reserve(void);
static void video_pause(void)
{
#ifndef RESIDENT_TEST
    /* Bounded software pause so BEGIN survives several camera frames.
     * Not a calibrated delay; does not use IRQs, timers or clock registers. */
    volatile u32 n;
    for(n=0;n<0x01000000u;n++)__asm__ volatile("nop");
#endif
}
void resident_reserve(void)
{
    original_fb_reserve();
    if(RESERVE(0x03e00000,0x100000)) {
        LOG("<0>T4_IO: resident RAM reservation FAILED; stopped\n");for(;;);
    }
    LOG("<5>T4_IO: resident RAM 03e00000+00100000 reserved\n");
}
void resident_iotable(struct map_desc *desc,int nr)
{
    int i;
    for(i=0;i<nr;i++) {
        LOG("<5>T4_IO %d/%d BEGIN va=%08x pa=%08x len=%08x type=%u\n",
            i+1,nr,desc[i].virtual,desc[i].pfn<<12,desc[i].length,desc[i].type);
        video_pause();
        CREATE(desc+i);
        LOG("<5>T4_IO %d/%d RETURNED\n",i+1,nr);
    }
}
void resident_board_map(void)
{
    LOG("<5>T4_BOARD CPU_MAP BEGIN\n");
    CPU(0x8930,(void*)0xc0019e88,1);
    LOG("<5>T4_BOARD CPU_MAP RETURNED\n");
    LOG("<5>T4_BOARD CLOCK BEGIN xtal=24000000\n");
    video_pause();
    CLOCK(24000000);
    LOG("<5>T4_BOARD CLOCK RETURNED\n");
    LOG("<5>T4_BOARD UART BEGIN\n");
    UART((void*)0xc0019ea4,4);
    LOG("<5>T4_BOARD UART RETURNED\n");
}
