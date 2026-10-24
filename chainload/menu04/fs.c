/* Thin adapter to the owner's captured, already controlled iBoot6 environment.
 * It reads a single new local boot file through existing iBoot filesystem and
 * Image3 APIs, validates immutable payloads, and uses native CPU quiescence.
 * No exploit, signature-check patch, USB stack or storage writer is included.
 */
typedef unsigned uint32_t;
typedef unsigned u32;
#include "bundle.h"
#include "crc-table.h"
#include "bridges.h"
#include "ios7.h"
const volatile u32 t4_ios_size=0;
const volatile u32 t4_ios_crc=0;
#define WORD(a) (*(volatile u32 *)(a))
#define PRINT ((int (*)(const char *,...))0x5ff32699)
#define SETENV ((int (*)(const char *,const char *,int))0x5ff15ef5)
#define MOUNT ((int (*)(void))0x5ff00a45)
#define LOAD ((int (*)(const char *,u32 *,u32 *,u32,u32))0x5ff21c7d)
#define JUMP ((void (*)(u32,u32,u32,u32))0x5ff1cef1)
#define KERNEL_LOAD ((int (*)(const char *,u32 *))0x5ff19cc5)
#define BOOT_KERNEL ((void (*)(u32,u32))0x5ff00a29)
/* mode: 1=current iOS7, 2=Android, 3=read/validate only.
 * status and error are RAM mailboxes, readable after a stopped test. */
#define t4_mailbox ((volatile u32 *)0x43000f00)
/* Part of the adapter's actual initialized image, not unowned alignment tail. */
const volatile u32 t4_mode=2;
struct segment {u32 offset,size,dest,crc;};
static void status(u32 step,const char *s)
{
    t4_mailbox[3]=step;
    PRINT("[T4_MENU_04] %u %s\n",step,s);
    SETENV("t4-menu-status",s,0); /* in-memory variable only; no saveenv */
}
static __attribute__((noinline)) u32 crc(const void *data,u32 size)
{
    const unsigned char *p=data;u32 result=~0u;
    while(size--)result=(result>>8)^crc_table[(result^*p++)&255];
    return ~result;
}
static __attribute__((noinline)) void move(void *dest,const void *source,u32 size)
{
    unsigned char *d=dest;const unsigned char *s=source;
    if(d>s && d<s+size) {
        d+=size;s+=size;
        while(size && ((u32)d&3)){*--d=*--s;size--;}
        u32 *dw=(u32 *)d;const u32 *sw=(const u32 *)s;
        while(size>=4){*--dw=*--sw;size-=4;}
        d=(unsigned char *)dw;s=(const unsigned char *)sw;
        while(size--)*--d=*--s;
    } else {
        while(size && ((u32)d&3)){*d++=*s++;size--;}
        u32 *dw=(u32 *)d;const u32 *sw=(const u32 *)s;
        while(size>=4){*dw++=*sw++;size-=4;}
        d=(unsigned char *)dw;s=(const unsigned char *)sw;
        while(size--)*d++=*s++;
    }
}
static int fail(u32 code,const char *message)
{
    t4_mailbox[4]=code;status(23,message);return -1;
}
int t4_fsboot(void)
{
    u32 mode=t4_mode;
    t4_mailbox[0]=0x334d3454;t4_mailbox[1]=mode;t4_mailbox[4]=0;
    status(1,"IBOOT6_FS_ADAPTER_ENTERED");
    if(mode<1 || mode>4)return fail(1,"UNSUPPORTED_TEST_MODE");
    /* These setters change this iBoot instance's heap only. They do not save
     * environment or alter the persistent DRV6 boot-partition=2 settings. */
    if(SETENV("boot-partition","0",0) || SETENV("boot-ramdisk","",0))
        return fail(2,"RAM_ENVIRONMENT_FAILED");
    if(mode==1 && SETENV("boot-args","pio-error=0",0))
        return fail(9,"IOS_RAM_BOOTARGS_FAILED");
    status(2,"MOUNT_EXISTING_SYSTEM_READ_ONLY");
    int r=MOUNT();t4_mailbox[5]=(u32)r;
    if(r)return fail(3,"SYSTEM_MOUNT_FAILED");
    if(mode==4) {
        status(3,"LOAD_MATCHING_KIT_IBOOT");
        u32 address=0x44000000,size=0x100000;
        if(t4_ios_size<0x400 || t4_ios_size>0x80000)
            return fail(14,"IOS_PROFILE_MISSING");
        r=LOAD("/boot/boot/t4/ios-iboot.img3",&address,&size,0x69626f62,0);
        if(r || address!=0x44000000 || size!=t4_ios_size ||
           crc((void *)address,size)!=t4_ios_crc)
            return fail(15,"IOS_IBOOT_CHECKSUM_FAILED");
        status(4,"NATIVE_TARGET_IBOOT_HANDOFF");
        JUMP(0,address,0,0);
        return fail(16,"TARGET_IBOOT_RETURNED");
    }
    if(mode==1) {
        /* Exact Kit touch4-ios7 DeviceTree that belongs to the installed
         * 11D257 port. Cache it through the native get-devicetree contract:
         * 5ff15c7c returns these globals before consulting firmware images. */
        status(3,"LOAD_INSTALLED_IOS7_DEVICETREE_FILE");
        u32 dt_address=0x47f00000,dt_size=0x100000;
        r=LOAD("/boot/boot/t4/devicetree-ios7.img3",&dt_address,&dt_size,0x64747265,0);
        if(r || dt_address!=0x47f00000 || dt_size!=IOS7_DT_SIZE)
            return fail(10,"IOS7_DEVICETREE_LOAD_FAILED");
        if(crc((void *)dt_address,dt_size)!=IOS7_DT_CRC)
            return fail(13,"IOS7_DEVICETREE_CHECKSUM_FAILED");
        WORD(0x5ff47f84)=0x47f00000;WORD(0x5ff47f88)=IOS7_DT_SIZE;
        status(4,"LOAD_EXISTING_IOS7_KERNELCACHE");
        u32 entry=0;
        r=KERNEL_LOAD("/boot/System/Library/Caches/com.apple.kernelcaches/kernelcache",&entry);
        t4_mailbox[9]=(u32)r;t4_mailbox[10]=entry;t4_mailbox[11]=WORD(0x5ff47f98);
        if(r || !entry || !WORD(0x5ff47f98))return fail(11,"IOS7_KERNEL_LOAD_FAILED");
        status(5,"NATIVE_IOS_KERNEL_HANDOFF");
        BOOT_KERNEL(entry,WORD(0x5ff47f98));
        return fail(12,"IOS_KERNEL_HANDOFF_RETURNED");
    }
    status(3,"SYSTEM_MOUNT_OK_LOAD_ANDROID_FILE");
    u32 address=0x44000000,size=0x03000000;
    r=LOAD("/boot/boot/t4/android.img3",&address,&size,0x6b726e6c,0);
    t4_mailbox[6]=(u32)r;t4_mailbox[7]=address;t4_mailbox[8]=size;
    if(r || address!=0x44000000 || size!=BUNDLE_SIZE)
        return fail(4,"ANDROID_FILE_LOAD_FAILED");
    status(4,"ANDROID_FILE_DECODED_VALIDATE_HEADER");
    const u32 *header=(const u32 *)address;
    if(header[0]!=0x334d3454 || header[1]!=3 || header[2]!=4 || header[3]!=BUNDLE_SIZE ||
       WORD(address+0xffc)!=crc((void *)address,0xffc))
        return fail(5,"BUNDLE_HEADER_FAILED");
    struct segment segments[4];
    for(u32 i=0;i<4;i++) {
        const u32 *p=header+4+i*4;
        segments[i]=(struct segment){p[0],p[1],p[2],p[3]};
        if(p[0]!=expected[i][0] || p[1]!=expected[i][1] ||
           p[2]!=expected[i][2] || p[3]!=expected[i][3] ||
           p[0]>size || p[1]>size-p[0])return fail(6,"BUNDLE_LAYOUT_FAILED");
        status(5+i,i==0 ? "CRC_KERNEL":i==1 ? "CRC_INITRD":i==2 ? "CRC_HANDOFF":"CRC_OPENIBOOT");
        if(crc((void *)(address+p[0]),p[1])!=p[3])return fail(7,"PAYLOAD_CHECKSUM_FAILED");
    }
    if(mode==3){status(9,"LOCAL_ANDROID_BUNDLE_READ_VERIFIED");return -1;}
    /* Save all descriptors before overwriting the bundle's own header.
     * Copy the three small segments first; the initrd move overlaps source. */
    const u32 order[4]={0,2,3,1};
    for(u32 n=0;n<4;n++) {
        const struct segment *p=&segments[order[n]];
        status(10+n,order[n]==1 ? "MOVE_INITRD_BACKWARDS":"PLACE_IMMUTABLE_PAYLOAD");
        move((void *)p->dest,(void *)(address+p->offset),p->size);
    }
    /* Only our new native image's RAM wrapper target is adapted. Its raw
     * OpeniBoot hardware instructions are unchanged. */
    WORD(0x41000018)=0x43000421;
    move((void *)0x43000400,native_start_bytes,sizeof(native_start_bytes));
    move((void *)0x43000420,native_bridge_bytes,sizeof(native_bridge_bytes));
    status(14,"NATIVE_QUIESCE_AND_OPENIBOOT_REENTRY");
    JUMP(0,0x43000401,0,0);
    return fail(8,"NATIVE_JUMP_RETURNED");
}
