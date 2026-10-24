#!/usr/bin/env python3
"""Apply the complete pinned N81 boot image set; never modifies OS/data/GPT/NVRAM.
Requires the owner's already-running SSH ramdisk on localhost:6414.
This performs persistent boot-firmware writes and is not a RAM-only test.
"""
import argparse,datetime,hashlib,json,os,shlex,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'saved/build/untethered-oib-02'
KIT=Path(os.environ.get('T4_KIT_DIR', str(Path.home() / 'Legacy-iOS-Kit')))
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',required=True)
    parser.add_argument('--port',type=int,default=6414)
    a=parser.parse_args()
    if not 1<=a.port<=65535:parser.error('Invalid port')
    if (OUT/'APPLY-ATTEMPT.json').exists():raise SystemExit('An attempt already exists; inspect its outcome before another persistent write.')
    meta=json.loads((OUT/'BUILD-SET.json').read_text())
    package=(OUT/'boot-set.pack').read_bytes();helper=(OUT/'io-probe/apply-set').read_bytes()
    assert sha(package)==meta['package_sha256'] and sha(helper)==meta['helper_sha256']
    assert json.loads((OUT/'OFFLINE-TESTS.json').read_text())['results'][0]['pass_test']
    control=tempfile.mkdtemp(prefix='t4-fullset-',dir='/tmp')+'/master'
    options=['-T','-o','HostKeyAlgorithms=+ssh-rsa','-o','UserKnownHostsFile='+str(ROOT/'saved/build/drv6-stage2-candidate/ramdisk-known-hosts'),'-o','StrictHostKeyChecking=accept-new','-o','ConnectTimeout=5','-o','ControlPath='+control,'-p',str(a.port),'root@127.0.0.1']
    connect=subprocess.run([str(KIT/'bin/macos/sshpass'),'-e','ssh','-o','ControlMaster=yes','-o','ControlPersist=600']+options+['/mnt1/usr/sbin/sysctl -n hw.machine'],env=dict(os.environ,SSHPASS=os.environ.get('T4_SSH_PASSWORD', '')),capture_output=True,timeout=15)
    if connect.returncode or connect.stdout.strip()!=b'iPod4,1':raise SystemExit('Did not confirm N81 ramdisk: '+connect.stderr.decode(errors='replace'))
    base=['ssh','-o','BatchMode=yes']+options
    def remote(command,data=None,timeout=30):
        return subprocess.run(base+[command],input=data,capture_output=True,timeout=timeout)
    mounted=remote('/sbin/mount')
    assert mounted.returncode==0 and b'/dev/md0 on / ' in mounted.stdout
    nvram=remote('/usr/sbin/nvram -p')
    assert nvram.returncode==0 and b'boot-partition\t2' in nvram.stdout
    assert b'boot-ramdisk\t/a/b/c/d/e/f/g/h/i/j/k/l/m/n/o/p/q/r/s/t/u/v/w/x/y/z/0/1/2/3/4/5/6/7/8/9/A/B/C/disk.dmg' in nvram.stdout
    # Read the already verified DRA partition; do not recreate or patch it.
    dra=remote('/bin/dd if=/dev/rdisk0s1s3 bs=16384 count=32')
    assert dra.returncode==0 and len(dra.stdout)==524288
    assert sha(dra.stdout)=='b1c9582c1b9862d60fb37ed73b0b55614b75c52e9d7e4480027b1565fbb0fd9e'
    log=OUT/'logs'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S');log.mkdir(parents=True)
    (log/'nvram-before.txt').write_bytes(nvram.stdout);(log/'existing-dra.bin').write_bytes(dra.stdout)
    r=remote('/bin/mkdir -p /var/tmp/t4-oib02')
    assert r.returncode==0
    for name,contents in [('apply-set',helper),('boot-set.pack',package)]:
        dest='/var/tmp/t4-oib02/'+name
        r=remote('/bin/cat > '+shlex.quote(dest),contents);assert r.returncode==0
        r=remote('/bin/cat '+shlex.quote(dest));assert r.returncode==0 and r.stdout==contents
    r=remote('/bin/chmod 700 /var/tmp/t4-oib02/apply-set');assert r.returncode==0
    record=dict(started=datetime.datetime.now().isoformat(),authorization='Owner requested untethered OpeniBoot, authorized direct testing, and explicitly cancelled iOS recovery.',package_sha256=sha(package),helper_sha256=sha(helper),scope='Complete boot firmware image group via Apple API; LLB then six images; persistent',system_data_partition_nvram_writes=False,exploit_changes=False,log=str(log),cold_boot_confirmed=False)
    audit=OUT/'APPLY-ATTEMPT.json';audit.write_text(json.dumps(record,indent=2)+'\n')
    print('Applying complete signed-LLB/iBoot6/OpeniBoot image set. Log:',log,flush=True)
    try:r=remote('/var/tmp/t4-oib02/apply-set --apply /var/tmp/t4-oib02/boot-set.pack',timeout=60)
    except subprocess.TimeoutExpired:
        record.update(outcome='TIMEOUT_DO_NOT_RETRY_OR_REBOOT');audit.write_text(json.dumps(record,indent=2)+'\n');raise
    (log/'apply.stdout').write_bytes(r.stdout);(log/'apply.stderr').write_bytes(r.stderr)
    record.update(exit=r.returncode,stdout=r.stdout.decode(errors='replace'),stderr=r.stderr.decode(errors='replace'),api_accepted=r.returncode==0 and b'COMPLETE_IMAGE_SET_API_ACCEPTED' in r.stdout)
    audit.write_text(json.dumps(record,indent=2)+'\n');print(record['stdout']);print(record['stderr'])
    after=remote('/usr/sbin/nvram -p');(log/'nvram-after.txt').write_bytes(after.stdout)
    record['nvram_unchanged']=after.returncode==0 and after.stdout==nvram.stdout
    audit.write_text(json.dumps(record,indent=2)+'\n')
    if not record['api_accepted']:raise SystemExit('Image-set submission incomplete. Keep ramdisk; no reboot issued.')
    print('Complete set accepted. No reboot issued; USB/cold boot still require a real test.')
if __name__=='__main__':main()
