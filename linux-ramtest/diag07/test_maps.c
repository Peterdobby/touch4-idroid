#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "diag_maps.h"
static unsigned pt[4096],before[4096];
int main(void)
{
    unsigned i;
    pt[0]=0xc0e;pt[0xc00]=0xc0e;pt[0xc01]=0x100c0e;
    memcpy(before,pt,sizeof(pt));
    assert(t4_add_diag_maps(pt,0xc0e,0xc12,0x48104580));
    for(i=0;i<4096;i++) {
        unsigned expected=before[i];
        if(i==0x43f || i==0x440)expected=(i<<20)|0xc0e;
        if(i>=0x481 && i<=0x483)expected=(i<<20)|0xc12;
        if(i>=0xc81 && i<=0xc83)expected=((i-0xc00)<<20)|0xc0e;
        assert(pt[i]==expected);
    }
    /* Existing mappings must never be overwritten, including later conflicts. */
    memset(pt,0,sizeof(pt));pt[0x483]=0xdeadbeef;memcpy(before,pt,sizeof(pt));
    assert(!t4_add_diag_maps(pt,0xc0e,0xc12,0x48104580));
    assert(!memcmp(before,pt,sizeof(pt)));
    memset(pt,0,sizeof(pt));pt[0xc83]=0xdeadbeef;memcpy(before,pt,sizeof(pt));
    assert(!t4_add_diag_maps(pt,0xc0e,0xc12,0x48104580));
    assert(!memcmp(before,pt,sizeof(pt)));
    memset(pt,0,sizeof(pt));pt[0x440]=2;memcpy(before,pt,sizeof(pt));
    assert(!t4_add_diag_maps(pt,0xc0e,0xc12,0x48104580));
    assert(!memcmp(before,pt,sizeof(pt)));
    memset(pt,0,sizeof(pt));
    assert(!t4_add_diag_maps(pt,0xc1e,0xc12,0x48104580));
    assert(!t4_add_diag_maps(pt,0xc0e,0xc12,0x48000001));
    assert(!t4_add_diag_maps(pt,0xc0e,0xc12,0x4ffff000));
    for(i=0;i<4096;i++)assert(pt[i]==0);
    puts("DIAG_MAPS_PASSED: exact entries; conflict rollback; executable flags; framebuffer bounds");
    return 0;
}
