#!/usr/bin/env python3
"""Re-enter the owner's existing Kit SSH ramdisk from controlled OpeniBoot.
Reuses byte-pinned, already generated iBEC/ramdisk/DT/kernel files. Does not
build/trigger an exploit, patch firmware checks, update firmware or set NVRAM.
Requires an existing localhost USB SSH forward (6414 -> device port 22).
"""
import argparse,datetime,hashlib,json,os,shlex,subprocess,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'saved/build/untethered-menu-03'
REF=OUT/'ramdisk-reference';KIT=(Path(os.environ.get('T4_KIT_DIR', str(Path.home() / 'Legacy-iOS-Kit'))) / 'bin/macos')
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--from-openiboot',action='store_true',required=True)
    args=parser.parse_args()
    manifest=json.loads((REF/'MANIFEST.json').read_text())
    for name in ['iBEC.patched','iBEC','Ramdisk.dmg','DeviceTree.dec','Kernelcache.dec']:
        assert hashlib.sha256((REF/name).read_bytes()).hexdigest()==manifest[name]['sha256']
    log=OUT/'ramdisk-returns'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S');log.mkdir(parents=True)
    def run(cmd,name,timeout=30):
        p=subprocess.run([str(x) for x in cmd],capture_output=True,timeout=timeout)
        (log/(name+'.log')).write_bytes(p.stdout+p.stderr)
        if p.returncode:raise RuntimeError(name+' failed; '+p.stderr.decode(errors='replace')[-600:])
        return p.stdout
    print('RAM-only: existing controlled OpeniBoot -> unmodified Kit iBEC.',flush=True)
    run([OUT/'acm-ram','upload','0x44000000',REF/'iBEC.patched'],'upload-ibec')
    run([OUT/'acm-ram','go','0x44000000'],'enter-ibec')
    deadline=time.monotonic()+20
    while True:
        try:p=subprocess.run([str(KIT/'irecovery'),'-q'],capture_output=True,timeout=4)
        except subprocess.TimeoutExpired:p=None
        if p is not None and not p.returncode:
            assert (f'ECID: 0x{int(os.environ["T4_ECID"], 0):016x}').encode() in p.stdout.lower().replace(b'ecid:',b'ECID:')
            assert b'CPID: 0x8930' in p.stdout
            (log/'ibec-query.log').write_bytes(p.stdout);break
        if time.monotonic()>deadline:raise RuntimeError('Existing Kit iBEC Recovery did not enumerate; no persistent changes made')
        time.sleep(.5)
    sequence=[('-f','Ramdisk.dmg'),('-c','getenv ramdisk-delay'),('-c','ramdisk'),
              ('-f','DeviceTree.dec'),('-c','devicetree'),('-f','Kernelcache.dec'),('-c','bootx')]
    for i,(flag,value) in enumerate(sequence):
        print('Kit RAM step:',value,flush=True)
        run([KIT/'irecovery',flag,REF/value if flag=='-f' else value],'step-'+str(i),45)
    cp=tempfile.mkdtemp(prefix='t4-menu03-rd-',dir='/tmp')+'/master'
    ssh=['ssh','-T','-o','ControlMaster=auto','-o','ControlPersist=600','-o','ControlPath='+cp,
         '-o','HostKeyAlgorithms=+ssh-rsa','-o','StrictHostKeyChecking=accept-new',
         '-o','UserKnownHostsFile='+str(OUT/'return-rd-known-hosts'),'-o','ConnectTimeout=3','-p','6414','root@127.0.0.1']
    deadline=time.monotonic()+45
    while True:
        try:p=subprocess.run([str(KIT/'sshpass'),'-e',*ssh,'/sbin/mount'],env=dict(os.environ,SSHPASS=os.environ.get('T4_SSH_PASSWORD', '')),capture_output=True,timeout=7)
        except subprocess.TimeoutExpired:p=None
        if p is not None and not p.returncode:
            assert b'/dev/md0 on / ' in p.stdout,'Refuse to mount/update a normal installed OS'
            mounts=p.stdout;break
        if time.monotonic()>deadline:raise RuntimeError('SSH ramdisk not online; check existing iproxy 6414:22. No firmware update issued.')
        time.sleep(1)
    base=['ssh','-T','-o','ControlPath='+cp,'-o','BatchMode=yes','-p','6414','root@127.0.0.1']
    for part in [1,2]:
        if (' on /mnt'+str(part)+' ').encode() not in mounts:
            run(base+['/sbin/mount_hfs -o ro /dev/disk0s1s'+str(part)+' /mnt'+str(part)],'mount-'+str(part))
    machine=run(base+['/mnt1/usr/sbin/sysctl -n hw.machine'],'machine');assert machine.strip()==b'iPod4,1'
    run(base+['/usr/sbin/nvram -p'],'nvram-read-only')
    (OUT/'.ssh-control-path').write_text(cp+'\n')
    (log/'RESULT.json').write_text(json.dumps(dict(status='EXISTING_KIT_RAMDISK_REENTERED',mounts_read_only=True,
        firmware_writes=False,new_exploit_code=False,new_signature_patches=False),indent=2)+'\n')
    print('Existing Kit SSH ramdisk online; /mnt1 and /mnt2 mounted read-only. Log:',log,flush=True)
if __name__=='__main__':main()
