#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "cmdline.h"
int main(void)
{
    char b[160];unsigned n;
    memset(b,0xa5,sizeof(b));
    n=t4_make_cmdline(b,sizeof(b),0x08104580);
    assert(!strcmp(b,"console=t4fb0 loglevel=8 ignore_loglevel rdinit=/init panic=0 "
                     "t4fb=0x08104580 t4_test=" T4_TEST_NAME T4_EXTRA_ARGS));
    assert(n==strlen(b) && (unsigned char)b[n+1]==0xa5);
    /* Regression: console=t4fb0 must not capture framebuffer substitutions. */
    assert(strstr(b,"console=t4fb0 loglevel=8 ")==b);
    assert(strstr(b," t4fb=0x08104580 ")!=NULL);
    assert(t4_make_cmdline(b,n,0x08000000)==0);
    assert(t4_make_cmdline(b,n+1,0x08000000)==n);
    assert(strstr(b," t4fb=0x08000000 ")!=NULL);
    assert(t4_make_cmdline(b,sizeof(b),0x08104580)==n);
    puts("CMDLINE_REGRESSION_PASSED");
    puts(b);
    return 0;
}
