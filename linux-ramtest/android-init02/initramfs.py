"""Whitelist a RAM initramfs; reuse original Android init/ueventd and static busybox."""
import gzip
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import zipfile

def digest(b):return hashlib.sha256(b).hexdigest()
def entry(name,data=b'',mode=0o100644,rdev=(0,0),ino=1):
    n=name.encode()+b'\0'
    fields=[ino,mode,0,0,1,0,len(data),0,0,*rdev,len(n),0]
    b=b'070701'+b''.join(f'{v:08x}'.encode() for v in fields)+n
    b+=bytes((-len(b))%4);b+=data;b+=bytes((-len(b))%4)
    return b

def prepare(root,here,out,cross):
    sys.path.insert(0,str(root))
    from prepare_android import unpack_cpio
    archive=Path('~/Downloads/androidi4.zip')
    assert digest(archive.read_bytes())=='ec675ca867c340d943eac9cd0676fa8ca71427432d93d5961379c851eda88d9d'
    with zipfile.ZipFile(archive) as z:
        compressed=z.read('androidi4/ramdisk.img')
    assert digest(compressed)=='a5ef36d2feb9cb7fd515bd556037712f2b30a61f68dc94baea78663bdd6fd0c9'
    _,files=unpack_cpio(gzip.decompress(compressed))
    android=files['init']
    assert digest(android)=='d67ec53adf54cbdb9e38c6cce4d324f5f1c4908abd4630169c438134057c520f'
    assert android[:7]==b'\x7fELF\x01\x01\x01' and struct.unpack_from('<H',android,18)[0]==40
    ph=struct.unpack_from('<I',android,28)[0];size,count=struct.unpack_from('<HH',android,42)
    assert all(struct.unpack_from('<I',android,ph+i*size)[0]!=3 for i in range(count)), 'dynamic interpreter required'
    (out/'android-init').write_bytes(android)
    for name,defines in [('init',['-DANDROID_BOOTSTRAP']),('t4-probe',[])]:
        subprocess.run([cross+'gcc','-nostdlib','-static','-fno-use-linker-plugin',
            '-mcpu=cortex-a8','-marm','-Os','-fno-builtin','-Wl,--build-id=none',
            '-Wl,-e,_start',*defines,str(here/'probe.c'),'-o',str(out/name)],check=True)
    busybox=files['sbin/busybox']
    assert busybox[:4]==b'\x7fELF'
    bp=struct.unpack_from('<I',busybox,28)[0];bs,bc=struct.unpack_from('<HH',busybox,42)
    assert all(struct.unpack_from('<I',busybox,bp+i*bs)[0]!=3 for i in range(bc))
    (out/'busybox').write_bytes(busybox)
    rc=(here/'init.rc').read_bytes()
    (out/'init.rc').write_bytes(rc)
    # init will also look up a hardware rc; no such imported file is supplied.
    items=[(n,b'',0o40755,(0,0)) for n in ['dev','sbin','bin','proc','sys','system','data','cache']]
    items += [(n,b'',0o20600,dev) for n,dev in [
        ('dev/console',(5,1)),('dev/kmsg',(1,11)),('dev/null',(1,3)),
        ('dev/zero',(1,5)),('dev/random',(1,8)),('dev/urandom',(1,9))]]
    items += [(n,data,mode,(0,0)) for n,data,mode in [
        ('init',(out/'init').read_bytes(),0o100755),('android-init',android,0o100755),
        ('sbin/t4-probe',(out/'t4-probe').read_bytes(),0o100755),
        ('init.rc',rc,0o100644),
        ('sbin/busybox',busybox,0o100755),
        ('bin/sh',b'/sbin/busybox',0o120777),
        ('sbin/ueventd',b'/android-init',0o120777),
        ('initDroid.sh',(here/'initDroid.sh').read_bytes(),0o100755),
        ('ueventd.rc',(here/'ueventd.rc').read_bytes(),0o100644),('default.prop',b'ro.secure=1\nro.debuggable=0\n',0o100644)]]
    payload=b''.join(entry(n,b,m,d,i+1) for i,(n,b,m,d) in enumerate(items))
    payload+=entry('TRAILER!!!',ino=len(items)+1)
    (out/'initramfs.cpio.gz').write_bytes(gzip.compress(payload,compresslevel=9,mtime=0))
    # Reparse generated CPIO: only whitelisted files, zero block devices.
    records,actual=unpack_cpio(payload)
    assert set(actual)=={n for n,b,m,d in items}
    assert all(actual[n]==b for n,b,m,d in items)
    assert actual['android-init']==android
    assert all(e['mode']&0o170000!=0o60000 for e in records)
    (out/'android-input.json').write_text(json.dumps({
        'archive':str(archive),'android_init_sha256':digest(android),
        'original_scripts_included':False,'original_system_included':False,
        'ram_only_entries':[n for n,b,m,d in items],
        'success':'Android init rc actions and service forked by PID1; not Android desktop',
        'busybox_sha256':digest(busybox),'ueventd':'original Android init via argv[0] symlink',
        'known_kernel_limits':['Android framework services not started','ashmem/binder not enabled']},indent=2)+'\n')
