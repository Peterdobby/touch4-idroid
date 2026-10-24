"""Pin the hardware-proven UI07 CPIO; add navigation map and input diagnostics."""
import gzip,hashlib,json,sys,shutil
from pathlib import Path

def sha(b):return hashlib.sha256(b).hexdigest()
def entry(name,data=b'',mode=0o100644,rdev=(0,0),ino=1,uid=0,gid=0,mtime=0):
    n=name.encode()+b'\0';fields=[ino,mode,uid,gid,1,mtime,len(data),0,0,*rdev,len(n),0]
    b=b'070701'+b''.join(f'{v:08x}'.encode() for v in fields)+n
    b+=bytes((-len(b))%4);b+=data;b+=bytes((-len(b))%4);return b

def prepare(root,here,out,cross):
    sys.path.insert(0,str(root));from prepare_android import unpack_cpio
    prev=root/'saved/build/T4_ANDROID_INPUT_03';m=json.loads((prev/'manifest.json').read_text())
    compressed=(prev/'initramfs.cpio.gz').read_bytes();assert sha(compressed)==m['files']['initramfs.cpio.gz']['sha256']
    records,files=unpack_cpio(gzip.decompress(compressed))
    items={e['path']:[files[e['path']],e['mode'],(e['rdev_major'],e['rdev_minor']),e['uid'],e['gid'],e['mtime']] for e in records}
    _,original=unpack_cpio((root/'saved/build/android-prepared/ramdisk-original.cpio').read_bytes())
    adbd=original['sbin/adbd']
    assert sha(adbd)=='54de8a66a99a842ce81616e09fd0525b45515bfc1aa29d830de8a3b499756137'
    rc=files['init.rc'].decode().replace('    ifup lo\n','    ifup lo\n    start t4-usb-setup\n',1)
    rc+='\nservice t4-usb-setup /bin/sh /sbin/t4-usb-setup.sh\n    disabled\n    oneshot\n    user root\n    group root\n\nservice adbd /bin/sh /sbin/t4-adbd.sh\n    disabled\n    user root\n    group root\n'
    props=files['default.prop'].decode().replace('ro.secure=1','ro.secure=0')
    assert 'ro.secure=0' in props
    overlays={'sbin/adbd':(adbd,0o100755),'sbin/t4-adbd.sh':((here/'t4-adbd.sh').read_bytes(),0o100755),'sbin/t4-usb-setup.sh':((here/'t4-usb-setup.sh').read_bytes(),0o100755),
              'init.rc':(rc.encode(),0o100644),'default.prop':(props.encode(),0o100644)}
    for n,(d,mode) in overlays.items():items[n]=[d,mode,(0,0),0,0,0]
    assert b'/dev/input/*' in files['ueventd.rc'] and b'root       input' in files['ueventd.rc']
    payload=b''.join(entry(n,*items[n][:3],ino=i+1,uid=items[n][3],gid=items[n][4],mtime=items[n][5]) for i,n in enumerate(sorted(items,key=lambda n:(n.count('/'),n))))
    payload+=entry('TRAILER!!!',ino=len(items)+1)
    compressed=gzip.compress(payload,compresslevel=9,mtime=0);assert len(compressed)<0x03800000
    checked,actual=unpack_cpio(payload)
    assert all(actual[n]==files[n] for n in files if n not in overlays)
    assert all(e['mode']&0o170000!=0o60000 for e in checked)
    (out/'initramfs.cpio.gz').write_bytes(compressed)
    for n in ['init','android-init','init.rc']:(out/n).write_bytes(actual[n])
    for n in ['native-compat.json','libandroid_servers.so','libandroid_runtime.so','t4-ramclock','ram-clock-epoch','zygote-id-fix.bin','zygote-id-fix.elf']:
        assert sha((prev/n).read_bytes())==m['files'][n]['sha256'],n
        shutil.copy2(prev/n,out/n)
    info=json.loads((prev/'android-input.json').read_text())
    info.update(base_initramfs_variant='T4_ANDROID_INPUT_03',base_initramfs_sha256=m['files']['initramfs.cpio.gz']['sha256'],cpio_unpacked_bytes=len(payload),cpio_compressed_bytes=len(compressed),cpio_files=len(actual),root_overlays=list(overlays),hardware_desktop='UI07 confirmed; new native input kernel pending',touch='not registered; N81 firmware and power/reset implementation required')
    info['system_overrides']+=['system/usr/keylayout/t4-ram-keys.kl']
    (out/'android-input.json').write_text(json.dumps(info,indent=2)+'\n')
    print('ADB01_RAM_USERSPACE_PREPARED',len(compressed),'bytes; INPUT03 retained; original adbd plus ADB-only USB service added')
