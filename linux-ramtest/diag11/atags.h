/* Minimal legacy ARM ATAGs, adapted from c5cee8c actions.c. RAM only. */
#ifndef T4_ATAGS_H
#define T4_ATAGS_H
static unsigned t4_build_atags(volatile unsigned *out,unsigned capacity,
                             const char *line,unsigned rd_size,unsigned rd_unpacked)
{
    volatile unsigned *p=out;
    unsigned n=0,i,words;
    while(line[n])n++;
    words=(n+1+3)/4;
    if(capacity<22+words)return 0;
    *p++=5;*p++=0x54410001;*p++=1;*p++=4096;*p++=0;
    *p++=4;*p++=0x54410002;*p++=0x10000000;*p++=0;
    *p++=5;*p++=0x54410004;*p++=0;*p++=(rd_unpacked+1023)/1024;*p++=0;
    *p++=4;*p++=0x54420005;*p++=0x08000000;*p++=rd_size;
    *p++=words+2;*p++=0x54410009;
    for(i=0;i<words;i++)p[i]=0;
    for(i=0;i<=n;i++)((volatile unsigned char*)p)[i]=line[i];
    p+=words;*p++=0;*p++=0;
    return (unsigned)(p-out);
}
#endif
