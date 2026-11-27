/* Early Linux printk console over OpeniBoot's inherited RAM framebuffer.
 * No CLCD/MIPI/GPIO programming. Enabled only by validated t4fb= parameter.
 */
#include <linux/kernel.h>
#include <linux/init.h>
#include <linux/console.h>
#include <linux/memblock.h>
#include <linux/mm.h>
#include <linux/fb.h>
#include <linux/string.h>
#include <asm/memory.h>
#include <asm/cacheflush.h>
#include <mach/t4_ramfont.h>

static unsigned long fb_phys;
static unsigned int *pixels;
static unsigned int col,row;
/* Nonzero while userspace holds /dev/fb0: printk is not painted over the UI.
 * Messages stay in the log buffer (dmesg); oops and panic still paint. */
static int fb_users;
#define FB_BYTES (640*960*4)
/* 8x8 glyphs doubled: 40 columns by 60 rows on the retina panel. */
#define COLS 40
#define ROWS 60

static int __init ramfb_param(char *s)
{
    unsigned long n=simple_strtoul(s,NULL,0);
    if(n>=0x08000000 && n<=0x10000000-640*960*4 && !(n&15)) fb_phys=n;
    return 0;
}
early_param("t4fb",ramfb_param);

void __init t4_ramfb_reserve(void)
{
    if(fb_phys) memblock_reserve(fb_phys&PAGE_MASK,
        PAGE_ALIGN((fb_phys&~PAGE_MASK)+640*960*4));
    memblock_reserve(0x03f00000,PAGE_SIZE);
}

static void ramfb_write(struct console *co,const char *s,unsigned int count)
{
    unsigned int c,x,y,v,*p;
    (void)co;
    if(!pixels) return;
    if(fb_users && !oops_in_progress && !test_taint(TAINT_DIE)) return;
    while(count--) {
        c=(unsigned char)*s++;
        if(c=='\r') { col=0;continue; }
        if(c=='\n') { col=0;row++; }
        else {
            if(c=='\t') c=' ';
            for(y=0;y<8;y++) for(x=0;x<8;x++) {
                v=(t4_ramfont[c*8+y]&(0x80>>x)) ? 0xffffff : 0;
                p=pixels+(row*16+y*2)*640+col*16+x*2;
                p[0]=p[1]=p[640]=p[641]=v;
            }
            if(++col==COLS) { col=0;row++; }
        }
        if(row>=ROWS) {
            memmove(pixels,pixels+16*640,(960-16)*640*4);
            memset(pixels+(960-16)*640,0,16*640*4);
            row=ROWS-1;
        }
        /* Clear the rest of a new line so old text never shows through. */
        if(col==0) memset(pixels+row*16*640,0,16*640*4);
    }
    __cpuc_flush_dcache_area(pixels,FB_BYTES);
}

static struct console ramfb_console={
    .name="t4fb", .write=ramfb_write,
    .flags=CON_ENABLED|CON_PRINTBUFFER, .index=-1,
};

void __init t4_ramfb_console_init(void)
{
    if(!fb_phys) return;
    pixels=__va(fb_phys);col=row=0;
    memset(pixels,0,FB_BYTES); /* drop the bootloader text */
    __cpuc_flush_dcache_area(pixels,FB_BYTES);
    register_console(&ramfb_console);
    printk(KERN_NOTICE "T4_LINUX_RAM_01: Linux printk console active; no storage mounted\n");
}

/* Minimal fbdev over the same inherited buffer; no display register access. */
static int t4fb_open(struct fb_info *info,int user) { if(user) fb_users++; return 0; }
static int t4fb_release(struct fb_info *info,int user) { if(user) fb_users--; return 0; }

static int t4fb_mmap(struct fb_info *info,struct vm_area_struct *vma)
{
    unsigned long off=vma->vm_pgoff<<PAGE_SHIFT;
    unsigned long size=vma->vm_end-vma->vm_start;
    unsigned long total=PAGE_ALIGN((fb_phys&~PAGE_MASK)+FB_BYTES);
    if(off>=total || size>total-off) return -EINVAL;
    vma->vm_flags|=VM_IO|VM_RESERVED;
    vma->vm_page_prot=pgprot_writecombine(vma->vm_page_prot);
    return remap_pfn_range(vma,vma->vm_start,((fb_phys&PAGE_MASK)+off)>>PAGE_SHIFT,
                           size,vma->vm_page_prot) ? -EAGAIN : 0;
}

static struct fb_ops t4fb_ops={
    .owner=THIS_MODULE, .fb_open=t4fb_open, .fb_release=t4fb_release,
    .fb_mmap=t4fb_mmap,
};

static int __init t4fb_register(void)
{
    struct fb_info *info;
    if(!fb_phys) return 0;
    info=framebuffer_alloc(0,NULL);
    if(!info) return -ENOMEM;
    strcpy(info->fix.id,"t4fb");
    info->fix.smem_start=fb_phys;
    info->fix.smem_len=FB_BYTES;
    info->fix.type=FB_TYPE_PACKED_PIXELS;
    info->fix.visual=FB_VISUAL_TRUECOLOR;
    info->fix.line_length=640*4;
    info->var.xres=info->var.xres_virtual=640;
    info->var.yres=info->var.yres_virtual=960;
    info->var.bits_per_pixel=32;
    info->var.red.offset=16; info->var.green.offset=8; info->var.blue.offset=0;
    info->var.red.length=info->var.green.length=info->var.blue.length=8;
    info->screen_base=(char __iomem *)__va(fb_phys);
    info->screen_size=FB_BYTES;
    info->fbops=&t4fb_ops;
    return register_framebuffer(info);
}
device_initcall(t4fb_register);
