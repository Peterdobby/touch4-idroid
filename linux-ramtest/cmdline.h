/* Shared by the freestanding ARM adapter and a native regression test.
 * Construct fields in order; never search for the ambiguous text "t4fb".
 */
#ifndef T4_LINUX_CMDLINE_H
#define T4_LINUX_CMDLINE_H
#ifndef T4_TEST_NAME
#define T4_TEST_NAME "T4_LINUX_RAM_02"
#endif
#ifndef T4_EXTRA_ARGS
#define T4_EXTRA_ARGS ""
#endif
static unsigned t4_make_cmdline(char *out,unsigned capacity,unsigned fb)
{
    static const char prefix[]="console=t4fb0 loglevel=8 ignore_loglevel "
        "rdinit=/init panic=0 t4fb=0x";
    static const char suffix[]=" t4_test=" T4_TEST_NAME T4_EXTRA_ARGS;
    static const char hex[]="0123456789abcdef";
    unsigned n=0,i;
    if(capacity<(sizeof(prefix)-1)+8+sizeof(suffix)) return 0;
    for(i=0;i<sizeof(prefix)-1;i++) out[n++]=prefix[i];
    for(i=0;i<8;i++) out[n++]=hex[(fb>>(28-i*4))&15];
    for(i=0;i<sizeof(suffix);i++) out[n++]=suffix[i];
    return n-1;
}
#endif
