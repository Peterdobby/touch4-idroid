/* RAM-only diagnostic adaptation of c5cee8c actions.c:boot_linux.
 * Reuses the public binary's critical/exit/cache/MMU functions, without
 * modifying any public hardware init or persistent storage. Checkpoints are
 * drawn by this module directly into the validated inherited framebuffer.
 */
#include "sizes.h"
#include "../cmdline.h"
#include "atags.h"
#include <mach/t4_ramfont.h>
typedef unsigned u32;
#define WORD(a) (*(volatile u32 *)(a))
#define PRINT ((int (*)(const char *,...))0xf66d)
#define TEXT ((void (*)(int))0x370d)
#define CALL(a) ((void (*)(void))(a))()
#define INFO ((volatile u32 *)0x43f00000)
static char args[160];
static volatile u32 *pixels;
extern void t4_branch_linux(u32,u32,u32) __attribute__((noreturn));

static u32 crc32(const volatile unsigned char *p,u32 n)
{
    u32 crc=~0u,i;
    while(n--) {crc^=*p++;for(i=0;i<8;i++)crc=(crc>>1)^(0xedb88320u&(0u-(crc&1)));}
    return ~crc;
}
static void flush(u32 begin,u32 end)
{
    u32 ctl;
    __asm__ volatile("mrc p15,0,%0,c1,c0,0":"=r"(ctl));
    if(ctl&4) for(begin&=~63u;begin<end;begin+=64)
        __asm__ volatile("mcr p15,0,%0,c7,c10,1"::"r"(begin):"memory");
    __asm__ volatile("dsb sy":::"memory");
}
static void mark(u32 step,const char *s)
{
    u32 x=16,y=24+(step>12 ? step-13:step)*64,row,bit,dx,dy,c;
    INFO[12]=step;
    for(row=y;row<y+16;row++)for(bit=0;bit<640;bit++)pixels[row*640+bit]=0;
    while((c=(unsigned char)*s++) && x<624) {
        for(row=0;row<8;row++) for(bit=0;bit<8;bit++)
            for(dy=0;dy<2;dy++) for(dx=0;dx<2;dx++)
                pixels[(y+row*2+dy)*640+x+bit*2+dx]=
                    (t4_ramfont[c*8+row]&(0x80>>bit)) ? 0xffffff : 0;
        x+=16;
    }
    flush((u32)(pixels+y*640),(u32)(pixels+(y+16)*640));
    flush((u32)INFO,(u32)(INFO+13));
}
static int validate(void)
{
    u32 fb=WORD(0x42de8),w=WORD(0x42dec);
    if(crc32((void*)0x2e3c,0x3030-0x2e3c)!=NATIVE_BOOT_CRC ||
       crc32((void*)0x42000000,KERNEL_SIZE)!=KERNEL_CRC ||
       crc32((void*)0x43000000,INITRD_SIZE)!=INITRD_CRC || WORD(0x42000024)!=0x016f2818) {
        PRINT("[T4_LINUX] REFUSED: baseline/kernel/initramfs checksum\n");return 0;
    }
    if(!w || WORD(0x3ff94)!=640 || WORD(0x3ff98)!=960 || WORD(w+16)!=fb ||
       WORD(w+28)!=640 || WORD(w+32)!=6 || fb<0x48000000 ||
       fb>0x50000000-640*960*4 || (fb&15)) {
        PRINT("[T4_LINUX] REFUSED: inherited framebuffer\n");return 0;
    }
    pixels=(volatile u32*)fb;
    if(!t4_make_cmdline(args,sizeof(args),fb-0x40000000))return 0;
    PRINT("[T4_LINUX] inherited framebuffer=%08x; machine_id=3564; RAM_ONLY\n",fb);
    PRINT("[T4_LINUX] prepared cmdline: %s\n",args);
    return 1;
}
void t4_linux_stage(void)
{
    u32 i;
    if(!validate())return;
    TEXT(0); /* Same proven switch as the RAM menu; keep printf off our marks. */
    for(i=0;i<640*960;i++)pixels[i]=0;
    flush((u32)pixels,(u32)(pixels+640*960));
    mark(0,"ANDROID INIT 02 - NATIVE CONSOLE / RAM INIT");
    PRINT("T4_LINUX_STAGED_NOT_EXECUTED\n");
}

void t4_linux_start(void)
{
    u32 i;
    if(!validate())return;
    for(i=0;i<16;i++)INFO[i]=0;
    INFO[1]=(u32)pixels-0x40000000;INFO[2]=640;INFO[3]=960;INFO[4]=640;INFO[5]=6;
    INFO[0]=0x54344c58;
    PRINT("[T4_LINUX] ANDROID INIT 02: native console and RAM init attempt; storage drivers blocked\n");
    mark(1,"1 BEFORE CRITICAL");
    CALL(0x4c1); /* original EnterCriticalSection */
    mark(2,"2 CRITICAL RETURNED");
    CALL(0x391); /* original exit_modules, verified empty table */
    mark(3,"3 MODULES RETURNED");
    mark(4,"4 BEFORE CACHE OFF");
    CALL(0x829); /* original arm_disable_caches */
    mark(5,"5 CACHE OFF RETURNED");
    CALL(0x12da1); /* original mmu_disable */
    mark(6,"6 MMU OFF RETURNED");
    /* All calls into the original low-memory firmware are now complete. */
    if(crc32((void*)0x02000000,KERNEL_SIZE)!=KERNEL_CRC) {
        mark(7,"7 LOW KERNEL CRC FAILED");for(;;);
    }
    for(i=0;i<INITRD_SIZE;i++)((volatile unsigned char*)0x48000000)[i]=
        ((volatile unsigned char*)0x43000000)[i];
    if(!t4_build_atags((volatile u32*)0x100,0x1000/4,args,INITRD_SIZE,INITRD_UNPACKED_SIZE)) {
        mark(7,"7 ATAG BUILD FAILED");for(;;);
    }
    mark(7,"7 TAGS INITRD READY");
    mark(8,"8 BEFORE ZIMAGE BRANCH");
    t4_branch_linux(0x02000000,3564,0x100);
}
static void hex_at(u32 row,const char *name,u32 value)
{
    char line[32];u32 i=0,j;
    while(name[i] && i<20) {line[i]=name[i];i++;}
    for(j=0;j<8;j++)line[i++ ]="0123456789ABCDEF"[(value>>(28-4*j))&15];
    line[i]=0;mark(row,line);
}
/* The real decompressor calls putstr; only its pixel-output implementation is
 * replaced so cacheable low-alias pixels cannot hide the messages. */
static u32 logcol,logrow;
static void decomp_text(const char *s)
{
    u32 c,x,y,n;
    mark(13,"13A DECOMPRESS C TEXT");
    for(n=0;n<4096 && (c=(unsigned char)*s++);n++) {
        if(c=='\r')logcol=0;
        else if(c=='\n') {logcol=0;logrow++;}
        else {
            if(logrow>=32)logrow=0;
            for(y=0;y<8;y++)for(x=0;x<8;x++)
                pixels[(256+logrow*8+y)*640+logcol*8+x]=
                    (t4_ramfont[c*8+y]&(0x80>>x)) ? 0xffffff:0;
            if(++logcol==80){logcol=0;logrow++;}
        }
    }
    flush((u32)(pixels+256*640),(u32)(pixels+512*640));
}
void t4_head_probe_screen(const u32 *r,u32 step)
{
    u32 i,got;
    if(step==9 && (r[0]!=0 || r[1]!=3564 || r[2]!=0x100 || WORD(0x104)!=0x54410001)) {
        mark(9,"9 ENTRY REGISTERS BAD");for(;;);
    }
    if(step==9)mark(9,"9 ZIMAGE HEADER PROBE");
    if(step==12)mark(12,"12 MMU WRITE RETURNED");
    if(step==13) {
        for(i=0;i<576*640;i++)pixels[i]=0;
        flush((u32)pixels,(u32)(pixels+576*640));
        mark(13,"13 BEFORE DECOMPRESS C");
        if(r[0]!=0x8000 || r[3]!=3564) {
            mark(13,"13 DECOMPRESS ARGS BAD - STOP");for(;;);
        }
    }
    if(step==30)decomp_text((const char*)r[0]);
    if(step==14) {
        mark(14,"14 DECOMPRESS RETURNED");
        got=crc32((void*)0x8000,IMAGE_SIZE);
        hex_at(16,"IMAGE CRC ",got);
        if(got!=IMAGE_CRC) {
            mark(14,"14 IMAGE CRC FAILED - STOP");for(;;);
        }
        mark(14,"14 IMAGE CRC OK");
    }
    if(step==15) {
        if(r[0]!=0 || r[4]!=0x8000 || r[7]!=3564 || r[8]!=0x100) {
            mark(15,"15 CORE ARGS BAD - STOP");for(;;);
        }
        if(crc32((void*)0x8000,IMAGE_SIZE)!=IMAGE_CRC) {
            mark(15,"15 IMAGE CRC BAD - STOP");for(;;);
        }
        mark(15,"15 NATIVE KERNEL / ANDROID INIT 02");
    }
}
