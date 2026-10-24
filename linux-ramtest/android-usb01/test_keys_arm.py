#!/usr/bin/env python3
"""Run the shared debounce logic and exact native GPIO reader under ARM emulation.
This exercises instructions against simulated registers, never physical hardware.
"""
from pathlib import Path
import json,subprocess,struct,gzip,sys
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE,UC_PROT_READ
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
OUT=ROOT/'saved/build/T4_ANDROID_USB_01';SOURCE=ROOT/'saved/sources/iDroid-kernel-T4_ANDROID_USB_01'
CROSS=str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-')
subprocess.run([CROSS+'gcc','-O2','-marm','-mcpu=cortex-a8','-nostdlib','-static','-fno-use-linker-plugin',
    '-fno-builtin','-fno-stack-protector','-Wl,--build-id=none','-Wl,-Ttext,0x10000','-Wl,-e,main',
    '-I'+str(SOURCE/'arch/arm/mach-s5l8930'),str(HERE/'test_keys.c'),'-o',str(OUT/'test-keys.elf')],check=True)
assert not subprocess.check_output([CROSS+'nm','-u',str(OUT/'test-keys.elf')],text=True).strip()
uc=Uc(UC_ARCH_ARM,UC_MODE_ARM);uc.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A8)
uc.mem_map(0x8000,0x20000);uc.mem_map(0x2000000,0x10000);uc.mem_map(0x3000000,0x1000)
elf=(OUT/'test-keys.elf').read_bytes();entry=struct.unpack_from('<I',elf,24)[0]
ph=struct.unpack_from('<I',elf,28)[0];size,count=struct.unpack_from('<HH',elf,42)
for i in range(count):
    p=struct.unpack_from('<8I',elf,ph+i*size)
    if p[0]==1 and p[4]:uc.mem_write(p[2],elf[p[1]:p[1]+p[4]])
uc.reg_write(UC_ARM_REG_SP,0x200fff0);uc.reg_write(UC_ARM_REG_LR,0x3000000)
uc.emu_start(entry,0x3000000,count=2000000)
assert uc.reg_read(UC_ARM_REG_PC)==0x3000000
assert uc.reg_read(UC_ARM_REG_R0)==0,('test_keys.c failed at line',uc.reg_read(UC_ARM_REG_R0))

nm=subprocess.check_output([CROSS+'nm',str(OUT/'vmlinux')],text=True)
sy={p[2]:int(p[0],16) for l in nm.splitlines() if len(p:=l.split())==3}
uc=Uc(UC_ARCH_ARM,UC_MODE_ARM);uc.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A8)
uc.mem_map(0xc0000000,0x800000);uc.mem_write(0xc0008000,(OUT/'Image.expected').read_bytes())
uc.mem_map(0xfcd00000,0x1000);uc.mem_map(0x1000000,0x1000)
reads=[];writes=[]
uc.hook_add(UC_HOOK_MEM_READ,lambda u,a,addr,size,value,d: reads.append((addr,size)),begin=0xfcd00000,end=0xfcd00fff)
uc.hook_add(UC_HOOK_MEM_WRITE,lambda u,a,addr,size,value,d: writes.append((addr,size)),begin=0xfcd00000,end=0xfcd00fff)
cases=0
for high in [0,0xdeadbeee]:
    for mask in range(256):
        for pin in range(8):uc.mem_write(0xfcd00000+pin*4,struct.pack('<I',high|int(not(mask>>pin&1))))
        uc.mem_protect(0xfcd00000,0x1000,UC_PROT_READ)
        reads.clear();uc.reg_write(UC_ARM_REG_CPSR,0xd3)
        uc.reg_write(UC_ARM_REG_LR,0x1000000);uc.reg_write(UC_ARM_REG_SP,0xc07ff000)
        uc.emu_start(sy['t4_read_keys'],0x1000000,count=200)
        assert uc.reg_read(UC_ARM_REG_PC)==0x1000000
        assert uc.reg_read(UC_ARM_REG_R0)==(mask&15)
        assert reads==[(0xfcd00000+i*4,4) for i in range(8)] and not writes
        cases+=1

sys.path.insert(0,str(ROOT));from prepare_android import unpack_cpio
_,files=unpack_cpio(gzip.decompress((OUT/'initramfs.cpio.gz').read_bytes()))
layout=files['system/usr/keylayout/t4-ram-keys.kl'].decode()
mapping={int(p[1]):p[2] for l in layout.splitlines() if (p:=l.split()) and p[0]=='key'}
assert mapping=={28:'DPAD_CENTER',102:'HOME',1:'BACK',139:'MENU',115:'DPAD_UP',114:'DPAD_DOWN'}
assert b'/dev/input/*              0660   root       input' in files['ueventd.rc']
assert b'input keyevent 82' not in files['sbin/t4-ui-watch.sh']
driver=(SOURCE/'arch/arm/mach-s5l8930/t4-keys.c').read_text()
for bad in ['writel(','gpio_direction','request_irq(','gpio_set_value(']:assert bad not in driver,bad
report={'ARM_debounce_hold_boot_held_and_wrap_regressions':True,'exact_native_GPIO_read_cases':cases,
 'MMIO_writes':len(writes),'polled_key_pins':[0,1,2,3],'diagnostic_pin_reads':list(range(8)),'kernel_virtual_gpio':'0xfcd00000',
 'public_OpeniBoot_physical_gpio':'0xbfa00000',
 'evdev_permissions_and_device_name_keylayout_checked':True,'hardware_input':'pending','touch':'not registered'}
(OUT/'input-arm-test.json').write_text(json.dumps(report,indent=2)+'\n')
print('INPUT_ARM_PASSED:',cases,'exact native read cases; bounce/short/long/boot-held/tick-wrap; no MMIO writes; UI07 userspace preserved')
