#!/usr/bin/env python3
"""Verify the RAM ADB image with the bundled host adb; never boots or modifies storage."""
import argparse,datetime,json,subprocess,time,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
ADB=ROOT/'tools/adb-host-adb01/adb'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--wait',type=float,default=90,help='seconds to wait for this serial; default90')
    p.add_argument('--serial',default='T4RAMADB01')
    p.add_argument('--port',type=int,default=5037,help='local adb server port; default5037 matches ordinary adb')
    a=p.parse_args()
    if not ADB.is_file():p.error('Bundled adb is missing: '+str(ADB))
    if a.wait<0 or not 1024<=a.port<=65535:p.error('Invalid wait/server port')
    path=ROOT/'saved/logs'/('adb-check-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.log');path.parent.mkdir(exist_ok=True)
    with path.open('x') as log:
        def output(s):print(s,flush=True);log.write(s+'\n');log.flush()
        def run(args,timeout=12):
            cmd=[str(ADB),'-P',str(a.port)]+args
            output('$ '+' '.join(cmd))
            env=dict(os.environ)
            if sys.platform=='darwin':env['ADB_LIBUSB']='1'
            try:r=subprocess.run(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=timeout);output(r.stdout.rstrip());return r.returncode,r.stdout
            except subprocess.TimeoutExpired as e:output('ADB_COMMAND_TIMEOUT');return 124,''
        output('Expected RAM ADB device: serial='+a.serial)
        run(['version'])
        deadline=time.monotonic()+a.wait;ready=False
        while True:
            rc,data=run(['devices','-l'])
            ready=rc==0 and any(len(s:=line.split())>=2 and s[0]==a.serial and s[1]=='device' for line in data.splitlines())
            if ready:break
            if time.monotonic()>=deadline:break
            time.sleep(min(2,max(0,deadline-time.monotonic())))
        if not ready:
            output('T4_ADB_NOT_ONLINE: expected serial absent/offline; photograph U/IRQ/SET/A and last T4_ADB messages.')
            output('Log: '+str(path));return 2
        # Legacy adbd lacks modern shell exit-status protocol; require the actual
        # marker in output instead of treating the host return code alone as proof.
        rc,data=run(['-s',a.serial,'shell','echo T4_ADB_SHELL_OK; id; uname -r'],timeout=20)
        if rc or 'T4_ADB_SHELL_OK' not in data:
            output('T4_ADB_DEVICE_SEEN_BUT_SHELL_UNCONFIRMED');output('Log: '+str(path));return 3
        output('T4_ADB_SHELL_CONFIRMED')
        output('Interactive shell: '+str(ADB)+' -P '+str(a.port)+' -s '+a.serial+' shell')
        output('Log: '+str(path));return 0
if __name__=='__main__':raise SystemExit(main())
