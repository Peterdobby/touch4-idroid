#!/usr/bin/env python3
"""Build the verified CLOCK15 protocol as a real N1 -> uinput RAM service. No device access."""
from pathlib import Path
import argparse,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];H=ROOT/'saved/research/touch-bringup';INPUT=H/'ios-working-n1-inputs'
CROSS=ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-gcc'
EXPECTED={'zephyr2.bin':'359b6154c8aaffb22eb6e9350be7c718be0bf00fbddbac257e9d10582e62428f','MtCl.bin':'7d96476816fbbcb0a3114c96940a9b91fb1f5e733bdf2b8b67d6e7e53129d1e8'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build(out):
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 for n,d in EXPECTED.items():assert sha(INPUT/n)==d,n
 for src,dst in [('t4-touch-input01.c','t4-touch-raw.c'),('t4-n1-input01.h','t4-n1-device-cal.h'),('t4-pmu-clock15.h','t4-pmu-clock15.h'),('t4-touch-uinput.h','t4-touch-uinput.h')]:
  (out/dst).write_bytes((H/src).read_bytes())
 asm=out/'working-ios-inputs.S';asm.write_text('.section .rodata\n'+''.join('.global '+sym+','+sym+'_end\n'+sym+':\n.incbin "'+str(INPUT/n)+'"\n'+sym+'_end:\n' for n,sym in [('zephyr2.bin','n81_fw'),('MtCl.bin','n81_device_cal')])+'.section .note.GNU-stack,"",%progbits\n')
 exe=out/'t4-touch-input'
 cmd=[CROSS,'-nostdlib','-static','-fno-use-linker-plugin','-mcpu=cortex-a8','-marm','-Os','-fno-builtin','-Wl,-e,_start','-DT4_RESET_PROBE','-DT4_FIRMWARE_PROBE','-DT4_RESET_HIZ','-DT4_RESET_CLOCK_HIGH','-DT4_SPI_BASE=0x4038','-DT4_RT','-DT4_FW_DIV=5','-DT4_ACK_DIV=3','-DT4_FW_SIZE=57880','-DT4_CAL_PROBE','-DT4_DEVICE_CAL_PROBE',out/'t4-touch-raw.c',asm,'-lgcc','-o',exe]
 subprocess.run(list(map(str,cmd)),check=True)
 info={'program':str(exe),'sha256':sha(exe),'firmware':EXPECTED,'build_command':list(map(str,cmd)),
 'source_sha256':{n:sha(H/n) for n in ['t4-touch-input01.c','t4-n1-input01.h','t4-pmu-clock15.h','t4-touch-uinput.h']},
 'hardware_protocol':'CLOCK15 real finger frames confirmed 20261022-222542; uinput/Launcher integration untested',
 'mapping':'existing iDroid FingerData; pressure_major/minor>0; X=raw; Y=SensorHeight-rawY; sensor dimensions from D9; Type A',
 'storage':'only RAM firmware/calibration; no block devices; no NAND/NOR; PMU GPIO0 clock mode restored on graceful termination'}
 (out/'touch-integration.json').write_text(json.dumps(info,indent=2)+'\n');print('Built real touch bridge:',exe);return exe
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=ROOT/'saved/build/T4_ANDROID_TOUCH_01');a=p.parse_args();build(a.out.resolve())
