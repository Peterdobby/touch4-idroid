/* RAM overlay for SHA256 61adbd...a8c, NOT a rebuilt OpeniBoot.
 * Hardware init and the native reboot command remain in the proven public binary.
 * Home on iOS emits a host-assisted boot request over the existing ACM log.
 * Fixed addresses are verified by the packaging script against that hash.
 */
typedef unsigned int uint32_t;
#include "9x15.h"

#define PRINT ((void (*)(const char *, ...))0xf66d)
#define CONSOLE ((void (*)(void))0x8209)
#define TEXT ((void (*)(int))0x370d)
#define TASK_INIT ((void (*)(void *, const char *, unsigned))0xed15)
#define TASK_START ((int (*)(void *, void *, void *))0xe865)
#define YIELD ((int (*)(void))0xea59)
#define WORD(a) (*(volatile unsigned *)(a))

static unsigned char ui_task[256] __attribute__((aligned(8)));
static unsigned selected;
static volatile unsigned *pixels;
static unsigned width, height;
static const char *titles[3] = {"iOS", "Test Entry", "Console"};

static unsigned pressed(unsigned pin)
{
    /* Exact gpio_pin_state/buttons_is_pushed semantics from c5cee8c.
     * Reads only. No GPIO or button initialization is performed here. */
    return !(WORD(0xbfa00000 + pin*4) & 1);
}

static void flush_pixels(void)
{
    unsigned a=(unsigned)pixels;
    unsigned end=a+width*height*4;
    for(;a<end;a+=64)
        __asm__ volatile("mcr p15, 0, %0, c7, c10, 1" :: "r"(a) : "memory");
    __asm__ volatile("dsb sy" ::: "memory");
}

static void label(const char *s,unsigned x,unsigned y,unsigned color)
{
    unsigned c,sx,sy,dx,dy;
    while((c=(unsigned char)*s++)) {
        for(sy=0;sy<fontHeight;sy++) for(sx=0;sx<fontWidth;sx++) {
            unsigned bit=fontWidth*fontHeight*c+fontWidth*sy+sx;
            if((fontData[bit/8]>>(bit%8))&1)
                for(dy=0;dy<3;dy++) for(dx=0;dx<3;dx++)
                    pixels[(y+sy*3+dy)*width+x+sx*3+dx]=color;
        }
        x+=fontWidth*3;
    }
}

static void draw(void)
{
    unsigned i,x,y;
    for(i=0;i<width*height;i++) pixels[i]=0;
    for(i=0;i<3;i++) {
        unsigned row=120+i*96;
        if(i==selected)
            for(y=row-8;y<row+56;y++) for(x=16;x<width-16;x++)
                pixels[y*width+x]=0xffffff;
        label(titles[i],40,row,i==selected ? 0 : 0xffffff);
    }
    flush_pixels();
    PRINT("[PUBLIC_MENU_01] draw returned; entries=3 selected=%s; UI_ONLY\n",titles[selected]);
}

static void poll(void *unused)
{
    unsigned old=0;
    (void)unused;
    PRINT("[PUBLIC_MENU_01] button task running\n");
    for(;;) {
        unsigned keys=pressed(0)|(pressed(1)<<1)|(pressed(2)<<2)|(pressed(3)<<3);
        unsigned edge=keys&~old;
        if(edge&(2|8)) { selected=selected==2 ? 0 : selected+1;draw(); }
        else if(edge&4) { selected=selected==0 ? 2 : selected-1;draw(); }
        if(edge&1) {
            if(selected==0)
                PRINT("[PUBLIC_MENU_01] IOS_BOOT_REQUEST\n");
            else
                PRINT("[PUBLIC_MENU_01] Home: %s; activation disabled\n",titles[selected]);
        }
        old=keys;
        YIELD();
    }
}

void t4_public_main(void)
{
    /* Original Console calls original init_modules and starts original ACM.
     * Calling its absolute address avoids the redirected OpenIBootMain GOT. */
    CONSOLE();
    PRINT("[PUBLIC_MENU_01] original console returned; original hardware init reused\n");
    width=WORD(0x3ff94);height=WORD(0x3ff98);
    pixels=(volatile unsigned *)WORD(0x42de8);
    unsigned window=WORD(0x42dec);
    unsigned color=window ? WORD(window+32) : 0;
    PRINT("[PUBLIC_MENU_01] fb=%08x width=%u height=%u colorspace=%u\n",
          (unsigned)pixels,width,height,color);
    unsigned stride=window ? WORD(window+28) : 0;
    if(width!=640 || height!=960 || color!=6 || stride!=width ||
       (unsigned)pixels<0x48000000 || (unsigned)pixels+width*height*4>0x50000000 ||
       ((unsigned)pixels&15) || WORD(window+16)!=(unsigned)pixels) {
        PRINT("[PUBLIC_MENU_01] framebuffer layout mismatch; renderer not called\n");
        return;
    }
    TEXT(0);
    selected=0;
    draw();
    TASK_INIT(ui_task,"public menu",0x100000);
    int result=TASK_START(ui_task,poll,0);
    PRINT("[PUBLIC_MENU_01] task_start returned %d; ACM stays active\n",result);
}
