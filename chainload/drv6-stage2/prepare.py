#!/usr/bin/env python3
"""Package the hardware-tested post-quiesce loader as an ibob candidate.
Host-only: no SSH, USB, exploit builder, installer or device writes.
"""
import hashlib,json,shutil,struct,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'saved/build/drv6-stage2-candidate'
sys.path.insert(0,str(ROOT/'chainload'))
from build import check_protected
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    previous=OUT/'MANIFEST.json'
    if previous.exists() and json.loads(previous.read_text()).get('status')=='PERSISTENT_TEST_FAILED_RECOVERY_REQUIRED':
        raise SystemExit('Disabled: this candidate failed persistent boot. Preserve its audit record and recover the original boot images first.')
    check_protected()
    loader=ROOT/'saved/build/chainload-iboot6/t4-oib-iboot6-loader.bin'
    native=ROOT/'saved/build/phase1-published/openiboot-native.bin'
    data=loader.read_bytes();original=native.read_bytes()
    assert data[4096:]==original and len(data)==286720
    evidence=ROOT/'saved/build/chainload-iboot6/logs/20261024-022104.log'
    evidence_data=evidence.read_bytes()
    assert b'CHAINLOAD_USB_VERSION_CONFIRMED' in evidence_data
    assert b'110f6d6f3ea892c23b2d55b42d88cc75e379b218a222bbaa9bfc26cead0d2608' in evidence_data
    stage=(ROOT/'saved/build/chainload-iboot6/iboot6-ram-stage.bin').read_bytes()
    # Tie the tested image to this exact candidate, rather than trust a filename.
    manifest=json.loads((ROOT/'saved/build/chainload-iboot6/manifest.json').read_text())
    assert sha(data)==manifest['files'][loader.name]
    assert sha(stage)==manifest['files']['iboot6-ram-stage.bin']
    assert stage.count(data)==1
    assert sha((ROOT/'saved/build/chainload-iboot6/iboot6-ram-test-native.bin').read_bytes())=='110f6d6f3ea892c23b2d55b42d88cc75e379b218a222bbaa9bfc26cead0d2608'
    OUT.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(loader,OUT/'openiboot-stage2.raw')
    maker=ROOT.parent/'touch4-idroid-untethered/research/Legacy-iOS-Kit-reference/bin/macos/img3maker'
    assert sha(maker.read_bytes())=='a30a074b4740e935cf1696736b1309db8b42b38d9b446e18fbdbb596a7355aea'
    image=OUT/'openiboot-stage2.ibob.img3'
    subprocess.run([str(maker),'-f',str(loader),'-o',str(image),'-t','ibob'],check=True)
    container=image.read_bytes()
    magic,total,body,shsh,kind=struct.unpack_from('<5I',container)
    assert magic==0x496d6733 and total==len(container) and body==total-20
    assert kind==0x69626f62 and shsh==0
    offset=20;tags=[];payloads=[]
    while offset<len(container):
        tag,size,length=struct.unpack_from('<3I',container,offset)
        assert 12<=size<=len(container)-offset and length<=size-12
        tags.append(dict(type=struct.pack('>I',tag).decode('ascii'),offset=offset,size=size,length=length))
        if tag==0x44415441:payloads.append(container[offset+12:offset+12+length])
        offset+=size
    assert offset==len(container) and payloads==[data]
    info=dict(status='PACKAGED_NOT_INSTALLED_NOT_COLD_BOOT_VERIFIED',
        type='ibob',load_address='0x44000000',entry='0x44000000 ARM after native jump_to cleanup',
        size=len(container),sha256=sha(container),data_sha256=sha(data),tags=tags,
        unsigned_container=True,existing_drv6_loader_acceptance_unverified=True,
        ram_evidence=dict(path=str(evidence),sha256=sha(evidence_data),
                          scope='isolated CPU/loader handoff, not full DRV6'),
        original_native_sha256=sha(original),native_input_and_android_unchanged=True,
        signature_verification_or_exploit_code_changes=False,device_writes=False,
        pending=['Read and back up actual installed second-stage image and boot-image layout.',
                 'Determine actual existing image capacity, container requirements and reversible update method.',
                 'Obtain explicit scope change before persistent writes forbidden by current user instructions.'])
    (OUT/'MANIFEST.json').write_text(json.dumps(info,indent=2)+'\n')
    check_protected()
    print('Prepared:',image)
    print('Container DATA byte-identical to tested post-quiesce loader.')
    print('This is a candidate, not an installer or proof of cold boot.')
if __name__=='__main__':main()
