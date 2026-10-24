/* Three real routes around the hardware-tested public OpeniBoot binary.
 * Native initialization, USB, CPU shutdown and original GPIO reads are reused.
 * The only new operations are drawing, copying owned RAM images and dispatch.
 */
typedef unsigned uint32_t;
#include "9x15.h"
#include "menu-config.h"
#define WORD(a) (*(volatile unsigned *)(a))
#define PRINT ((void (*)(const char *,...))0xf66d)
#define CONSOLE ((void (*)(void))0x8209)
#define TEXT ((void (*)(int))0x370d)
#define TASK_INIT ((void (*)(void *,const char *,unsigned))0xed15)
#define TASK_START ((int (*)(void *,void *,void *))0xe865)
#define YIELD ((int (*)(void))0xea59)
#define GO ((int (*)(int,char **))0x3051)
extern const unsigned char service_blob[],service_end[];
static unsigned char ui_task[256] __attribute__((aligned(8)));
static volatile unsigned *pixels;
static unsigned selected,console_mode,width,height,attached;
static const char *titles[]={"iOS","Android","Console"};
static unsigned pressed(unsigned pin){return !(WORD(0xbfa00000+pin*4)&1);}
static void flush(void)
{
    unsigned a=(unsigned)pixels,end=a+width*height*4;
    for(;a<end;a+=64)__asm__ volatile("mcr p15,0,%0,c7,c10,1"::"r"(a):"memory");
    __asm__ volatile("dsb sy":::"memory");
}
static void clear(void){for(unsigned i=0;i<width*height;i++)pixels[i]=0;}
static void label(const char *s,unsigned x,unsigned y,unsigned scale,unsigned color)
{
    unsigned c;
    while((c=(unsigned char)*s++)) {
        if(x+fontWidth*scale>width)break;
        for(unsigned sy=0;sy<fontHeight;sy++)for(unsigned sx=0;sx<fontWidth;sx++) {
            unsigned bit=fontWidth*fontHeight*c+fontWidth*sy+sx;
            if((fontData[bit/8]>>(bit%8))&1)
                for(unsigned dy=0;dy<scale;dy++)for(unsigned dx=0;dx<scale;dx++)
                    pixels[(y+sy*scale+dy)*width+x+sx*scale+dx]=color;
        }
        x+=fontWidth*scale;
    }
}
static void draw(void)
{
    TEXT(0);clear();label("OpeniBoot",40,48,3,0xffffff);
    for(unsigned i=0;i<3;i++) {
        unsigned row=200+i*112;
        if(i==selected)for(unsigned y=row-8;y<row+56;y++)for(unsigned x=16;x<width-16;x++)
            pixels[y*width+x]=0xffffff;
        label(titles[i],40,row,3,i==selected ? 0:0xffffff);
    }
    label("Volume: select",40,720,2,0xaaaaaa);
    label("Home: boot / enter",40,764,2,0xaaaaaa);
    label("T4 MENU 04",40,880,2,0x666666);flush();
    PRINT("[T4_MENU_04] MENU_DRAW entries=3 selected=%s\n",titles[selected]);
}
static void wait_home_release(void){while(pressed(0))YIELD();}
static void activate(unsigned index)
{
    wait_home_release();
    if(index==2) {
        console_mode=1;clear();flush();TEXT(1);
        PRINT("OpeniBoot Console; USB ACM 0525:1280.\nPress Home to return to the menu.\n");
        return;
    }
    PRINT("[T4_MENU_04] %s boot requested; existing iBoot filesystem route\n",titles[index]);
    if((unsigned)(service_end-service_blob)!=SERVICE_SIZE ||
       WORD((unsigned)service_blob+MODE_OFFSET)!=1) {
        PRINT("[T4_MENU_04] REFUSED: service image layout mismatch\n");return;
    }
    /* Both operating systems use the original iBoot filesystem reader.
     * The current iOS's exact Kit DeviceTree is a separate new boot file. */
    for(unsigned i=0;i<SERVICE_SIZE;i+=4)
        WORD(0x44000000+i)=WORD((unsigned)service_blob+i);
    WORD(0x44000000+MODE_OFFSET)=index==0 ? 4:2;
    __asm__ volatile("dsb sy":::"memory");
    char *args[]={"go","0x44000000"};
    /* Exact original command: PMU stage, delay, critical section, watchdog,
     * cache/MMU shutdown and ARM entry. No replacement hardware sequence. */
    int result=GO(2,args);
    PRINT("[T4_MENU_04] native go returned %d; boot unconfirmed\n",result);
}
void t4_test_ios(void){activate(0);}
void t4_test_android(void){activate(1);}
void t4_test_console(void){activate(2);}
static void poll(void *unused)
{
    (void)unused;unsigned old=0;
    for(;;) {
        unsigned keys=pressed(0)|(pressed(1)<<1)|(pressed(2)<<2)|(pressed(3)<<3);
        unsigned edge=keys&~old;
        if(console_mode) {
            if(edge&1){wait_home_release();console_mode=0;draw();old=0;continue;}
        } else {
            if(edge&8){selected=selected==2 ? 0:selected+1;draw();}
            else if(edge&4){selected=selected==0 ? 2:selected-1;draw();}
            if(edge&1){activate(selected);old=0;continue;}
        }
        old=keys;YIELD();
    }
}
void t4_menu_live(void)
{
    if(attached)return;
    width=WORD(0x3ff94);height=WORD(0x3ff98);
    pixels=(volatile unsigned *)WORD(0x42de8);unsigned window=WORD(0x42dec);
    if(width!=640 || height!=960 || !window || WORD(window+32)!=6 || WORD(window+28)!=640 ||
       WORD(window+16)!=(unsigned)pixels || (unsigned)pixels<0x48000000 ||
       (unsigned)pixels>0x50000000-640*960*4 || ((unsigned)pixels&15)) {
        PRINT("[T4_MENU_04] REFUSED: inherited framebuffer contract\n");return;
    }
    selected=0;console_mode=0;attached=1;draw();
    TASK_INIT(ui_task,"T4 boot menu",0x100000);
    int result=TASK_START(ui_task,poll,0);
    PRINT("[T4_MENU_04] menu task started=%d; original ACM retained\n",result);
}
void t4_menu_main(void){CONSOLE();t4_menu_live();}
