#!/usr/bin/env python3
"""Read-only SSH ramdisk inventory. Outputs on Mac only; no mount/flash/NVRAM writes."""
import argparse,datetime,hashlib,json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
COMMANDS={
    'identity.txt':'uname -a; sysctl hw.machine hw.model',
    'nvram.txt':'nvram -p',
    'mounts.txt':'mount',
    'devices.txt':'ls -l /dev',
    'tools.txt':'for t in ioreg dd openssl sha256sum shasum nor nor_dump norbackup img3tool nvram; do command -v "$t"; done',
    'firmware-paths.txt':'ls -la /Firmware /mnt1/Firmware /mnt1/usr/standalone/firmware /mnt1/boot /mnt2/boot /boot /usr/standalone/firmware',
    'binaries.txt':'ls -l /bin /sbin /usr/bin /usr/sbin /usr/local/bin /usr/local/sbin',
    'device-tree.txt':'ioreg -p IODeviceTree -lw0',
}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port',type=int,default=2222)
    a=p.parse_args()
    if not 1<=a.port<=65535:p.error('Invalid SSH port')
    out=ROOT/'saved/build/drv6-stage2-candidate/backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    out.mkdir(parents=True,exist_ok=False)
    known=out/'known_hosts'
    with tempfile.TemporaryDirectory(prefix='t4-ramdisk-') as temp:
        base=['ssh','-T','-o','HostKeyAlgorithms=+ssh-rsa','-o','PubkeyAcceptedAlgorithms=+ssh-rsa',
              '-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(known),
              '-o','ConnectTimeout=10','-o','ControlMaster=auto','-o','ControlPersist=60',
              '-o','ControlPath='+temp+'/master','-p',str(a.port),'root@127.0.0.1']
        try:
            prefix='PATH=/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:/usr/local/sbin; export PATH; '
            identity=subprocess.run(base+[prefix+'if command -v sysctl >/dev/null 2>&1; then sysctl -n hw.machine; else uname -m; fi'],stdout=subprocess.PIPE,timeout=90)
            if identity.returncode or identity.stdout.strip()!=b'iPod4,1':
                raise SystemExit('SSH did not confirm iPod4,1; no further commands sent.')
            records={}
            for name,command in COMMANDS.items():
                with (out/name).open('wb') as stream,(out/(name+'.stderr')).open('wb') as err:
                    proc=subprocess.run(base+[prefix+command],stdout=stream,stderr=err,timeout=45)
                data=(out/name).read_bytes()
                records[name]=dict(command=command,exit=proc.returncode,size=len(data),sha256=hashlib.sha256(data).hexdigest())
                print(name,proc.returncode,len(data),flush=True)
            (out/'INVENTORY.json').write_text(json.dumps(dict(device_writes=False,filesystems_mounted_by_script=False,
                boot_images_backed_up=False,stage='inventory only; actual NOR/ibob backup still required',records=records),indent=2)+'\n')
            print('Inventory saved:',out)
        finally:
            subprocess.run(base[:-1]+['-O','exit',base[-1]],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
if __name__=='__main__':main()
