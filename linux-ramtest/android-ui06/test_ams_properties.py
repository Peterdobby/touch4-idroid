#!/usr/bin/env python3
"""Regress the photographed AMS static-initializer failure using real inputs.
Validate all properties against original androidi4 and vendor_apple init.rc,
not an invented list. Verify only the intended root files change and the
tested kernel/system are preserved. Offline only; no Android success claim.
"""
from pathlib import Path
import gzip,json,re,sys
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'saved/build/T4_ANDROID_UI_06'
sys.path.insert(0,str(ROOT));from prepare_android import unpack_cpio
java=(ROOT/'saved/research/idroid-legacy/platform_frameworks_base/services/java/com/android/server/am/ActivityManagerService.java').read_text()
required=re.findall(r'getIntProp\("(ro\.\w+)", (true|false)\)',java)
assert len(required)==18
def read(variant):
    return unpack_cpio(gzip.decompress((ROOT/'saved/build'/variant/'initramfs.cpio.gz').read_bytes()))[1]
old=read('T4_ANDROID_UI_05');new=read('T4_ANDROID_UI_06')
def boot_properties(rc):
    props={};in_boot=False
    for line in rc.splitlines():
        if line and not line[0].isspace():in_boot=line=='on boot'
        if not in_boot:continue
        args=line.split()
        if args[:2]==['start','t4-dynamic-probe']:break
        if len(args)==3 and args[0]=='setprop':props[args[1]]=args[2]
    return props
before=boot_properties(old['init.rc'].decode());after=boot_properties(new['init.rc'].decode())
missing=[n for n,zero in required if not before.get(n)]
assert len(missing)==9 and missing[0]=='ro.FOREGROUND_APP_MEM'
assert all(n.endswith('_MEM') for n in missing)
assert 'FOREGROUND_APP_MEM = getIntProp("ro.FOREGROUND_APP_MEM", false)' in java.splitlines()[370]
try:int(before.get(missing[0],''))
except ValueError:pass
else:raise AssertionError('missing property must fail integer conversion')
for rel in ['saved/research/idroid-legacy/vendor_apple/common/init.rc','saved/build/android-prepared/ramdisk-text/init.rc']:
    reference=dict(re.findall(r'^\s+setprop (ro\.\w+) (\d+)\s*$',(ROOT/rel).read_text(),re.M))
    for name,allow_zero in required:
        assert after[name]==reference[name],(rel,name)
        assert after[name].isdigit()
        assert allow_zero=='true' or int(after[name])>0
        assert name.encode()+b'\0' in new['system/framework/services.odex'],name
delta={n for n in set(old)|set(new) if old.get(n)!=new.get(n)}
assert delta=={'init.rc','sbin/t4-dynamic-probe.sh'},delta
probe=new['sbin/t4-dynamic-probe.sh'].decode()
for name,_ in required:assert name in probe,name
assert probe.index('T4_AMS_PROPERTIES_READY')<probe.index('setprop t4.dynamic.ready 1')
for n in ['zImage','zImage.original','Image.expected','Image.instrumented','vmlinux','kernel.config']:
    assert (OUT/n).read_bytes()==(ROOT/'saved/build/T4_ANDROID_UI_04'/n).read_bytes(),n
result={'UI05_missing_properties':missing,'first_failure_matches_photo':'ActivityManagerService.java:371 ro.FOREGROUND_APP_MEM empty integer',
        'AMS_integer_properties_validated':len(required),'values_match_original_androidi4_and_legacy_idroid':True,
        'actual_services_odex_contains_all_property_names':True,'root_delta':sorted(delta),
        'UI04_kernel_byte_identical':True,'all_original_system_and_init_bytes_preserved':True,
        'hardware_desktop':'pending'}
(OUT/'ams-properties-test.json').write_text(json.dumps(result,indent=2)+'\n')
print('AMS_PROPERTIES_PASSED: UI05 missing 9 MEM values reproduces line 371; UI06 all 18 match both original references; kernel/system unchanged')
