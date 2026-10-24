#!/usr/bin/env python3
"""Stage one NEW boot file on the existing system filesystem via SSH ramdisk.
Never replaces an existing file, updates firmware, changes NVRAM or reboots.
"""
import datetime,hashlib,json,shlex,struct,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'saved/build/untethered-menu-03'
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    if (OUT/'STAGED.json').exists():raise SystemExit('Already staged; inspect STAGED.json rather than overwriting.')
    m=json.loads((OUT/'ANDROID-BUNDLE.json').read_text());data=(OUT/'android.img3').read_bytes()
    assert sha(data)==m['image_sha256']
    cp=(OUT/'.ssh-control-path').read_text().strip()
    base=['ssh','-T','-o','ControlPath='+cp,'-o','BatchMode=yes','-o','ConnectTimeout=5','-p','6414','root@127.0.0.1']
    def remote(command,data=None,timeout=55):
        p=subprocess.run(base+[command],input=data,capture_output=True,timeout=timeout)
        if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
        return p.stdout
    assert remote('/mnt1/usr/sbin/sysctl -n hw.machine').strip()==b'iPod4,1'
    mounted=remote('/sbin/mount');assert b'/dev/md0 on / ' in mounted and b'/dev/disk0s1s1 on /mnt1 ' in mounted
    nvram=remote('/usr/sbin/nvram -p')
    header=remote('/bin/dd if=/dev/rdisk0s1s1 bs=8192 count=1');assert len(header)==8192
    assert header[1024:1026] in [b'H+',b'HX']
    bs,_,free=struct.unpack_from('>III',header,1024+40)
    assert bs*free>len(data)+16*1024*1024,'Insufficient system free space'
    path='/mnt1/boot/t4/android.img3';partial=path+'.partial'
    # Refuse to follow an existing directory or file at the new location.
    remote('test ! -e /mnt1/boot/t4 && test ! -L /mnt1/boot/t4 && /bin/mkdir /mnt1/boot/t4')
    record=dict(started=datetime.datetime.now().isoformat(),status='UPLOAD_PENDING',
       image_sha256=sha(data),bytes=len(data),destination=path,
       firmware_writes=False,nvram_writes=False,partition_changes=False)
    (OUT/'STAGING-ATTEMPT.json').write_text(json.dumps(record,indent=2)+'\n')
    print('Uploading NEW Android boot file; existing OS/data and boot firmware untouched.',flush=True)
    remote('/bin/cat > '+shlex.quote(partial),data)
    print('Reading back the complete file for byte comparison.',flush=True)
    received=remote('/bin/cat '+shlex.quote(partial))
    assert received==data and sha(received)==record['image_sha256']
    remote('/bin/chmod 444 '+shlex.quote(partial)+' && /bin/mv '+shlex.quote(partial)+' '+shlex.quote(path))
    assert remote('/usr/sbin/nvram -p')==nvram
    record.update(status='STAGED_BYTE_VERIFIED_NOT_BOOTED',verified=datetime.datetime.now().isoformat(),nvram_unchanged=True)
    (OUT/'STAGED.json').write_text(json.dumps(record,indent=2)+'\n')
    print('STAGED_BYTE_VERIFIED_NOT_BOOTED; no reboot issued.',flush=True)
if __name__=='__main__':main()
