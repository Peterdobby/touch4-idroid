#!/usr/bin/env python3
"""Read-only ADB confirmation of the native N1 input bridge. No event injection."""
from pathlib import Path
import os,subprocess,re,json,datetime
R=Path(__file__).resolve().parents[1];ADB=R/'tools/adb-host-adb01/adb';ENV=dict(os.environ,ADB_LIBUSB='1')
def shell(cmd):
 p=subprocess.run([str(ADB),'-s','T4RAMADB01','shell',cmd],env=ENV,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=20)
 if p.returncode:raise RuntimeError(p.stdout)
 return p.stdout.replace('\r\n','\n')
def main():
 text=shell('echo T4_TOUCH_ADB_OK; id; uname -r; cat /proc/bus/input/devices; echo T4_INPUT_KERNEL_LOG; dmesg | /sbin/busybox tail -n 80')
 path=R/'logs'/('touch-input-check-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.log');path.write_text(text)
 print(text);blocks=text.split('\n\n');block=next((b for b in blocks if 'Name="T4 Multitouch"' in b),'')
 m=re.search(r'Handlers=.*\b(event[0-9]+)\b',block)
 ok='T4_TOUCH_ADB_OK' in text and 'uid=0(root)' in text and m is not None
 print('Log:',path)
 if not ok:print('T4_TOUCH_INPUT_NOT_CONFIRMED');return 2
 node='/dev/input/'+m.group(1);print('T4_TOUCH_INPUT_REGISTERED:',node)
 print('Observe real finger events locally:')
 print('ADB_LIBUSB=1 '+str(ADB)+' -s T4RAMADB01 shell getevent '+node)
 print('Physical Launcher touch still requires the user to tap/swipe.');return 0
if __name__=='__main__':raise SystemExit(main())
