/* Diagnostic section mappings only; leave all occupied kernel entries intact. */
static int t4_add_diag_maps(volatile unsigned *pt,unsigned code,unsigned io,unsigned fb)
{
    unsigned first=fb>>20,last=(fb+640u*960u*4u-1)>>20,i;
    if((code&3)!=2 || (io&3)!=2 || (code&0x10) ||
       (code>>20) || (io>>20) || fb<0x48000000u ||
       fb>0x50000000u-640u*960u*4u || (fb&15))return 0;
    if(pt[0x43f] || pt[0x440] || pt[0xc3e])return 0;
    for(i=first;i<=last;i++)if(pt[i] || pt[i+0x800])return 0;
    pt[0x43f]=0x43f00000u|code;
    pt[0x440]=0x44000000u|code;
    pt[0xc3e]=0x03e00000u|code;
    for(i=first;i<=last;i++) {
        pt[i]=(i<<20)|io;
        /* Native Linux console uses __va(low physical framebuffer).
         * This kernel-space direct map survives prepare_page_table. */
        pt[i+0x800]=((i-0x400)<<20)|code;
    }
    return 1;
}
