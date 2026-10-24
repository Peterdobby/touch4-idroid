#!/usr/bin/env python3
"""Batch native/JNI/config regressions against the actual packaged bytes."""
from pathlib import Path
import gzip,json,struct,sys,subprocess
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_INTR
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'saved/build/T4_ANDROID_UI_07'
sys.path[:0]=[str(ROOT),str(ROOT/'saved/research/runtime-analysis'),str(Path(__file__).resolve().parent)]
from prepare_android import unpack_cpio
from server_jni_audit import audit
from native_compat import patch_battery
_,f=unpack_cpio(gzip.decompress((OUT/'initramfs.cpio.gz').read_bytes()))
original=(ROOT/'saved/build/android-prepared/system-root/lib/libandroid_servers.so').read_bytes()
fixed=f['system/lib/libandroid_servers.so'];assert patch_battery(original)[0]==fixed
old_missing=audit(original,missing=True)
new_missing=audit(fixed,missing=True)
old_empty=audit(original,missing=False)
new_empty=audit(fixed,missing=False)
assert len(old_missing['registrations'])==8 and not old_missing['battery_values']
for case in [new_missing,old_empty,new_empty]:
    assert len(case['registrations'])==9 and case['JNI_cached_IDs_checked_against_DEX']==84
    assert case['return']=='0x10004'
assert new_missing['registrations']==old_empty['registrations']==new_empty['registrations']
assert new_missing['battery_values']==old_empty['battery_values']==new_empty['battery_values']
assert new_missing['battery_values']=={'mAcOnline':0,'mUsbOnline':0,'mBatteryPresent':0,'mBatteryLevel':0,'mBatteryVoltage':0,'mBatteryTemperature':0,'mBatteryStatus':1}
assert new_missing['mocked_filesystem']==[['opendir','/sys/class/power_supply']]
for case in [old_missing,new_missing,old_empty,new_empty]:assert not any('mismatch' in x for x in case['logs'])

# Run the actual freestanding ARM clock ELF, checking its only privileged
# operation is Linux settimeofday. Neither RTC/alarm ioctl nor devices exist.
def clock(args,fail=False):
    d=f['sbin/t4-ramclock'];uc=Uc(UC_ARCH_ARM,UC_MODE_ARM);uc.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A8)
    ph=struct.unpack_from('<I',d,28)[0];ps,pn=struct.unpack_from('<HH',d,42);pages=set()
    for i in range(pn):
        p=struct.unpack_from('<8I',d,ph+ps*i)
        if p[0]!=1 or not p[5]:continue
        for a in range(p[2]&~4095,(p[2]+p[5]+4095)&~4095,4096):
            if a not in pages:uc.mem_map(a,4096);pages.add(a)
        uc.mem_write(p[2],d[p[1]:p[1]+p[4]])
    uc.mem_map(0x70000000,0x10000);argv=[];pos=0x70000100
    for text in ['t4-ramclock']+args:
        uc.mem_write(pos,text.encode()+b'\0');argv.append(pos);pos+=len(text)+1
    uc.mem_write(0x7000f000,struct.pack('<'+'I'*(len(argv)+2),len(argv),*argv,0))
    uc.reg_write(UC_ARM_REG_CPSR,0x10);uc.reg_write(UC_ARM_REG_SP,0x7000f000);result={'settimeofday':[],'stdout':'','exit':None,'syscalls':[]}
    def syscall(uc,num,data):
        n=uc.reg_read(UC_ARM_REG_R7);a=uc.reg_read(UC_ARM_REG_R0);b=uc.reg_read(UC_ARM_REG_R1);c=uc.reg_read(UC_ARM_REG_R2);result['syscalls'].append(n)
        if n==79:
            assert b==0;result['settimeofday'].append(struct.unpack('<ii',uc.mem_read(a,8)));uc.reg_write(UC_ARM_REG_R0,0xffffffff if fail else 0)
        elif n==4:
            assert a==1;result['stdout']+=bytes(uc.mem_read(b,c)).decode();uc.reg_write(UC_ARM_REG_R0,c)
        elif n==1:result['exit']=a;uc.emu_stop()
        else:raise AssertionError(('unexpected privileged/syscall operation',n))
    uc.hook_add(UC_HOOK_INTR,syscall);uc.emu_start(struct.unpack_from('<I',d,24)[0],0,count=10000)
    assert result['exit'] is not None
    return result
valid=clock([f['sbin/t4-ram-epoch'].decode().strip()]);assert valid['exit']==0 and len(valid['settimeofday'])==1 and valid['stdout'].endswith('\n')
for args in [[],['abc'],['0'],['2147483648'],['999999999999999999999']]:
    c=clock(args);assert c['exit']==1 and not c['settimeofday']
failed=clock(['1792339200'],True);assert failed['exit']==1 and not failed['stdout']
rc=f['init.rc'].decode();sf=rc.split('service surfaceflinger ',1)[1].split('\nservice ',1)[0]
assert '\n    user root\n' in sf and '\n    group graphics system\n' in sf
for n in ['zImage','Image.expected','Image.instrumented','vmlinux','kernel.config']:
    assert (OUT/n).read_bytes()==(ROOT/'saved/build/T4_ANDROID_UI_04'/n).read_bytes(),n
result={'JNI_without_sysfs_original_8_patched_9':True,'registration_groups':9,
        'native_method_signatures_checked':sum(len(r['methods']) for r in new_missing['registrations']),
        'JNI_cached_fields_methods_checked':84,'all_types_static_instance_and_native_flags_match_original_DEX':True,
        'existing_power_supply_path_unchanged':True,'battery_UNKNOWN_not_fabricated_readings':new_missing['battery_values'],
        'RAM_clock_actual_ARM':valid,'clock_invalid_and_failed_syscall_rejected':True,'RTC_or_device_operations':0,
        'SF_VT_permission_configured':True,'UI04_kernel_identical':True,
        'mock_limits':'VM/JNI/libc filesystem calls explicitly mocked; actual ARM register/update functions executed; no real Dalvik/hardware success claim',
        'hardware_desktop':'pending'}
(OUT/'bundle-test.json').write_text(json.dumps(result,indent=2)+'\n')
(OUT/'jni-audit.json').write_text(json.dumps({'original_missing_sysfs':old_missing,'patched_missing_sysfs':new_missing,'original_empty_sysfs':old_empty,'patched_empty_sysfs':new_empty},indent=2)+'\n')
print('BUNDLE_PASSED: 9 JNI groups,',result['native_method_signatures_checked'],'native signatures, 84 field/method IDs; original failure reproduced; UNKNOWN battery; RAM-only clock ARM; kernel unchanged')
