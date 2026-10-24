#!/usr/bin/env python3
"""Verify minimal CPIO/config, then run actual static PID1 against RAM syscall fixtures."""
from pathlib import Path
import gzip,hashlib,json,struct,subprocess,sys
from unicorn import *
from unicorn.arm_const import *
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R));from prepare_android import unpack_cpio
O=R/'saved/build/T4_USB_ACM_01';m=json.loads((O/'manifest.json').read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for p,d in m['protected_baselines'].items():assert sha(Path(p))==d,p
for n,d in m['files'].items():assert sha(O/n)==d['sha256'],n
records,files=unpack_cpio(gzip.decompress((O/'initramfs.cpio.gz').read_bytes()))
assert set(files)=={'dev','proc','sys','dev/kmsg','dev/console','init'}
assert all(x['mode']&0o170000!=0o60000 for x in records)
c=(O/'kernel.config').read_text()
for n in ['USB_G_SERIAL','USB_S3C_HSOTG','USB_GADGET']:assert f'CONFIG_{n}=y\n' in c
for n in ['USB_G_ANDROID','USB_STORAGE','MTD','MMC','SCSI','ATA','SUSPEND','PM_RUNTIME']:assert f'CONFIG_{n}=y\n' not in c,n
elf=files['init'];entry=struct.unpack_from('<I',elf,24)[0];ph=struct.unpack_from('<I',elf,28)[0];size,num=struct.unpack_from('<HH',elf,42)
u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A8)
for i in range(num):
 p=struct.unpack_from('<8I',elf,ph+i*size)
 if p[0]!=1:continue
 a=p[2]&~4095;end=(p[2]+p[5]+4095)&~4095;u.mem_map(a,end-a);u.mem_write(p[2],elf[p[1]:p[1]+p[4]])
u.mem_map(0x70000000,0x10000);u.reg_write(UC_ARM_REG_SP,0x7000fff0)
def string(p):
 b=b''
 while True:
  x=bytes(u.mem_read(p,1));p+=1
  if x==b'\0':return b.decode()
  b+=x
state={'mounts':[],'nodes':[],'writes':[],'fds':{},'loops':0,'echoed':False};fixture=b'U=20 IRQ=3 SET=4 ID=fixture\n'
def svc(u,no,data):
 n=u.reg_read(UC_ARM_REG_R7);a,b,c,d,e=[u.reg_read(x) for x in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4]];ret=0
 if n==21:
  what,where,kind=map(string,[a,b,c]);assert (what,where,kind) in [('proc','/proc','proc'),('sysfs','/sys','sysfs')];state['mounts'].append((what,where,kind))
 elif n==5:
  p=string(a);assert p in ['/dev/kmsg','/sys/class/tty/ttyGS0/dev','/sys/devices/platform/s3c-hsotg/usb_state','/dev/ttyGS0'],p
  ret=3+len(state['fds']);state['fds'][ret]=p
 elif n==6:pass
 elif n==3:
  p=state['fds'][a]
  if p.endswith('/ttyGS0/dev'):payload=b'253:0\n'
  elif p.endswith('/usb_state'):payload=fixture
  elif p=='/dev/ttyGS0':payload=b'T4_HOST_ECHO_CHECK\n' if not state['echoed'] else b'';state['echoed']=True
  else:raise AssertionError(p)
  u.mem_write(b,payload);ret=len(payload)
 elif n==4:
  state['writes'].append((state['fds'][a],bytes(u.mem_read(b,c)).decode())) ;ret=c
 elif n==14:
  assert string(a)=='/dev/ttyGS0' and b==0o20600 and c==(253<<8)
  state['nodes'].append((string(a),b,c))
 elif n==162:
  state['loops']+=1
  if state['loops']==7:u.emu_stop()
 else:raise AssertionError(('unexpected syscall',n))
 u.reg_write(UC_ARM_REG_R0,ret)
u.hook_add(UC_HOOK_INTR,svc);u.emu_start(entry,0,count=2000000)
assert state['loops']==7 and len(state['mounts'])==2 and len(state['nodes'])==1,state
assert any(p=='/dev/kmsg' and 'PID1_REACHED' in s for p,s in state['writes'])
assert any(p=='/dev/ttyGS0' and 'RAM serial alive' in s for p,s in state['writes'])
assert any(p=='/dev/ttyGS0' and 'T4_HOST_ECHO_CHECK' in s for p,s in state['writes'])
state.update(physical_hardware='not executed; syscalls are mocked',protected_baseline_files=len(m['protected_baselines']),cpio_files=len(files),ADB_disabled=True)
(O/'bundle-test.json').write_text(json.dumps(state,indent=2)+'\n');print('BUNDLE_PASS: protected builds intact; ACM only; actual ARM PID1 heartbeat/echo; RAM character nodes only')
