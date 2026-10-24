#!/usr/bin/env python3
"""Independently check executable vectors, native stubs and RAM-only CPIO policy."""
import gzip,hashlib,json,struct,subprocess,sys,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'saved/build/T4_ANDROID_INIT_02'
sys.path.insert(0,str(ROOT))
from prepare_android import unpack_cpio
m=json.loads((OUT/'manifest.json').read_text())
orig=(OUT/'zImage.original').read_bytes();z=(OUT/'zImage').read_bytes();h=(OUT/'handoff.bin').read_bytes()
u32=lambda b,p:struct.unpack_from('<I',b,p)[0]
allow={p for a,b in m['zimage_modified_ranges'] for p in range(a,b)}
assert len(z)==len(orig)
assert all(a==b or p in allow for p,(a,b) in enumerate(zip(orig,z)))
assert zlib.decompress(z[m['gzip_offset']:],31)==(OUT/'Image.expected').read_bytes()
nm=subprocess.check_output([str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-nm'),str(OUT/'handoff.elf')],text=True)
s={l[2]:int(l[0],16)-0x44000000 for line in nm.splitlines() if len(l:=line.split())==3}
for n in ['header_probe','enabled_probe','decompress_probe','decompressed_probe','putstr_probe','kernel_probe']:
 p=s[n]
 assert [u32(h,p+i) for i in [0,4,8,24,28,32]]==[0xe92d5fff,0xe10f0000,0xe92d0003,0xe8bd0003,0xe128f000,0xe8bd5fff]
assert u32(h,s['enabled_probe']+36)==0xe1a0f00c
assert u32(h,s['putstr_probe']+36)==0xe12fff1e
assert u32(h,s['kernel_probe']+36)==0xe1a01007
for n,lr,dest in [('decompress_probe',0x02000164,0x02000b0c),('decompressed_probe',0x02000168,0x02000620)]:
 p=s[n];assert [u32(h,p+i) for i in [36,40,44,48]]==[0xe51fe000,0xe51ff000,lr,dest]
assert not m['kernel_runtime_patches']
for p,d in m['protected_baselines'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==d
records,files=unpack_cpio(gzip.decompress((OUT/'initramfs.cpio.gz').read_bytes()))
assert hashlib.sha256(files['android-init']).hexdigest()=='d67ec53adf54cbdb9e38c6cce4d324f5f1c4908abd4630169c438134057c520f'
assert files['sbin/ueventd']==b'/android-init'
assert files['bin/sh']==b'/sbin/busybox'
assert 'dev/.coldboot_done' not in files and not any('dev/block' in p for p in files)
assert all(x['mode']&0o170000!=0o60000 for x in records)
rc=files['init.rc'].decode();script=files['initDroid.sh'].decode()
assert 'start ueventd' in rc and 'mkdir /data/property 0700 root root' in rc
assert rc.index('on post-fs')<rc.index('on boot')
for line in rc.splitlines():
 if line.strip().startswith('mount '):assert line.strip().split()[:3]==['mount','tmpfs','tmpfs']
assert 'mount ' not in script.replace('# Sanitized replacement: only nodes in the /dev tmpfs, no block devices or mounts.','')
assert files['sbin/t4-probe']==(OUT/'t4-probe').read_bytes()
print('PACKAGE_PASSED: six zImage probes; native kernel; original Android init/ueventd; real coldboot; RAM-only mounts; unchanged baselines')
