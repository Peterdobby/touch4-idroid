/* RAM-only adapter for the SHA256-pinned public c5cee8c binary.
 * No peripheral init, boot-image lookup, filesystem, or persistent writes.
 * Original boot_linux supplies ATAGs, shuts modules down, and jumps to Linux.
 */
#include "sizes.h"
#include "cmdline.h"
typedef unsigned u32;
#define WORD(a) (*(volatile u32 *)(a))
#define PRINT ((int (*)(const char *, ...))0xf66d)
#define NATIVE_BOOT_LINUX ((void (*)(const char *,u32))0x2e3d)
#define INFO ((volatile u32 *)0x43f00000)
#define MAGIC 0x54344c58u

static char args[160];

static u32 crc32(const volatile unsigned char *p, u32 n)
{
    u32 crc=~0u, i;
    while(n--) {
        crc^=*p++;
        for(i=0;i<8;i++) crc=(crc>>1)^(0xedb88320u & (0u-(crc&1)));
    }
    return ~crc;
}

static int validate(void)
{
    u32 fb=WORD(0x42de8), window=WORD(0x42dec);
    if(crc32((void *)0x2e3c,0x3030-0x2e3c)!=NATIVE_BOOT_CRC) {
        PRINT("[T4_LINUX] REFUSED: native boot_linux code differs from pinned baseline\n");
        return 0;
    }
    if(WORD(0x42000024)!=0x016f2818 ||
       crc32((void *)0x42000000,KERNEL_SIZE)!=KERNEL_CRC ||
       crc32((void *)0x43000000,INITRD_SIZE)!=INITRD_CRC) {
        PRINT("[T4_LINUX] REFUSED: kernel/initramfs checksum or zImage magic\n");
        return 0;
    }
    if(WORD(0x3ff94)!=640 || WORD(0x3ff98)!=960 || !window ||
       WORD(window+16)!=fb || WORD(window+28)!=640 || WORD(window+32)!=6 ||
       fb<0x48000000 || fb>0x50000000-640*960*4 || (fb&15)) {
        PRINT("[T4_LINUX] REFUSED: unsupported inherited framebuffer\n");
        return 0;
    }
    PRINT("[T4_LINUX] kernel CRC32=%08x bytes=%u; initramfs CRC32=%08x bytes=%u\n",
          KERNEL_CRC,KERNEL_SIZE,INITRD_CRC,INITRD_SIZE);
    PRINT("[T4_LINUX] inherited framebuffer=%08x; machine_id=3564; RAM_ONLY\n",fb);
    return 1;
}

void t4_linux_stage(void)
{
    if(!validate()) return;
    if(!t4_make_cmdline(args,sizeof(args),WORD(0x42de8)-0x40000000)) {
        PRINT("[T4_LINUX] REFUSED: command line buffer too small\n");
        return;
    }
    PRINT("[T4_LINUX] prepared cmdline: %s\n",args);
    PRINT("T4_LINUX_STAGED_NOT_EXECUTED\n");
}

void t4_linux_start(void)
{
    u32 fb,i;
    if(!validate()) return;
    fb=WORD(0x42de8)-0x40000000;
    if(!t4_make_cmdline(args,sizeof(args),fb)) return;
    /* Shared decompressor cursor block, at Linux physical 0x03f00000. */
    for(i=0;i<8;i++) INFO[i]=0;
    INFO[1]=fb; INFO[2]=640; INFO[3]=960; INFO[4]=640; INFO[5]=6;
    INFO[0]=MAGIC;
    /* Verified native boot_linux globals; avoid script_load_file's free()
     * of a fixed-RAM URI and leave the original BootEntry/iOS route untouched.
     * 0x41ffe000..0x42000000 is reserved staging space for native ATAG setup.
     */
    WORD(0x3fb4c)=0x42000000; /* kernel */
    WORD(0x3fb58)=KERNEL_SIZE;
    WORD(0x3fb50)=0x43000000; /* ramdisk */
    WORD(0x3fb5c)=INITRD_SIZE;
    WORD(0x3fb60)=(INITRD_UNPACKED_SIZE+1023)/1024;
    PRINT("[T4_LINUX] handoff requested; %s\n",args);
    PRINT("[T4_LINUX] ACM will stop; USB disappearance is NOT Linux success\n");
    /* Native shutdown may tear ACM down before queued text reaches the host. */
    NATIVE_BOOT_LINUX(args,3564);
    PRINT("[T4_LINUX] native boot_linux returned unexpectedly\n");
}
