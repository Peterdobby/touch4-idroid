#!/usr/bin/env python3
"""Validate full Android RAM layout, original file integrity and ODEX closure."""
from pathlib import Path
import gzip,hashlib,json,struct,subprocess,sys
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'saved/build/T4_ANDROID_UI_02'
sys.path.insert(0,str(ROOT));from prepare_android import unpack_cpio
m=json.loads((OUT/'manifest.json').read_text());compressed=(OUT/'initramfs.cpio.gz').read_bytes()
records,files=unpack_cpio(gzip.decompress(compressed));rs={r['path']:r for r in records}
assert hashlib.sha256(files['android-init']).hexdigest()=='d67ec53adf54cbdb9e38c6cce4d324f5f1c4908abd4630169c438134057c520f'
assert files['system/lib/egl/egl.cfg']==b'0 0 android\n'
assert 'system/app/Launcher2.apk' in files and 'system/app/Launcher2.odex' in files
assert all(e['mode']&0o170000!=0o60000 for e in records)
assert not any(n.startswith('dev/block') for n in files)
assert 'dev/.coldboot_done' not in files
# No original disk mounting script is run. The only mounts are RAM/pseudo fs.
for line in files['init.rc'].decode().splitlines():
 tokens=line.strip().split()
 if tokens and tokens[0]=='mount':assert tokens[1] in ['tmpfs','cgroup'],line
for n in ['system/etc/vold.fstab','system/etc/vold.conf']:
 assert not [l for l in files[n].decode().splitlines() if l.strip() and not l.lstrip().startswith('#')]
for n in ['initDroid.sh','sbin/t4-ui-watch.sh']:
 assert '/dev/block' not in files[n].decode() and 'nand' not in files[n].decode().lower()
# All original system files/symlinks/modes/owners preserved except four explicit overlays.
meta=json.loads((ROOT/'saved/build/android-prepared/system-files.json').read_text());overrides=set(json.loads((OUT/'android-input.json').read_text())['system_overrides'])
for e in meta:
 n='system'+('/'+e['path'] if e['path'] else '')
 if n in overrides:continue
 rec=rs[n];assert (rec['mode'],rec['uid'],rec['gid'],rec['mtime'])==(e['mode'],e['uid'],e['gid'],e['mtime']),n
 if e['kind']==1:assert files[n]==(ROOT/'saved/build/android-prepared/system-root'/e['path']).read_bytes(),n
 elif e['kind']==2:assert files[n]==e['target'].encode(),n
# The actual ODEX dependency path/order/signatures match the configured bootclasspath.
boot=['system/framework/'+n+'.odex' for n in ['core','bouncycastle','ext','framework','android.policy','services','core-junit']]
count=0
for n,d in files.items():
 if not n.endswith('.odex'):continue
 assert d[:8]==b'dey\n036\0'
 header=struct.unpack_from('<8I',d,8);pos=header[2];_,_,build,num=struct.unpack_from('<4I',d,pos);pos+=16
 assert build==23
 expected=boot[:boot.index(n)] if n in boot else boot
 deps=[]
 for i in range(num):
  length=struct.unpack_from('<I',d,pos)[0];pos+=4;name=d[pos:pos+length].rstrip(b'\0').decode().lstrip('/');pos+=length
  sig=d[pos:pos+20];pos+=20;target=files[name];dexoff=struct.unpack_from('<I',target,8)[0]
  assert target[dexoff+12:dexoff+32]==sig,(n,name)
  deps.append(name);count+=1
 assert deps==expected,(n,deps,expected)
 assert pos==header[2]+header[3]
layout=m['ram_layout'];start=layout['initrd_upload'];end=start+len(compressed)
assert start==0x44800000 and end<0x48000000 # OpeniBoot's actual heap starts 0x48000000
assert layout['initrd_physical']==start-0x40000000
intervals=[(0x42000000,0x42000000+m['files']['zImage']['bytes']),(0x43f00000,0x43f01000),(0x44000000,0x44010000),(start,end),(0x48000000,0x50000000)]
for i,(a,b) in enumerate(intervals):
 for c,d in intervals[i+1:]:assert b<=c or d<=a,(hex(a),hex(c))
for p,d in m['protected_baselines'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==d,p
result={'RAM_interval_disjoint':True,'compressed_initrd_bytes':len(compressed),'cpio_entries':len(records),'odex_dependencies_verified':count,'original_system_metadata_preserved':True,'physical_storage_mounts_configured':0,'software_EGL_only':True,'hardware_desktop':'pending'}
(OUT/'package-test.json').write_text(json.dumps(result,indent=2)+'\n')
print('FULL_RAM_PACKAGE_PASSED:',len(records),'entries;',count,'ODEX deps; original init/metadata; no physical volume config; RAM ranges disjoint')
