#!/usr/bin/env python3
"""Reproduce physically verified N81 touch ROM/firmware diagnostics on current RAM Android.
Default --check only reads hardware. --firmware resets touch and uploads verified
N81 firmware into controller RAM, then restores saved SPI/reset/CS state.
No input registration, reference calibration, controller execution or storage operations.
"""
import argparse,datetime,hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/'saved/research/touch-bringup';OUT=ROOT/'saved/build/T4_TOUCH_DIAG_01'
ADB=ROOT/'tools/adb-host-adb01/adb';CROSS=ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-gcc'
FW=HERE/'apple-inputs/n81-firmware/zephyr2.bin'
FW_SHA='3c7a25bb9dd2580f4c0ce8eae472338e2b150d3ce9a0d519a01ed196af8242ab'
ENV=dict(os.environ,ADB_LIBUSB='1');SERIAL='T4RAMADB01'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(argv,timeout=30):
 r=subprocess.run(list(map(str,argv)),cwd=ROOT,env=ENV,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
 if r.returncode:raise RuntimeError(r.stdout.decode(errors='replace'))
 return r.stdout.decode(errors='replace').replace('\r\n','\n')
def adb(*args,timeout=30):return run([ADB,'-s',SERIAL,*args],timeout)
def main():
 p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group();g.add_argument('--check',action='store_true');g.add_argument('--firmware',action='store_true');p.add_argument('--build-only',action='store_true');a=p.parse_args()
 OUT.mkdir(exist_ok=True)
 protected=[ROOT/'saved/build/T4_ANDROID_ADB_01'/n for n in ['manifest.json','zImage','handoff.bin','initramfs.cpio.gz']]
 protected +=[ROOT/'saved/build/phase1-published'/n for n in ['openiboot.bin','openiboot-native.bin']]
 before={str(f.relative_to(ROOT)):sha(f) for f in protected}
 name='t4-touch-diag-fw' if a.firmware else 't4-touch-diag-read';exe=OUT/name
 args=[CROSS,'-nostdlib','-static','-fno-use-linker-plugin','-mcpu=cortex-a8','-marm','-Os','-fno-builtin','-Wl,-e,_start']
 if a.firmware:
  if not FW.is_file() or len(FW.read_bytes())!=53196 or sha(FW)!=FW_SHA:raise RuntimeError('Verified N81 firmware missing or changed; inspect apple-inputs/n81-firmware/extraction.json')
  asm=OUT/'n81-verified-fw.S';asm.write_text('.section .rodata\n.global n81_fw,n81_fw_end\nn81_fw:\n.incbin "'+str(FW)+'"\nn81_fw_end:\n.section .note.GNU-stack,"",%progbits\n')
  args +=['-DT4_RESET_PROBE','-DT4_FIRMWARE_PROBE','-DT4_RESET_HIZ','-DT4_RESET_CLOCK_HIGH','-DT4_SPI_BASE=0x4038','-DT4_RT','-DT4_FW_DIV=5',HERE/'t4-touch-raw.c',asm,'-lgcc']
 else:args +=[HERE/'t4-touch-raw.c']
 args+=['-o',exe];run(args)
 manifest={'program':str(exe),'sha256':sha(exe),'firmware_sha256':FW_SHA if a.firmware else None,'source_sha256':sha(HERE/'t4-touch-raw.c'),'protected':before,'physical_scope':'SPI1 + reset204 + CS601; PMGR mapping read-only; no input registration or controller execution','build_command':list(map(str,args))}
 (OUT/(name+'.json')).write_text(json.dumps(manifest,indent=2)+'\n')
 print('Built:',exe,flush=True)
 if a.build_only:return
 check=adb('shell','id; uname -r; cat /proc/mounts; ls /sys/bus/spi/devices')
 if 'uid=0(root)' not in check or '3.0.8' not in check or not any(' /data tmpfs ' in line for line in check.splitlines()):raise RuntimeError('Requires the existing root RAM Android 3.0.8 with /data on tmpfs')
 for line in check.splitlines():
  if line.startswith('spi') and '.' in line:raise RuntimeError('A Linux SPI device is registered; refuse direct MMIO diagnostic')
 dest='/data/local/tmp/'+name
 adb('push',exe,dest);adb('shell','chmod 700 '+dest)
 output=adb('shell',dest,timeout=40)
 required=['T4_TOUCH N81_FIRMWARE_ACK_CONFIRMED','T4_TOUCH N1_CHIP_VERSION=6e3101a0','T4_TOUCH TXCOUNT_before_stop=00000000','T4_TOUCH firmware_RX_discarded=0000cfcc','T4_TOUCH original SPI/GPIO state restored'] if a.firmware else ['T4_TOUCH READ_ONLY_DONE']
 stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');log=OUT/('hardware-'+name+'-'+stamp+'.log');log.write_text(check+'\n'+output)
 print(output,flush=True)
 if not all(x in output for x in required):raise RuntimeError('Expected physical milestone markers absent: '+str(log))
 alive=adb('shell','echo T4_TOUCH_ADB_STILL_OK; cat /proc/uptime')
 if 'T4_TOUCH_ADB_STILL_OK' not in alive:raise RuntimeError('ADB shell not confirmed after test')
 print(alive,flush=True)
 after={str(f.relative_to(ROOT)):sha(f) for f in protected}
 if before!=after:raise RuntimeError('Protected baseline hashes changed')
 result={'log':str(log),'program_sha256':sha(exe),'firmware_sha256':FW_SHA if a.firmware else None,'milestone':'N81 firmware ACK and chip version confirmed; NO touch frame/input confirmation' if a.firmware else 'read-only SPI MMIO confirmed','adb_shell':True,'protected_unchanged':True}
 (OUT/('HARDWARE-'+name+'.json')).write_text(json.dumps(result,indent=2)+'\n')
 print('Log:',log);print('BASELINE_HASHES_UNCHANGED')
if __name__=='__main__':
 try:main()
 except (RuntimeError,subprocess.TimeoutExpired,OSError) as e:print('T4_TOUCH_DIAG_FAILED:',e,file=sys.stderr);sys.exit(1)
