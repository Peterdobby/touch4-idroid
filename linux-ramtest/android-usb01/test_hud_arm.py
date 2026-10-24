#!/usr/bin/env python3
from pathlib import Path
import json,re,struct,subprocess
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'saved/build/T4_ANDROID_USB_01'
SOURCE=ROOT/'saved/sources/iDroid-kernel-T4_ANDROID_USB_01';CROSS=str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-')
sy={p[2]:int(p[0],16) for l in subprocess.check_output([CROSS+'nm',str(OUT/'vmlinux')],text=True).splitlines() if len(p:=l.split())==3}
u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A8)
u.mem_map(0xc0000000,0x1000000);u.mem_write(0xc0008000,(OUT/'Image.expected').read_bytes())
LCD=0xc5000100;STOP=0x1000000
u.mem_map(0xc5000000,0x400000);u.mem_map(STOP,0x1000)
values=[0x12345678,0x85,12,1,1,5,1,4]
usb=[20,123,5,3]
def hook(u,pc,size,d):
 if pc==sy['t4_keys_snapshot']:
  u.mem_write(u.reg_read(UC_ARM_REG_R0),struct.pack('<8I',*values));u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
old_hook=hook
def hook(u,pc,size,d):
 if pc==sy['t4_usb_snapshot']:
  u.mem_write(u.reg_read(UC_ARM_REG_R0),struct.pack('<4I',*usb));u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
 else:old_hook(u,pc,size,d)
u.hook_add(UC_HOOK_CODE,hook)
font=(SOURCE/'arch/arm/mach-s5l8930/include/mach/t4_ramfont.h').read_text().split('{',1)[1].split('}',1)[0]
font=bytes(map(int,re.findall(r'\d+',font)));assert len(font)==2048
for frame in [1,2]:
 u.mem_write(LCD-32,b'\x93'*(640*960*4+64));u.reg_write(UC_ARM_REG_CPSR,0xd3)
 u.reg_write(UC_ARM_REG_SP,0xc0fff000);u.reg_write(UC_ARM_REG_LR,STOP);u.reg_write(UC_ARM_REG_R0,LCD)
 u.emu_start(sy['t4_input_hud'],STOP,count=3000000);assert u.reg_read(UC_ARM_REG_PC)==STOP
 lines=[f'USB01 P={values[0]:08x} RAW={values[1]:02x} EV={values[2]:08x}',f'REG={values[3]} OPEN={values[4]} HB={values[5]:08x} NODE={values[6]}',f'PH={values[7]} F={frame:08x} TOUCH=OFF',f'U={usb[0]} IRQ={usb[1]:08x} SET={usb[2]:04x} A={usb[3]:x}']
 expected=bytearray(640*64*4)
 for row,line in enumerate(lines):
  for col,c in enumerate(line.ljust(40)[:40].encode()):
   for y in range(8):
    for x in range(8):
     color=0xffffff if font[c*8+y]&(0x80>>x) else 0
     for dy in range(2):
      for dx in range(2):struct.pack_into('<I',expected,((row*16+y*2+dy)*640+col*16+x*2+dx)*4,color)
 assert bytes(u.mem_read(LCD,len(expected)))==expected
 assert bytes(u.mem_read(LCD-32,32))==b'\x93'*32
 assert bytes(u.mem_read(LCD+len(expected),640*960*4-len(expected)+32))==b'\x93'*(640*960*4-len(expected)+32)
 values[5]+=1
result={'actual_ARM_HUD_pixels_and_font':True,'two_heartbeat_frame_values':True,'only_top_64_rows_modified':True,'display_guards_preserved':True,'MMIO_maps':0,'mock':'input snapshot only; kernel snprintf and pixel code execute','hardware':'pending'}
(OUT/'hud-arm-test.json').write_text(json.dumps(result,indent=2)+'\n');print('HUD_ARM_PASSED: native text/pixels; bounds; changing counters; no MMIO')
