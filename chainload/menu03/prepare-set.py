#!/usr/bin/env python3
"""Prepare the already successful complete boot-image transaction with a new menu.
Six other images (including Apple's personalized LLB/ticket) remain byte exact.
This builds and tests host files only; it does not connect or install anything.
"""
import hashlib,importlib.util,json,shutil,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'saved/build/untethered-menu-03'
INSTALL=OUT/'install';OLD=ROOT/'saved/build/untethered-oib-02'
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    if (INSTALL/'APPLY-ATTEMPT.json').exists():raise SystemExit('Preserve the audited installed image set.')
    menu=json.loads((OUT/'MENU-BUILD.json').read_text())
    ibob=(OUT/'OpeniBoot-menu.ibob.img3').read_bytes();assert sha(ibob)==menu['ibob_sha256']
    old=json.loads((OLD/'MANIFEST.json').read_text());pins={r['name']:r for r in old['images']}
    (INSTALL/'images').mkdir(parents=True,exist_ok=True);records=[]
    for name in old['minimal_order']:
        data=ibob if name=='OpeniBoot.ibob.img3' else (OLD/'images'/name).read_bytes()
        if name!='OpeniBoot.ibob.img3':assert sha(data)==pins[name]['sha256']
        (INSTALL/'images'/name).write_bytes(data)
        records.append(dict(name=name,size=len(data),sha256=sha(data),
           type=struct.pack('>I',struct.unpack_from('<I',data,16)[0]).decode('ascii')))
    total=sum(r['size'] for r in records);assert total==menu['complete_firmware_set_bytes'] and total<0x180000
    manifest=dict(name='T4_UNTETHERED_MENU_03',status='PREPARED_NOT_INSTALLED',ecid=old['ecid'],
       minimal_order=old['minimal_order'],minimal_bytes=total,images=records,
       six_non_menu_images_byte_exact=True,existing_dra_partition_unchanged=True,
       new_exploit_or_signature_patches=False,device_writes=False,
       runtime_files=['/boot/t4/android.img3','/boot/t4/devicetree-ios7.img3'],
       ios_profile='Current Kit 7.1.2/11D257; other iOS versions require a matching profile')
    (INSTALL/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    for name in ['build-set','test-set']:
        spec=importlib.util.spec_from_file_location('menu03_'+name,ROOT/('chainload/untethered-oib02/'+name+'.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.OUT=INSTALL;module.main()
    print('Prepared full image set; only OpeniBoot ibob differs from successful OIB02. Nothing installed.')
if __name__=='__main__':main()
