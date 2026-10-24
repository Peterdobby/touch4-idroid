#!/usr/bin/env python3
"""Execute actual old/fixed ARM handlers; model CP15 SCTLR reads/writes explicitly.
No hardware MMIO or USB. This is an instruction-level regression, not a device boot.
"""
from pathlib import Path
import json,struct,subprocess
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'saved/build/T4_ANDROID_UI_03';STOP=0x01000000
REGS=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_R12,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC]
def run(folder,control=0x10c5387f,saved=None):
 folder=ROOT/'saved/build'/folder
 nm=subprocess.check_output([str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-nm'),str(folder/'vmlinux')],text=True)
 sy={s[2]:int(s[0],16) for line in nm.splitlines() if len(s:=line.split())==3}
 uc=Uc(UC_ARCH_ARM,UC_MODE_ARM);uc.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A8)
 uc.mem_map(0xc0000000,0x800000);uc.mem_write(0xc0008000,(folder/'Image.expected').read_bytes())
 uc.mem_map(STOP,0x1000);uc.reg_write(UC_ARM_REG_SP,0xc07ff000);uc.reg_write(UC_ARM_REG_LR,STOP)
 uc.reg_write(UC_ARM_REG_CPSR,0xd3)
 uc.mem_write(sy['cr_alignment'],struct.pack('<II',control if saved is None else saved,(control if saved is None else saved)&~2))
 state={'control':control,'reads':0,'writes':0,'panic':None,'printk':[]}
 def string(addr):
  b=bytearray()
  for i in range(256):
   c=uc.mem_read(addr+i,1)[0]
   if not c:break
   b.append(c)
  return b.decode()
 def step(uc,pc,size,user):
  if pc==sy['panic']:
   state['panic']=string(uc.reg_read(UC_ARM_REG_R0));uc.emu_stop();return
  if pc==sy['printk']:
   state['printk'].append(string(uc.reg_read(UC_ARM_REG_R0)))
   uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  ins=struct.unpack('<I',uc.mem_read(pc,4))[0]
  if ins&0xffff0fff==0xee110f10:
   rd=(ins>>12)&15;uc.reg_write(REGS[rd],state['control']);state['reads']+=1;uc.reg_write(UC_ARM_REG_PC,pc+4)
  elif ins&0xffff0fff==0xee010f10:
   rd=(ins>>12)&15;state['control']=uc.reg_read(REGS[rd]);state['writes']+=1;uc.reg_write(UC_ARM_REG_PC,pc+4)
 uc.hook_add(UC_HOOK_CODE,step)
 uc.emu_start(sy['t4_early_noalign'],STOP,count=10000)
 state['returned']=uc.reg_read(UC_ARM_REG_PC)==STOP
 state['saved_alignment']=struct.unpack('<I',uc.mem_read(sy['cr_alignment'],4))[0]
 state['saved_noalignment']=struct.unpack('<I',uc.mem_read(sy['cr_no_alignment'],4))[0]
 return state
old=run('T4_ANDROID_INIT_03')
assert old['panic']=='T4_ALIGN SCTLR mismatch' and old['control']==0x10c5387d and old['reads']==1
new=run('T4_ANDROID_UI_03')
assert new['panic'] is None and new['returned'] and new['control']==0x10c5387d and new['reads']==2
assert new['saved_alignment']==new['saved_noalignment']==0x10c5387d
clear=run('T4_ANDROID_UI_03',control=0x10c5387d)
assert clear['returned'] and clear['panic'] is None and clear['control']==0x10c5387d
no_u=run('T4_ANDROID_UI_03',control=0x1085387f)
assert no_u['panic']=='T4_ALIGN U=0' and no_u['writes']==0
mismatch=run('T4_ANDROID_UI_03',saved=0x10c5387f^4)
assert mismatch['panic']=='T4_ALIGN SCTLR mismatch'
result={'old_false_panic_reproduced':old,'fixed_handler':new,'already_clear':'passed','missing_U_rejected':'passed','actual_mismatch_rejected':'passed','CP15':'explicit model for actual emitted MRC/MCR instructions; no hardware boot claim'}
(OUT/'noalign-arm-test.json').write_text(json.dumps(result,indent=2)+'\n')
print('OLD_FALSE_PANIC_REPRODUCED: hardware A cleared but stale compiler register compared; one SCTLR read')
print('FIXED_NOALIGN_ARM_PASSED: live second read; returns normally; both saved CRs updated; U=0 and real mismatch still rejected')
