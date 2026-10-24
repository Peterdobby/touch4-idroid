"""Reproducible RAM-only Android framework CPIO from pinned androidi4 files."""
import gzip,hashlib,json,struct,sys,tarfile
from pathlib import Path

def sha(b):return hashlib.sha256(b).hexdigest()
def entry(name,data=b'',mode=0o100644,rdev=(0,0),ino=1,uid=0,gid=0,mtime=0):
    n=name.encode()+b'\0';fields=[ino,mode,uid,gid,1,mtime,len(data),0,0,*rdev,len(n),0]
    b=b'070701'+b''.join(f'{v:08x}'.encode() for v in fields)+n
    b+=bytes((-len(b))%4);b+=data;b+=bytes((-len(b))%4);return b

def prepare(root,here,out,cross):
    # Pin the full system and all existing device nodes to tested UI04.
    sys.path.insert(0,str(root));from prepare_android import unpack_cpio
    previous=root/'saved/build/T4_ANDROID_UI_04';manifest=json.loads((previous/'manifest.json').read_text())
    compressed=(previous/'initramfs.cpio.gz').read_bytes()
    assert sha(compressed)==manifest['files']['initramfs.cpio.gz']['sha256']
    records,files=unpack_cpio(gzip.decompress(compressed))
    items={e['path']:[files[e['path']],e['mode'],(e['rdev_major'],e['rdev_minor']),e['uid'],e['gid'],e['mtime']] for e in records}
    overlays=['init.rc','sbin/t4-ui-watch.sh','sbin/t4-zygote.sh','sbin/t4-critical-log.sh','sbin/t4-dynamic-probe.sh']
    for name in overlays:
        items[name]=[(here/Path(name).name).read_bytes(),0o100644 if name=='init.rc' else 0o100755,(0,0),0,0,0]
    payload=b''.join(entry(n,*items[n][:3],ino=i+1,uid=items[n][3],gid=items[n][4],mtime=items[n][5]) for i,n in enumerate(sorted(items,key=lambda n:(n.count('/'),n))))
    payload+=entry('TRAILER!!!',ino=len(items)+1)
    compressed=gzip.compress(payload,compresslevel=9,mtime=0)
    assert len(compressed)<0x03800000
    checked,actual=unpack_cpio(payload)
    assert all(actual[n]==files[n] for n in files if n not in overlays)
    assert all(actual[n]==items[n][0] for n in actual)
    assert not any(n.startswith('dev/block') for n in actual)
    assert all(e['mode']&0o170000!=0o60000 for e in checked)
    (out/'initramfs.cpio.gz').write_bytes(compressed)
    for n in ['init','android-init','init.rc']:(out/n).write_bytes(actual[n])
    info=json.loads((previous/'android-input.json').read_text())
    info.update(base_initramfs_variant='T4_ANDROID_UI_04',base_initramfs_sha256=manifest['files']['initramfs.cpio.gz']['sha256'],cpio_unpacked_bytes=len(payload),cpio_compressed_bytes=len(compressed),cpio_files=len(actual),root_overlays=overlays,hardware_desktop='pending actual screen verification')
    (out/'android-input.json').write_text(json.dumps(info,indent=2)+'\n')
    print('UI06_RAM_USERSPACE_PREPARED',len(compressed),'bytes; original system/init preserved')
