"""Reproducible RAM-only Android framework CPIO from pinned androidi4 files."""
import gzip,hashlib,json,struct,sys,tarfile
from pathlib import Path

def sha(b):return hashlib.sha256(b).hexdigest()
def entry(name,data=b'',mode=0o100644,rdev=(0,0),ino=1,uid=0,gid=0,mtime=0):
    n=name.encode()+b'\0';fields=[ino,mode,uid,gid,1,mtime,len(data),0,0,*rdev,len(n),0]
    b=b'070701'+b''.join(f'{v:08x}'.encode() for v in fields)+n
    b+=bytes((-len(b))%4);b+=data;b+=bytes((-len(b))%4);return b

def prepare(root,here,out,cross):
    sys.path.insert(0,str(root));from prepare_android import unpack_cpio
    previous=root/'saved/build/T4_ANDROID_INIT_04';m=json.loads((previous/'manifest.json').read_text())
    records,files=unpack_cpio(gzip.decompress((previous/'initramfs.cpio.gz').read_bytes()))
    assert sha((previous/'initramfs.cpio.gz').read_bytes())==m['files']['initramfs.cpio.gz']['sha256']
    items={e['path']:[files[e['path']],e['mode'],(e['rdev_major'],e['rdev_minor']),e['uid'],e['gid'],e['mtime']] for e in records}
    items.pop('sbin/t4-probe')
    items['init.rc']=[(here/'init.rc').read_bytes(),0o100644,(0,0),0,0]
    items['sbin/t4-dynamic-probe.sh']=[(here/'t4-dynamic-probe.sh').read_bytes(),0o100755,(0,0),0,0]
    items['sbin/t4-ui-watch.sh']=[(here/'t4-ui-watch.sh').read_bytes(),0o100755,(0,0),0,0]
    rules=(root/'saved/build/android-prepared/ramdisk-text/ueventd.rc').read_bytes()+b'\n/dev/kmsg 0600 root root\n'
    items['ueventd.rc']=[rules,0o100644,(0,0),0,0]
    items['default.prop']=[b'ro.secure=1\nro.debuggable=1\nro.kernel.qemu=0\nro.sf.lcd_density=240\ndalvik.vm.heapsize=24m\ndalvik.vm.execution-mode=int:fast\nro.setupwizard.mode=DISABLED\n',0o100644,(0,0),0,0]
    tarpath=root/'saved/build/android-prepared/system-preserved.tar'
    # Pin the local preserved source against the original YAFFS-derived manifest.
    meta=json.loads((root/'saved/build/android-prepared/system-files.json').read_text())
    expected={'system'+('/'+e['path'] if e['path'] else ''):e for e in meta}
    system_count=0;system_bytes=0;elfs={}
    with tarfile.open(tarpath) as tar:
        for member in tar:
            name=member.name
            assert name in expected and not name.startswith('/') and '..' not in Path(name).parts
            e=expected[name]
            assert member.uid==e['uid'] and member.gid==e['gid'] and member.mode==(e['mode']&0o7777)
            if member.isdir():data=b'';mode=0o40000|member.mode
            elif member.issym():
                assert member.linkname==e['target'];data=member.linkname.encode();mode=0o120000|member.mode
            else:
                assert member.isfile();data=tar.extractfile(member).read();mode=0o100000|member.mode
                assert len(data)==e['size'];system_bytes+=len(data)
                # The audited original extraction is a read-only source, never execute it on host.
                assert data==(root/'saved/build/android-prepared/system-root'/e['path']).read_bytes()
                if data[:4]==b'\x7fELF':elfs[name]=data
            items[name]=[data,mode,(0,0),member.uid,member.gid,int(member.mtime)];system_count+=1
    assert system_count==len(expected)
    assert sha(items['android-init'][0])=='d67ec53adf54cbdb9e38c6cce4d324f5f1c4908abd4630169c438134057c520f'
    # Emulator GPU modules remain as inert files; select only software EGL.
    overrides={'system/lib/egl/egl.cfg':b'0 0 android\n',
        'system/etc/vold.fstab':b'# T4 RAM-only: deliberately no dev_mount volumes.\n',
        'system/etc/vold.conf':b'# T4 RAM-only: no persistent devices.\n'}
    buildprop=items['system/build.prop'][0].decode()
    settings={'ro.kernel.android.checkjni':'0','ro.setupwizard.mode':'DISABLED','ro.sf.lcd_density':'240','dalvik.vm.heapsize':'24m','dalvik.vm.execution-mode':'int:fast','debug.sf.hw':'0','debug.egl.hw':'0','debug.sf.nobootanimation':'1'}
    lines=[l for l in buildprop.splitlines() if l.split('=',1)[0] not in settings]
    overrides['system/build.prop']=('\n'.join(lines)+'\n'+''.join(k+'='+v+'\n' for k,v in settings.items())).encode()
    for n,data in overrides.items():items[n]=[data,0o100644,(0,0),0,0]
    # Verify native ELF dependency closure without running any ARM binaries.
    missing=[]
    def string(data,p):return data[p:data.index(b'\0',p)].decode()
    for name,data in elfs.items():
        assert data[4:7]==b'\x01\x01\x01' and struct.unpack_from('<H',data,18)[0]==40,name
        ph=struct.unpack_from('<I',data,28)[0];size,count=struct.unpack_from('<HH',data,42)
        segments=[struct.unpack_from('<8I',data,ph+i*size) for i in range(count)]
        for seg in segments:
            if seg[0]==3:assert string(data,seg[1]).lstrip('/') in items,(name,'interpreter')
        dyn=[seg for seg in segments if seg[0]==2]
        if not dyn:continue
        tags=[]
        for off in range(dyn[0][1],dyn[0][1]+dyn[0][4],8):
            tag,val=struct.unpack_from('<II',data,off)
            if tag==0:break
            tags.append((tag,val))
        strva=next((v for t,v in tags if t==5),None)
        if strva is None:continue
        maps=[seg for seg in segments if seg[0]==1 and seg[2]<=strva<seg[2]+seg[4]]
        assert len(maps)==1
        st=maps[0][1]+strva-maps[0][2]
        for tag,v in tags:
            if tag==1:
                lib=string(data,st+v)
                if 'system/lib/'+lib not in items:missing.append((name,lib))
    # Report all libraries; assert closure for the actual framework executables.
    critical=['system/bin/'+n for n in ['servicemanager','app_process','surfaceflinger','mediaserver','installd','vold','netd','logcat','debuggerd','keystore']]
    assert all(n in elfs for n in critical)
    assert not [v for v in missing if v[0] in critical],missing
    payload=b''.join(entry(n,*items[n][:3],ino=i+1,uid=items[n][3],gid=items[n][4],mtime=items[n][5] if len(items[n])>5 else 0) for i,n in enumerate(sorted(items,key=lambda n:(n.count('/'),n))))
    payload+=entry('TRAILER!!!',ino=len(items)+1)
    compressed=gzip.compress(payload,compresslevel=9,mtime=0)
    assert len(compressed)<0x03800000, 'exceeds the isolated 72–128 MiB RAM slot'
    (out/'initramfs.cpio.gz').write_bytes(compressed)
    entries,actual=unpack_cpio(payload)
    assert len(actual)==len(items) and all(actual[n]==items[n][0] for n in actual)
    assert all(e['mode']&0o170000!=0o60000 for e in entries)
    assert not any(n.startswith('dev/block') for n in actual)
    for n in ['init','android-init']: (out/n).write_bytes(items[n][0])
    (out/'init.rc').write_bytes(items['init.rc'][0])
    (out/'android-input.json').write_text(json.dumps({'source_archive':'~/Downloads/androidi4.zip','system_original_entries':system_count,'system_original_file_bytes':system_bytes,'system_tar_sha256':sha(tarpath.read_bytes()),'android_init_sha256':sha(items['android-init'][0]),'cpio_unpacked_bytes':len(payload),'cpio_compressed_bytes':len(compressed),'cpio_files':len(items),'system_overrides':list(overrides),'elf_files_checked':len(elfs),'all_missing_sonames':missing,'device_block_entries':0,'physical_storage_mounts':0,'system_mtimes_preserved':True,'odex_vm_build':23,'hardware_desktop':'pending actual screen verification'},indent=2)+'\n')
    print('RAM_ANDROID_SYSTEM_PREPARED',len(compressed),'compressed;',len(payload),'unpacked')
