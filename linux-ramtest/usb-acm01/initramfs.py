"""Minimal static PID1 with RAM character nodes; no Android payload."""
import gzip,subprocess

def entry(name,data=b'',mode=0o100644,rdev=(0,0),ino=1):
    n=name.encode()+b'\0';fields=[ino,mode,0,0,1,0,len(data),0,0,*rdev,len(n),0]
    b=b'070701'+b''.join(f'{v:08x}'.encode() for v in fields)+n
    b+=bytes((-len(b))%4);b+=data;b+=bytes((-len(b))%4);return b

def prepare(root,here,out,cross):
    subprocess.run([cross+'gcc','-nostdlib','-static','-fno-use-linker-plugin','-fno-builtin','-fno-stack-protector','-Os','-marm','-mcpu=cortex-a8','-Wl,-e,_start',str(here/'init.c'),'-o',str(out/'init')],check=True)
    items=[('dev',b'',0o40755,(0,0)),('proc',b'',0o40555,(0,0)),('sys',b'',0o40555,(0,0)),('dev/kmsg',b'',0o20600,(1,11)),('dev/console',b'',0o20600,(5,1)),('init',(out/'init').read_bytes(),0o100755,(0,0))]
    payload=b''.join(entry(*x,ino=i+1) for i,x in enumerate(items))+entry('TRAILER!!!',ino=100)
    (out/'initramfs.cpio.gz').write_bytes(gzip.compress(payload,mtime=0))
