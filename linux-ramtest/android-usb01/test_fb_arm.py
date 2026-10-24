#!/usr/bin/env python3
"""Execute actual framebuffer driver ARM code. Mock scheduling/cache flush only.
The display is ordinary emulator RAM; any unmapped MMIO access fails the test.
"""
from pathlib import Path
import json,struct,subprocess,shlex
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'saved/build/T4_ANDROID_USB_01'
SOURCE=ROOT/'saved/sources/iDroid-kernel-T4_ANDROID_USB_01';CROSS=str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-')
fields={'info_size':'sizeof(struct fb_info)','var':'offsetof(struct fb_info,var)','fix':'offsetof(struct fb_info,fix)',
 'bpp':'offsetof(struct fb_info,var.bits_per_pixel)','smem_start':'offsetof(struct fb_info,fix.smem_start)',
 'smem_len':'offsetof(struct fb_info,fix.smem_len)','line_length':'offsetof(struct fb_info,fix.line_length)',
 'screen_size':'offsetof(struct fb_info,screen_size)','var_size':'sizeof(struct fb_var_screeninfo)',
 'vma_size':'sizeof(struct vm_area_struct)','vm_start':'offsetof(struct vm_area_struct,vm_start)',
 'vm_end':'offsetof(struct vm_area_struct,vm_end)','vm_pgoff':'offsetof(struct vm_area_struct,vm_pgoff)',
 'vm_flags':'offsetof(struct vm_area_struct,vm_flags)','vm_page_prot':'offsetof(struct vm_area_struct,vm_page_prot)'}
source='#include <linux/fb.h>\n#include <linux/mm.h>\nconst unsigned offsets[]={'+','.join(fields.values())+'};\n'
(OUT/'fb-offsets.c').write_text(source)
cmd=(SOURCE/'arch/arm/mach-s5l8930/.t4-android-fb.o.cmd').read_text().splitlines()[0].split(' := ',1)[1]
flags=shlex.split(cmd);flags=flags[:flags.index('-c')];flags=[x for x in flags if not x.startswith(('-Wp,','-DKBUILD'))]
subprocess.run(flags+['-c',str(OUT/'fb-offsets.c'),'-o',str(OUT/'fb-offsets.o')],cwd=SOURCE,check=True,stdout=subprocess.DEVNULL)
subprocess.run([CROSS+'objcopy','-O','binary','-j','.rodata',str(OUT/'fb-offsets.o'),str(OUT/'fb-offsets.bin')],check=True)
vals=struct.unpack('<'+'I'*len(fields),(OUT/'fb-offsets.bin').read_bytes());off=dict(zip(fields,vals))
nm=subprocess.check_output([CROSS+'nm',str(OUT/'vmlinux')],text=True);entries=[l.split() for l in nm.splitlines() if len(l.split())==3]
ks={s[2]:int(s[0],16) for s in entries}
for n in ['t4_info','shadow','display','claimed','users']:assert sum(s[2]==n for s in entries)==1,n
uc=Uc(UC_ARCH_ARM,UC_MODE_ARM);uc.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A8)
STOP=0x01000000;FLUSH=STOP+0x100;SHADOW=0xc4000000;LCD=0xc5000100;OBJ=0xc6000000;VMA=OBJ+0x2000
for a,size in [(0xc0000000,0x1000000),(SHADOW,0x400000),(0xc5000000,0x400000),(OBJ,0x10000),(STOP,0x1000)]:uc.mem_map(a,size)
uc.mem_write(0xc0008000,(OUT/'Image.expected').read_bytes())
def put(a,v):uc.mem_write(a,struct.pack('<I',v&0xffffffff))
def get(a):return struct.unpack('<I',uc.mem_read(a,4))[0]
for n,v in [('t4_info',OBJ),('shadow',SHADOW),('display',LCD),('users',0),('claimed',0),('android_owns_display',0)]:put(ks[n],v)
# Native driver uses the CPU cache callback at cpu_cache+24 (verified in emitted ARM).
put(ks['cpu_cache']+24,FLUSH)
records=[]
def hook(uc,pc,size,user):
 if pc in [ks['mutex_lock'],ks['mutex_unlock'],ks['printk'],ks['schedule_delayed_work'],ks['remap_pfn_range'],ks['t4_input_hud'],FLUSH]:
  args=[uc.reg_read(r) for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]]
  records.append((pc,args));uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
uc.hook_add(UC_HOOK_CODE,hook)
def call(name,args):
 records.clear();uc.reg_write(UC_ARM_REG_CPSR,0xd3);uc.reg_write(UC_ARM_REG_SP,0xc0fff000);uc.reg_write(UC_ARM_REG_LR,STOP)
 for r,v in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3],args):uc.reg_write(r,v&0xffffffff)
 uc.emu_start(ks[name],STOP,count=20000000)
 assert uc.reg_read(UC_ARM_REG_PC)==STOP,name
 assert uc.reg_read(UC_ARM_REG_SP)==0xc0fff000,name
 return uc.reg_read(UC_ARM_REG_R0)
def mode(bits,yvirt=960):
 uc.mem_write(OBJ,bytes(off['info_size']))
 uc.mem_write(OBJ+off['var'],struct.pack('<7I',640,960,640,yvirt,0,0,bits))
 return call('t4_check',[OBJ+off['var'],OBJ])
assert mode(32,1920)==0xffffffea,'double buffer unsupported; gralloc must fall back to one'
assert mode(24)==0xffffffea
assert mode(32)==0;call('t4_set_par',[OBJ])
assert get(OBJ+off['line_length'])==2560 and get(OBJ+off['smem_len'])==2457600
assert call('t4_open',[OBJ,1])==0 and get(ks['users'])==1
# No fake image or console suppression for an untouched/black initial buffer.
uc.mem_write(SHADOW,bytes(2457600));uc.mem_write(LCD-32,b'\x93'*(2457600+64));call('t4_scan',[0])
assert get(ks['claimed'])==0 and get(ks['android_owns_display'])==0
assert bytes(uc.mem_read(LCD-32,2457600+64))==b'\x93'*(2457600+64)
# Real RGBX pixels from userspace are copied/converted across the whole frame.
uc.mem_write(SHADOW,struct.pack('<I',0x00a06020)*614400);call('t4_scan',[0])
assert get(ks['claimed'])==1 and get(ks['android_owns_display'])==1
assert bytes(uc.mem_read(LCD,2457600))==struct.pack('<I',0x002060a0)*614400
assert bytes(uc.mem_read(LCD-32,32))==b'\x93'*32 and bytes(uc.mem_read(LCD+2457600,32))==b'\x93'*32
assert any(pc==FLUSH and a[:2]==[LCD,2457600] for pc,a in records)
assert call('t4_release',[OBJ,1])==0 and get(ks['users'])==0 and get(ks['android_owns_display'])==0
# Verify 16-bit fallback mode too, using RGB565 source pixels.
assert mode(16)==0;call('t4_set_par',[OBJ]);assert get(OBJ+off['line_length'])==1280
call('t4_open',[OBJ,1]);uc.mem_write(SHADOW,struct.pack('<H',0xf800)*614400);call('t4_scan',[0])
assert bytes(uc.mem_read(LCD,2457600))==struct.pack('<I',0x00f80000)*614400
call('t4_release',[OBJ,1])
# Native mmap never maps the unaligned physical LCD or arbitrary extra pages.
assert mode(32)==0;call('t4_set_par',[OBJ])
for pgoff,size,ok in [(0,2457600,True),(1,4096,True),(600,4096,False),(599,8192,False)]:
 uc.mem_write(VMA,bytes(off['vma_size']));put(VMA+off['vm_start'],0x10000000);put(VMA+off['vm_end'],0x10000000+size);put(VMA+off['vm_pgoff'],pgoff)
 ret=call('t4_mmap',[OBJ,VMA]);calls=[a for pc,a in records if pc==ks['remap_pfn_range']]
 if ok:assert ret==0 and len(calls)==1 and calls[0][:4]==[VMA,0x10000000,0x4000+pgoff,size]
 else:assert ret==0xffffffea and not calls
result={'actual_driver_ARM':'passed','RGBX8888_entire_frame_and_guards':True,'RGB565_fallback':True,'no_image_fabricated':True,'unwritten_buffer_keeps_console':True,'close_restores_console':True,'mmap_boundaries':True,'MMIO_accesses':0,'scheduling_and_cache_callback':'mocked','HUD':'mocked here; tested separately against native ARM','hardware':'pending'}
(OUT/'fb-arm-test.json').write_text(json.dumps(result,indent=2)+'\n');print('FB_ARM_PASSED: actual native mode/mmap/scanout code; RGBX+565 full-frame guards; ownership; no MMIO')
