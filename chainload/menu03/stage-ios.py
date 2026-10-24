#!/usr/bin/env python3
"""Stage the existing Kit iOS7 DeviceTree as one NEW file, never replace OS files."""
import datetime,hashlib,json,plistlib,shlex,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'saved/build/untethered-menu-03'
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    reference=json.loads((OUT/'IOS7-REFERENCE.json').read_text())
    contents=Path(reference['devicetree_source']).read_bytes()
    assert sha(contents)==reference['devicetree_image_sha256']
    cp=(OUT/'.ssh-control-path').read_text().strip()
    base=['ssh','-T','-o','ControlPath='+cp,'-o','BatchMode=yes','-o','ConnectTimeout=5','-p','6414','root@127.0.0.1']
    def remote(cmd,data=None):
        p=subprocess.run(base+[cmd],input=data,capture_output=True,timeout=25)
        if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
        return p.stdout
    assert remote('/mnt1/usr/sbin/sysctl -n hw.machine').strip()==b'iPod4,1'
    mounts=remote('/sbin/mount');assert b'/dev/md0 on / ' in mounts and b'/dev/disk0s1s1 on /mnt1 ' in mounts
    version=plistlib.loads(remote('/bin/cat /mnt1/System/Library/CoreServices/SystemVersion.plist'))
    assert (version['ProductVersion'],version['ProductBuildVersion'])==('7.1.2','11D257')
    nvram=remote('/usr/sbin/nvram -p');assert b'boot-partition\t2' in nvram
    kernel=remote('/bin/cat /mnt1/System/Library/Caches/com.apple.kernelcaches/kernelcache')
    assert sha(kernel)=='d400e375db09e4e3433f29a1c174009c34388e89699c7f031e338acbaf1703e7','Installed kernel differs; do not assume this iOS profile'
    dest='/mnt1/boot/t4/devicetree-ios7.img3'
    if (OUT/'IOS-STAGED.json').exists():
        assert remote('/bin/cat '+shlex.quote(dest))==contents
        print('Existing staged DeviceTree still byte-exact; nothing written.');return
    remote('test -d /mnt1/boot/t4 && test ! -L /mnt1/boot/t4 && test ! -e '+shlex.quote(dest)+' && test ! -L '+shlex.quote(dest))
    temporary=dest+'.partial'
    remote('test ! -e '+shlex.quote(temporary)+' && /bin/cat > '+shlex.quote(temporary),contents)
    assert remote('/bin/cat '+shlex.quote(temporary))==contents
    remote('/bin/chmod 444 '+shlex.quote(temporary)+' && test ! -e '+shlex.quote(dest)+' && /bin/mv '+shlex.quote(temporary)+' '+shlex.quote(dest))
    assert remote('/usr/sbin/nvram -p')==nvram
    record=dict(time=datetime.datetime.now().isoformat(),status='STAGED_BYTE_VERIFIED_NOT_BOOTED',destination=dest,
       bytes=len(contents),sha256=sha(contents),installed_version=version,installed_kernel_sha256=sha(kernel),
       kernel_unchanged=True,existing_os_files_replaced=False,nvram_unchanged=True,firmware_writes=False)
    (OUT/'IOS-STAGED.json').write_text(json.dumps(record,indent=2)+'\n')
    print('New DeviceTree file staged and byte-verified. Installed iOS7 kernel and NVRAM unchanged.')
if __name__=='__main__':main()
