/* Early Linux printk console over OpeniBoot's inherited RAM framebuffer.
 * No CLCD/MIPI/GPIO programming. Enabled only by validated t4fb= parameter.
 */
#include <linux/kernel.h>
#include <linux/init.h>
#include <linux/console.h>
#include <linux/memblock.h>
#include <linux/mm.h>
#include <asm/memory.h>
#include <asm/cacheflush.h>
#include <mach/t4_ramfont.h>

static unsigned long fb_phys;
static unsigned int *pixels;
static unsigned int col,row;

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
    unsigned int c,x,y;
    (void)co;
    if(!pixels) return;
    while(count--) {
        c=(unsigned char)*s++;
        if(c=='\r') { col=0;continue; }
        if(c=='\n') { col=0;row++; }
        else {
            if(c=='\t') c=' ';
            for(y=0;y<8;y++) for(x=0;x<8;x++)
                pixels[(row*8+y)*640+col*8+x]=
                    (t4_ramfont[c*8+y]&(0x80>>x)) ? 0xffffff : 0;
            if(++col==80) { col=0;row++; }
        }
        if(row>=120) {
            for(y=0;y<952*640;y++) pixels[y]=pixels[y+8*640];
            for(;y<960*640;y++) pixels[y]=0;
            row=119;
        }
    }
    __cpuc_flush_dcache_area(pixels,640*960*4);
}

static struct console ramfb_console={
    .name="t4fb", .write=ramfb_write,
    .flags=CON_ENABLED|CON_PRINTBUFFER, .index=-1,
};

void __init t4_ramfb_console_init(void)
{
    if(!fb_phys) return;
    pixels=__va(fb_phys);col=row=0;
    register_console(&ramfb_console);
    printk(KERN_NOTICE "T4_LINUX_RAM_01: Linux printk console active; no storage mounted\n");
}
