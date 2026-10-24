/* Real Linux decompressor output to the inherited framebuffer, not UART.
 * Shared RAM block was validated by the host-loaded handoff adapter.
 */
#include <mach/t4_ramfont.h>
#define T4_INFO ((volatile unsigned int *)0x03f00000)
static inline void putc(int c)
{
    volatile unsigned int *v=T4_INFO,*fb;
    unsigned int x,y,col,row;
    if(v[0]!=0x54344c58 || v[2]!=640 || v[3]!=960 || v[4]!=640 || v[5]!=6 ||
       v[1]<0x08000000 || v[1]>0x10000000-640*960*4 || (v[1]&15)) return;
    fb=(volatile unsigned int *)v[1];col=v[6];row=v[7];
    if(col>=80 || row>=120) col=row=0;
    if(c=='\r') col=0;
    else if(c=='\n') { col=0;row++; }
    else {
        for(y=0;y<8;y++) for(x=0;x<8;x++)
            fb[(row*8+y)*640+col*8+x]=
                (t4_ramfont[((unsigned char)c)*8+y]&(0x80>>x)) ? 0xffffff : 0;
        if(++col==80) { col=0;row++; }
    }
    if(row>=120) row=0;
    v[6]=col;v[7]=row;
}
static inline void flush(void) { }
#define arch_decomp_setup()
#define arch_decomp_wdog()
