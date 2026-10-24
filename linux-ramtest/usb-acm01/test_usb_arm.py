#!/usr/bin/env python3
"""Execute real emitted A4 PHY/FIFO/reset/pullup instructions on modeled registers."""
from pathlib import Path
import json,shlex,struct,subprocess
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'saved/build/T4_USB_ACM_01';SRC=ROOT/'saved/sources/iDroid-kernel-T4_USB_ACM_01';CROSS=str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-')
fields=['offsetof(struct s3c_hsotg,regs)','offsetof(struct s3c_hsotg,dev)','offsetof(struct s3c_hsotg,gadget)']
(OUT/'usb-offsets.c').write_text('#include "'+str(SRC/'drivers/usb/gadget/s3c-hsotg.c')+'"\nconst unsigned t4_usb_offsets[]={'+','.join(fields)+'};\n')
cmd=(SRC/'drivers/usb/gadget/.s3c-hsotg.o.cmd').read_text().splitlines()[0].split(' := ',1)[1]
flags=shlex.split(cmd);flags=flags[:flags.index('-c')];flags=[x for x in flags if not x.startswith(('-Wp,','-DKBUILD'))]
subprocess.run(flags+['-DKBUILD_MODNAME="t4usbtest"','-c',str(OUT/'usb-offsets.c'),'-o',str(OUT/'usb-offsets.o')],cwd=SRC,check=True,stdout=subprocess.DEVNULL)
nm=subprocess.check_output([CROSS+'nm','-S',str(OUT/'usb-offsets.o')],text=True);o=int(next(l.split()[0] for l in nm.splitlines() if l.split()[-1]=='t4_usb_offsets'),16)
subprocess.run([CROSS+'objcopy','-O','binary','-j','.rodata',str(OUT/'usb-offsets.o'),str(OUT/'usb-offsets.bin')],check=True)
regs,dev,gadget=struct.unpack_from('<3I',(OUT/'usb-offsets.bin').read_bytes(),o)
sy={p[2]:int(p[0],16) for l in subprocess.check_output([CROSS+'nm',str(OUT/'vmlinux')],text=True).splitlines() if len(p:=l.split())==3}
u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A8)
BASE=0xc5000000;CTRL=0xe0000000;PHY=0xfcc00000;STOP=0x1000000
u.mem_map(0xc0000000,0x1000000);u.mem_write(0xc0008000,(OUT/'Image.expected').read_bytes())
for a,size in [(BASE,0x10000),(CTRL,0x10000),(PHY,0x1000),(0xfc500000,0x10000),(STOP,0x1000)]:u.mem_map(a,size)
def put(a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
put(BASE+regs,CTRL);put(BASE+dev,0);put(BASE+8,sy['a4_hsotg_data']);put(CTRL+0x40,0x4f54280a);put(CTRL+0x4c,0x07e800e8)
state={'rate':24000000,'clkerror':False,'mode':'clear','reads':0,'stages':[],'writes':[],'delays':0}
def hook(u,pc,size,d):
 if pc==sy['clk_get']:value=0xfffffffe if state['clkerror'] else BASE+0x4000
 elif pc==sy['clk_get_rate']:value=state['rate']
 elif pc==sy['t4_usb_stage']:
  state['stages'].append(u.reg_read(UC_ARM_REG_R0));value=0
 elif pc in [sy[n] for n in ['device_create_file','device_remove_file','clk_put','__const_udelay','__udelay','dev_printk','_dev_info','printk'] if n in sy]:
  if pc in [sy[n] for n in ['__const_udelay','__udelay'] if n in sy]:state['delays']+=1
  value=0
 else:return
 u.reg_write(UC_ARM_REG_R0,value);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
def read(u,access,a,size,value,d):
 if a==CTRL+0x10:
  state['reads']+=1
  if state['mode']=='clear':put(a,0)
  elif state['mode']=='flush-stuck':put(a,0x30)
  elif state['mode']=='reset-ok':put(a,1 if state['reads']<3 else 0x80000000)
  elif state['mode']=='reset-stuck':put(a,1)
  elif state['mode']=='idle-stuck':put(a,0)
def write(u,access,a,size,value,d):state['writes'].append((a,value))
u.hook_add(UC_HOOK_CODE,hook)
u.hook_add(UC_HOOK_MEM_READ,read,begin=CTRL,end=CTRL+0xffff)
u.hook_add(UC_HOOK_MEM_WRITE,write,begin=CTRL,end=CTRL+0xffff)
u.hook_add(UC_HOOK_MEM_WRITE,write,begin=PHY,end=PHY+0xfff)
def call(name,args):
 state['writes']=[];state['reads']=0;state['delays']=0;state['stages']=[]
 u.reg_write(UC_ARM_REG_CPSR,0xd3);u.reg_write(UC_ARM_REG_SP,0xc0fff000);u.reg_write(UC_ARM_REG_LR,STOP)
 for i,r in enumerate([UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11]):u.reg_write(r,0x12340000+i)
 for r,v in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3],args):u.reg_write(r,v)
 u.emu_start(sy[name],STOP,count=3000000)
 assert u.reg_read(UC_ARM_REG_PC)==STOP,(name,hex(u.reg_read(UC_ARM_REG_PC)))
 assert u.reg_read(UC_ARM_REG_SP)==0xc0fff000
 for i,r in enumerate([UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11]):assert u.reg_read(r)==0x12340000+i
 result=u.reg_read(UC_ARM_REG_R0);return result if result<0x80000000 else result-0x100000000
phy_cases=[]
for rate,select in [(12000000,0),(24000000,1),(48000000,2)]:
 state['rate']=rate;state['clkerror']=False;put(CTRL+0xe00,0xa7);put(PHY+4,0xa8);put(PHY+8,0x80)
 assert call('a4_usb_hw_init',[0,CTRL])==0
 expect=[(CTRL+0xe00,0xa4),(PHY+0x60,0x200),(PHY,6),(PHY+0x1c,6),(PHY+0x44,0x733),(PHY+4,0xa8|select),(PHY+8,0x81),(PHY+8,0x80)]
 assert [x for x in state['writes'] if PHY<=x[0]<PHY+0x1000]==expect[1:],(rate,state['writes']);assert state['writes'][0]==expect[0] and state['delays']>=6
 phy_cases.append({'rate':rate,'select':select,'writes':len(expect)})
state['rate']=19000000;assert call('a4_usb_hw_init',[0,CTRL])==-22 and not state['writes']
state['clkerror']=True;assert call('a4_usb_hw_init',[0,CTRL])==-2 and not state['writes'];state['clkerror']=False
# N81 capacity and strict non-overlap of all dedicated FIFOs.
put(CTRL+0x4c,0x07e800e8);state['mode']='clear';assert call('s3c_hsotg_init_fifo',[BASE])==0
w=state['writes'];assert w[:2]==[(CTRL+0x24,512),(CTRL+0x28,(128<<16)|512)]
assert w[2:10]==[(CTRL+0x104+4*(i-1),(128<<16)|(640+128*(i-1))) for i in range(1,9)]
assert 640+128*8==1664<2024 and state['reads']==1
put(CTRL+0x4c,1024<<16);assert call('s3c_hsotg_init_fifo',[BASE])==-28 and not state['writes']
put(CTRL+0x4c,0x07e800e8);state['mode']='flush-stuck';assert call('s3c_hsotg_init_fifo',[BASE])==-110 and state['reads']==1000
state['mode']='reset-ok';assert call('s3c_hsotg_corereset',[BASE])==0
state['mode']='reset-stuck';assert call('s3c_hsotg_corereset',[BASE])==-22 and state['reads']<=10002
state['mode']='idle-stuck';assert call('s3c_hsotg_corereset',[BASE])==-110 and state['reads']<=10003
put(CTRL+0x804,0x12340002);assert call('s3c_hsotg_pullup',[BASE+gadget,1])==0 and get(CTRL+0x804)==0x12340000 and get(CTRL)&2
assert call('s3c_hsotg_pullup',[BASE+gadget,0])==0 and get(CTRL+0x804)==0x12340002
for bit,on,expect in [(1,1,1),(2,1,3),(2,0,1),(1,0,0)]:
 call('t4_usb_adb_flag',[bit,on]);call('t4_usb_snapshot',[BASE+0x8000])
 assert get(BASE+0x800c)==expect
call('t4_usb_irq_tick',[]);call('t4_usb_setup_tick',[]);call('t4_usb_snapshot',[BASE+0x8000])
assert get(BASE+0x8004)==1 and get(BASE+0x8008)==1
source=(SRC/'drivers/usb/gadget/s3c-hsotg.c').read_text();assert 'disable_irq(hsotg->irq)' not in source
assert source.count('if(ret) goto err_bound;')==2
report={'actual_native_PHY_cases':phy_cases,'PHY_invalid_reference_and_missing_clock_do_no_MMIO':True,'FIFO_N81_depth_2024_end_1664':True,'FIFO_capacity_rejection_before_writes':True,'FIFO_reset_and_AHB_idle_timeouts_bounded':True,'pullup_preserves_other_DCTL_bits':True,'kernel_ABI_preserved':True,'legacy_diagnostic_counters_unchanged':True,'GSNPSID_fixture':'0x4f54280a is modeled, not a T4 measurement','mock':'clock/logging/delay services and DWC/PHY register responses; no physical USB execution','hardware':'pending'}
(OUT/'usb-arm-test.json').write_text(json.dumps(report,indent=2)+'\n');print('USB_ARM_PASSED: exact A4 PHY writes; N81 FIFO bounds; timeout paths; pullup; no hardware claim')
