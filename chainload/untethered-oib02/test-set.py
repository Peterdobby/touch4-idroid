#!/usr/bin/env python3
"""Host-only argument/CRC/order tests with a fake IOKit implementation."""
import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'saved/build/untethered-oib-02'
FAKE=r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
unsigned int mach_task_self_=1;
static unsigned int step;
int sysctlbyname(const char*a,void*b,unsigned long*c,void*d,unsigned long e){strcpy(b,"iPod4,1");return 0;}
const void *IOServiceMatching(const char*a){return (void*)1;}
unsigned int IOServiceGetMatchingService(unsigned int a,const void*b){puts("MOCK_SERVICE_OPENED");return 1;}
int IOServiceOpen(unsigned int a,unsigned int b,unsigned int c,unsigned int*d){*d=2;return 0;}
int IOServiceClose(unsigned int a){if(step!=8)abort();return 0;}
int IOObjectRelease(unsigned int a){return 0;}
int IOConnectCallStructMethod(unsigned int a,unsigned int sel,const void*b,unsigned long n,void*c,unsigned long*d){
 unsigned int expected=step==0?2:step==1?0:1;
 if(sel!=expected || step>=8)abort();step++;return 0;
}
'''
def main():
    work=OUT/'offline-tests';work.mkdir(exist_ok=True)
    (work/'fake.c').write_text(FAKE)
    exe=work/'apply-set-host-mock'
    subprocess.run(['clang','-Wno-deprecated-non-prototype','-I'+str(OUT/'io-probe'),str(ROOT/'chainload/untethered-oib02/apply-set.c'),str(work/'fake.c'),'-o',str(exe)],check=True,capture_output=True)
    pack=OUT/'boot-set.pack';b=pack.read_bytes()
    damaged=bytearray(b);damaged[-1]^=1
    (work/'damaged.pack').write_bytes(damaged);(work/'truncated.pack').write_bytes(b[:-1])
    cases=[('complete_order',['--apply',str(pack)],0,True),('damaged',['--apply',str(work/'damaged.pack')],8,False),('truncated',['--apply',str(work/'truncated.pack')],6,False),('missing_flag',[str(pack)],2,False)]
    results=[]
    for name,args,code,opened in cases:
        r=subprocess.run([str(exe)]+args,capture_output=True)
        assert r.returncode==code,(name,r.returncode,r.stderr)
        assert (b'MOCK_SERVICE_OPENED' in r.stdout)==opened
        results.append(dict(test=name,exit=r.returncode,pass_test=True))
    (OUT/'OFFLINE-TESTS.json').write_text(json.dumps(dict(scope='Mock IOKit; does not prove hardware boot',results=results),indent=2)+'\n')
    print('4 host-only package/order tests passed; real cold boot unconfirmed.')
if __name__=='__main__':main()
