"""Retain the exact ADB01 RAM Android; add only a native N1 -> Linux input service."""
import gzip,hashlib,json,sys,shutil,importlib.util
from pathlib import Path
def sha(b):return hashlib.sha256(b).hexdigest()
def entry(name,data=b'',mode=0o100644,rdev=(0,0),ino=1,uid=0,gid=0,mtime=0):
 n=name.encode()+b'\0';fields=[ino,mode,uid,gid,1,mtime,len(data),0,0,*rdev,len(n),0]
 b=b'070701'+b''.join(f'{v:08x}'.encode() for v in fields)+n;b+=bytes((-len(b))%4);b+=data;b+=bytes((-len(b))%4);return b
def prepare(root,here,out,cross):
 sys.path.insert(0,str(root));from prepare_android import unpack_cpio
 spec=importlib.util.spec_from_file_location('touch_build',root/'tools/build-t4-touch-input.py');builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder);exe=builder.build(out)
 prev=root/'saved/build/T4_ANDROID_ADB_01';m=json.loads((prev/'manifest.json').read_text());packed=(prev/'initramfs.cpio.gz').read_bytes();assert sha(packed)==m['files']['initramfs.cpio.gz']['sha256']
 records,files=unpack_cpio(gzip.decompress(packed));items={e['path']:[files[e['path']],e['mode'],(e['rdev_major'],e['rdev_minor']),e['uid'],e['gid'],e['mtime']] for e in records}
 rc=files['init.rc'].decode();assert rc.count('    start t4-usb-setup\n')==1
 rc=rc.replace('    start t4-usb-setup\n','    start t4-usb-setup\n    start t4-touch\n',1)
 rc+='\nservice t4-touch /bin/sh /sbin/t4-touch-start.sh\n    disabled\n    oneshot\n    user root\n    group root input\n'
 overlays={'init.rc':(rc.encode(),0o100644),'sbin/t4-touch-input':(exe.read_bytes(),0o100755),'sbin/t4-touch-start.sh':((here/'t4-touch-start.sh').read_bytes(),0o100755)}
 for n,(data,mode) in overlays.items():items[n]=[data,mode,(0,0),0,0,0]
 payload=b''.join(entry(n,*items[n][:3],ino=i+1,uid=items[n][3],gid=items[n][4],mtime=items[n][5]) for i,n in enumerate(sorted(items,key=lambda n:(n.count('/'),n))))+entry('TRAILER!!!',ino=len(items)+1)
 checked,actual=unpack_cpio(payload)
 assert all(actual[n]==files[n] for n in files if n not in overlays)
 assert not any(e['mode']&0o170000==0o60000 for e in checked)
 compressed=gzip.compress(payload,compresslevel=9,mtime=0);assert len(compressed)<0x03800000
 (out/'initramfs.cpio.gz').write_bytes(compressed)
 for n in ['init','android-init','init.rc']:(out/n).write_bytes(actual[n])
 for n in ['native-compat.json','libandroid_servers.so','libandroid_runtime.so','t4-ramclock','ram-clock-epoch','zygote-id-fix.bin','zygote-id-fix.elf']:
  assert sha((prev/n).read_bytes())==m['files'][n]['sha256'],n
  shutil.copy2(prev/n,out/n)
 info=json.loads((prev/'android-input.json').read_text());info.update(base_initramfs_variant='T4_ANDROID_ADB_01',base_initramfs_sha256=m['files']['initramfs.cpio.gz']['sha256'],root_overlays=list(overlays),touch='Native CLOCK15 N1 firmware/calibration and real MT Type A uinput service; hardware integration pending',cpio_unpacked_bytes=len(payload),cpio_compressed_bytes=len(compressed))
 (out/'android-input.json').write_text(json.dumps(info,indent=2)+'\n');print('TOUCH01 RAM overlay prepared; existing Android/ADB files retained')
