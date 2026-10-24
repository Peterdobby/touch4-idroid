#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "sizes.h"
#include "../cmdline.h"
#include "atags.h"
int main(void)
{
    unsigned b[1025],n,off=0,i;char line[160];
    unsigned ids[]={0x54410001,0x54410002,0x54410004,0x54420005,0x54410009};
    assert(sizeof(unsigned)==4);
    assert(t4_make_cmdline(line,sizeof(line),0x08104580));
    for(i=0;i<1025;i++)b[i]=0xa5a5a5a5;
    n=t4_build_atags(b,1024,line,INITRD_SIZE,INITRD_UNPACKED_SIZE);
    for(i=0;i<5;i++) {assert(b[off+1]==ids[i]);assert(b[off]>=2);off+=b[off];}
    assert(off+2==n && b[off]==0 && b[off+1]==0 && b[n]==0xa5a5a5a5);
    assert(b[0]==5 && b[2]==1 && b[3]==4096 && b[4]==0);
    assert(b[5]==4 && b[7]==0x10000000 && b[8]==0);
    assert(b[14]==4 && b[16]==0x08000000 && b[17]==INITRD_SIZE);
    assert(!strcmp((const char*)(b+20),line));
    assert(t4_build_atags(b,n-1,line,INITRD_SIZE,INITRD_UNPACKED_SIZE)==0);
    puts("ATAG_LAYOUT_AND_BOUNDS_PASSED");
    return 0;
}
