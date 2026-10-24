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
#define NOALIGN ((int (*)(char*))0xc000c4d0)
static u32 control_read(void)
{
    u32 value;
    __asm__ volatile("mrc p15,0,%0,c1,c0,0":"=r"(value));
    return value;
}
#define CONTROL_READ control_read
#define FATAL_MASK() __asm__ volatile("cpsid if":::"memory","cc")
#define RAM_READ(p) (*(volatile const u32*)(p))
#define FAULT_READ(a,b) do { \
    __asm__ volatile("mrc p15,0,%0,c5,c0,0":"=r"(a)); \
    __asm__ volatile("mrc p15,0,%0,c6,c0,0":"=r"(b)); \
} while(0)
static u32 gate_read(u32 index)
{
    u32 value;
    __asm__ volatile("dsb sy":::"memory");
    value=*(volatile u32*)(0xfc501010u+index*4);
    __asm__ volatile("dsb sy":::"memory");
    return value;
}
static void gate_write(u32 index,u32 value)
{
    __asm__ volatile("dsb sy":::"memory");
    *(volatile u32*)(0xfc501010u+index*4)=value;
    __asm__ volatile("dsb sy":::"memory");
}
#define GATE_READ gate_read
#define GATE_WRITE gate_write
#define GATE_STOP() do { for(;;)__asm__ volatile("nop"); } while(0)
#endif
#ifndef GATE_POLL_LIMIT
#define GATE_POLL_LIMIT 1000000u
#endif
void resident_alignment(void)
{
    u32 before=CONTROL_READ(),after;
    /* Same native noalign path as mmu.c, including BOTH saved CR values.
     * GCC 4.8 emits unaligned normal-RAM word stores before alignment_init.
     * Require ARMv7 U bit; preserve every other SCTLR bit. No MMIO changes. */
    if(!(before&(1u<<22))) {
        LOG("<0>T4_ALIGN REFUSED SCTLR=%08x U=0 - STOP\n",before);
        GATE_STOP();return;
    }
    NOALIGN((char*)0);
    after=CONTROL_READ();
    LOG("<5>T4_ALIGN noalign EARLY before=%08x after=%08x\n",before,after);
    if(after!=(before&~2u)) {
        LOG("<0>T4_ALIGN CONTROL MISMATCH - STOP\n");GATE_STOP();
    }
}
void resident_progress(u32 stage)
{
    static const char *const names[]={"PERCPU RETURNED","IRQ_DESC BEGIN",
        "IRQ_DESC RETURNED","VIC INIT RETURNED"};
    if(stage<4) LOG("<5>T4_INIT %s\n",names[stage]);
}
static volatile u32 fatal_seen;
static int ram_words(u32 p,u32 bytes)
{
    return bytes<=0x10000000u && p>=0xc0000000u &&
        p<=0xd0000000u-bytes && !(p&3u);
}
static void fatal_cache(u32 cache,u32 object,u32 offset)
{
    u32 cpu;
    LOG("<0>T4_SLAB cache=%08x object=%08x offset=%08x addr=%08x\n",
        cache,object,offset,object+offset);
    /* Only inspect aligned words wholly inside the mapped 256MB RAM bank.
     * No speculative dereference of the faulting pointer or MMIO. */
    if(ram_words(cache,68)) {
        cpu=RAM_READ(cache);
        LOG("<0>T4_SLAB size=%08x objsize=%08x offset=%08x nameptr=%08x\n",
            RAM_READ(cache+12),RAM_READ(cache+16),RAM_READ(cache+20),RAM_READ(cache+64));
        if(ram_words(cpu,16)) LOG("<0>T4_SLAB cpu=%08x free=%08x tid=%08x page=%08x\n",
            cpu,RAM_READ(cpu),RAM_READ(cpu+4),RAM_READ(cpu+8));
    }
    if(ram_words(object,16)) LOG("<0>T4_SLAB object words=%08x %08x %08x %08x\n",
        RAM_READ(object),RAM_READ(object+4),RAM_READ(object+8),RAM_READ(object+12));
}
void resident_fatal(const char *reason,const u32 *regs,int error)
{
    u32 fsr,far,i;
    FATAL_MASK();
    if(fatal_seen) {GATE_STOP();return;}
    fatal_seen=1;
    FAULT_READ(fsr,far);
    /* Deliberate diagnostic halt BEFORE die's spin_unlock_irq and do_exit.
     * This preserves the first failure rather than a nested IRQ Oops storm. */
    LOG("<0>T4_FIRST_FATAL %s error=%08x - STOP\n",reason,(u32)error);
    if(regs) LOG("<0>T4_FIRST_FATAL PC=%08x LR=%08x CPSR=%08x\n",
        regs[15],regs[14],regs[16]);
    LOG("<0>T4_FIRST_FATAL DFSR=%08x DFAR=%08x SCTLR=%08x\n",
        fsr,far,CONTROL_READ());
    if(regs) {
        for(i=0;i<12;i+=4) LOG("<0>T4_REG R%u=%08x R%u=%08x R%u=%08x R%u=%08x\n",
            i,regs[i],i+1,regs[i+1],i+2,regs[i+2],i+3,regs[i+3]);
        LOG("<0>T4_REG R12=%08x SP=%08x\n",regs[12],regs[13]);
        if(regs[15]==0xc007ef2c) fatal_cache(regs[5],regs[4],regs[12]);
    }
    GATE_STOP();
}
void resident_gate(int index,int enable)
{
    u32 value,request,n;
    if(index<0 || index>=64) {
        LOG("<0>T4_CLK INVALID gate=%d - STOP\n",index);GATE_STOP();return;
    }
    /* Display domain, CLCD, MIPI DSIM, display pipe: preserve only OFF requests.
     * Indices are shared with verified c5cee8c clcd.c/mipi_dsim.h. */
    if(!enable && (index==0x0b || index==0x0f || index==0x11 || index==0x12)) {
        LOG("<5>T4_CLK KEEP_DISPLAY gate=%02x request=OFF\n",index);return;
    }
    LOG("<5>T4_CLK gate=%02x enable=%d BEGIN\n",index,enable);
    value=GATE_READ((u32)index);
    request=enable ? value|15u : value&~15u;
    GATE_WRITE((u32)index,request);
    for(n=0;n<GATE_POLL_LIMIT;n++) {
        value=GATE_READ((u32)index);
        if((value&15u)==((value>>4)&15u)) {
            LOG("<5>T4_CLK gate=%02x RETURNED reg=%08x\n",index,value);return;
        }
    }
    LOG("<0>T4_CLK gate=%02x TIMEOUT requested=%08x last=%08x - STOP\n",index,request,value);
    GATE_STOP();
}
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
    resident_alignment();
    LOG("<5>T4_MEMSET ORIGINAL_DEST_RETURN active; SLUB checks retained\n");
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
