#!/usr/bin/env python3
"""Exercise actual evdev_read ARM; only user-copy boundary is modeled."""
from pathlib import Path
import json,struct,subprocess,shlex
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'saved/build/T4_ANDROID_USB_01';SOURCE=ROOT/'saved/sources/iDroid-kernel-T4_ANDROID_USB_01';CROSS=str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-')
fields=['sizeof(struct file)','offsetof(struct file,f_flags)','offsetof(struct file,private_data)','sizeof(struct evdev)','offsetof(struct evdev,exist)','offsetof(struct evdev_client,evdev)','offsetof(struct evdev_client,head)','offsetof(struct evdev_client,tail)','offsetof(struct evdev_client,packet_head)','offsetof(struct evdev_client,bufsize)','offsetof(struct evdev_client,buffer)','offsetof(struct input_dev,h_list)','offsetof(struct input_handle,d_node)','offsetof(struct input_handle,handler)','offsetof(struct input_handle,open)','offsetof(struct input_handler,name)']
(OUT/'evdev-offsets.c').write_text('#include "'+str(SOURCE/'drivers/input/evdev.c')+'"\nconst unsigned t4_evdev_offsets[]={'+','.join(fields)+'};\n')
cmd=(SOURCE/'drivers/input/.evdev.o.cmd').read_text().splitlines()[0].split(' := ',1)[1]
flags=shlex.split(cmd);flags=flags[:flags.index('-c')];flags=[x for x in flags if not x.startswith(('-Wp,','-DKBUILD'))]
subprocess.run(flags+['-DKBUILD_MODNAME="evdev"','-c',str(OUT/'evdev-offsets.c'),'-o',str(OUT/'evdev-offsets.o')],cwd=SOURCE,check=True,stdout=subprocess.DEVNULL)
nm=subprocess.check_output([CROSS+'nm','-S',str(OUT/'evdev-offsets.o')],text=True)
p=next(l.split() for l in nm.splitlines() if l.split()[-1]=='t4_evdev_offsets');offset=int(p[0],16)
subprocess.run([CROSS+'objcopy','-O','binary','-j','.rodata',str(OUT/'evdev-offsets.o'),str(OUT/'evdev-offsets.bin')],check=True)
fsize,fflags,private,esize,exist,clientev,head,tail,packet,bufsize,buffer,hlist,dnode,handler,handleopen,handlername=struct.unpack_from('<16I',(OUT/'evdev-offsets.bin').read_bytes(),offset)
results={}
for variant in ['T4_ANDROID_INPUT_01','T4_ANDROID_USB_01']:
 folder=ROOT/'saved/build'/variant
 sy={p[2]:int(p[0],16) for l in subprocess.check_output([CROSS+'nm',str(folder/'vmlinux')],text=True).splitlines() if len(p:=l.split())==3}
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A8)
 u.mem_map(0xc0000000,0x1000000);u.mem_write(0xc0008000,(folder/'Image.expected').read_bytes())
 BASE=0xc5000000;FILE=BASE;CLIENT=BASE+0x2000;EVDEV=BASE+0x4000;USER=BASE+0x6000;STOP=0x1000000
 u.mem_map(BASE,0x10000);u.mem_map(STOP,0x1000)
 copyfail=False
 def hook(u,pc,size,data):
  if pc==sy['input_event_to_user']:
   if not copyfail:u.mem_write(u.reg_read(UC_ARM_REG_R0),bytes(u.mem_read(u.reg_read(UC_ARM_REG_R1),16)))
   u.reg_write(UC_ARM_REG_R0,int(copyfail));u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 def put(a,v):u.mem_write(a,struct.pack('<I',v))
 events=struct.pack('<llHHi',1,2,1,28,1)+struct.pack('<llHHi',1,2,0,0,0)
 cases=[]
 for count,n,live,fail,expect in [(8,2,1,False,-22),(16,2,1,False,16),(32,2,1,False,32),(64,2,1,False,32),(64,0,1,False,-11),(32,2,0,False,-19),(32,2,1,True,-14)]:
  u.mem_write(BASE,bytes(0x10000));put(FILE+fflags,0x802);put(FILE+private,CLIENT);put(CLIENT+clientev,EVDEV)
  u.mem_write(EVDEV+exist,bytes([live]));put(CLIENT+head,n);put(CLIENT+packet,n);put(CLIENT+bufsize,64);u.mem_write(CLIENT+buffer,events)
  copyfail=fail
  for reg in range(UC_ARM_REG_R0,UC_ARM_REG_R12+1):u.reg_write(reg,0xdeadbeef)
  u.reg_write(UC_ARM_REG_CPSR,0xd3);u.reg_write(UC_ARM_REG_SP,0xc0fff000);u.reg_write(UC_ARM_REG_LR,STOP)
  for reg,value in [(UC_ARM_REG_R0,FILE),(UC_ARM_REG_R1,USER),(UC_ARM_REG_R2,count),(UC_ARM_REG_R3,0)]:u.reg_write(reg,value)
  u.emu_start(sy['evdev_read'],STOP,count=10000)
  assert u.reg_read(UC_ARM_REG_PC)==STOP
  ret=u.reg_read(UC_ARM_REG_R0);ret=ret if ret<0x80000000 else ret-0x100000000
  assert ret==expect,(variant,count,n,live,fail,ret,expect)
  if ret>0:assert bytes(u.mem_read(USER,ret))==events[:ret]
  cases.append({'count':count,'events':n,'live':live,'copy_fail':fail,'return':ret})
 results[variant]=cases
# Prove OPEN excludes VT keyboard and reports only an opened evdev handle.
INPUT=BASE+0x8000;A=BASE+0x9000;B=BASE+0x9200;HA=BASE+0xa000;HB=BASE+0xa200
put(sy['keys'],INPUT);put(sy['t4_registered'],1)
put(INPUT+hlist,A+dnode);put(INPUT+hlist+4,B+dnode)
put(A+dnode,B+dnode);put(A+dnode+4,INPUT+hlist)
put(B+dnode,INPUT+hlist);put(B+dnode+4,A+dnode)
put(A+handler,HA);put(B+handler,HB);put(A+handleopen,1)
put(HA+handlername,BASE+0xb000);u.mem_write(BASE+0xb000,b'kbd\0')
put(HB+handlername,BASE+0xb100);u.mem_write(BASE+0xb100,b'evdev\0')
for is_open in [0,1]:
 put(B+handleopen,is_open)
 u.reg_write(UC_ARM_REG_SP,0xc0fff000);u.reg_write(UC_ARM_REG_LR,STOP);u.reg_write(UC_ARM_REG_R0,USER)
 u.emu_start(sy['t4_keys_snapshot'],STOP,count=10000)
 assert u.reg_read(UC_ARM_REG_PC)==STOP
 v=struct.unpack('<8I',bytes(u.mem_read(USER,32)))
 assert v[3]==1 and v[4]==is_open,('VT counted as evdev',v)
body=(SOURCE/'drivers/input/evdev.c').read_text().split('static ssize_t evdev_read(',1)[1].split('static unsigned int evdev_poll',1)[0]
assert 'int retval = 0;' in body
report={'actual_native_nonblocking_read_cases':results,'native_snapshot_excludes_VT_keyboard':True,'old_compiled_read_also_passes':True,'source_undefined_initial_value_fixed':True,'not_claimed_as_hardware_failure_cause':True,'mock':'input_event_to_user copy boundary only; no physical input or USB','hardware':'pending'}
(OUT/'evdev-arm-test.json').write_text(json.dumps(report,indent=2)+'\n');print('EVDEV_ARM_PASSED: 14 actual old/new read cases; old compiled read also passes; source initialization hardened')
