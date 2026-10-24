#!/usr/bin/env python3
"""Build a host-only N81 boot image set; never connects to a device."""
import os
import hashlib,json,plistlib,struct,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'saved/build/untethered-oib-02'
KIT=Path(os.environ.get('T4_KIT_DIR', str(Path.home() / 'Legacy-iOS-Kit')))
ECID=int(os.environ.get('T4_ECID', '0'), 0)
sys.path.insert(0,str(ROOT/'chainload'))
from build import check_protected
def sha(b):return hashlib.sha256(b).hexdigest()
def elements(data,start=20):
    off=start; result=[]
    while off<len(data):
        tag,size,length=struct.unpack_from('<III',data,off)
        assert size>=12 and length<=size-12 and off+size<=len(data)
        result.append((tag,off,data[off:off+size],data[off+12:off+12+length]))
        off+=size
    assert off==len(data)
    return result
def main():
    if (OUT/'APPLY-ATTEMPT.json').exists():
        raise SystemExit('An installed-test audit exists. Preserve this exact build instead of regenerating it.')
    check_protected(); OUT.mkdir(exist_ok=True)
    ticket_path=next(OUT.glob('*_iPod4,1_n81ap_6.1.6-10B500_*.shsh2'))
    ticket=plistlib.loads(ticket_path.read_bytes())
    signature=ticket['LLB']['Blob']; tags=elements(signature,0)
    assert [t[0] for t in tags]==[0x45434944,0x53485348,0x43455254]
    assert struct.unpack('<Q',tags[0][3])[0]==ECID
    images=OUT/'images';images.mkdir(exist_ok=True)
    with zipfile.ZipFile(ROOT/'saved/research/touch-bringup/apple-inputs/iPod4,1_6.1.6_10B500_Restore.ipsw') as z:
        build=plistlib.loads(z.read('BuildManifest.plist'))
        assert build['ProductBuildVersion']=='10B500'
        identity=build['BuildIdentities'][0]
        assert identity['Info']['DeviceClass']=='n81ap'
        assert ticket['LLB']['PartialDigest']==identity['Manifest']['LLB']['PartialDigest']
        prefix='Firmware/all_flash/all_flash.n81ap.production/'
        names=z.read(prefix+'manifest').decode().splitlines()
        for name in names:(images/name).write_bytes(z.read(prefix+name))
    llb=images/'LLB.n81ap.RELEASE.img3';original=llb.read_bytes();parts=elements(original)
    kept=[t for t in parts if t[0] not in (0x45434944,0x53485348,0x43455254)]
    body=b''.join(t[2] for t in kept)+signature
    shsh_offset=sum(len(t[2]) for t in kept)+len(tags[0][2])
    personalised=struct.pack('<5I',0x496d6733,20+len(body),len(body),shsh_offset,0x696c6c62)+body
    llb.write_bytes(personalised)
    # Only Apple's ECID/SHSH/CERT records change. The encrypted LLB is untouched.
    assert next(t[3] for t in elements(personalised) if t[0]==0x44415441)==next(t[3] for t in parts if t[0]==0x44415441)
    loader=(ROOT/'saved/build/chainload-iboot6/t4-oib-iboot6-loader.bin').read_bytes()
    native=(ROOT/'saved/build/phase1-published/openiboot-native.bin').read_bytes()
    assert sha(loader)=='fdede46db6adf433d4c91677183083cbf559f8580f140b2da06f1f35b3aa7a43'
    assert loader[4096:]==native
    ibob=(ROOT/'saved/build/drv6-stage2-candidate/openiboot-stage2.ibob.img3').read_bytes()
    assert next(t[3] for t in elements(ibob) if t[0]==0x44415441)==loader
    (images/'OpeniBoot.ibob.img3').write_bytes(ibob)
    (OUT/'apticket.der').write_bytes(ticket['APTicket'])
    subprocess.run([str(KIT/'bin/macos/xpwntool'),str(OUT/'apticket.der'),str(images/'applelogoT.img3'),'-t',str(KIT/'resources/firmware/src/scab_template.img3')],check=True)
    # Normal cold-boot subset. Charging artwork is not required by this target.
    minimal=[names[0],names[1],'DeviceTree.n81ap.img3','applelogo@2x.s5l8930x.img3','recoverymode@2x~iphone.s5l8930x.img3','OpeniBoot.ibob.img3','applelogoT.img3']
    full=names+['OpeniBoot.ibob.img3','applelogoT.img3']
    records=[]
    for name in full:
        b=(images/name).read_bytes();elements(b)
        assert struct.unpack_from('<I',b,4)[0]==len(b)
        records.append(dict(name=name,size=len(b),sha256=sha(b),type=struct.pack('>I',struct.unpack_from('<I',b,16)[0]).decode('ascii')))
    info=dict(name='T4_UNTETHERED_OIB_02',status='PREPARED_NOT_FLASHED',ecid=hex(ECID),
        upstream_signing_response=str(ticket_path),llb_personalisation='Apple-issued ECID/SHSH/CERT; encrypted DATA unchanged',
        cpu_loader='Existing RAM-tested post-quiesce loader; no exploit or signature-check changes',
        native_sha256=sha(native),images=records,minimal_order=minimal,full_order=full,
        minimal_bytes=sum((images/n).stat().st_size for n in minimal),full_bytes=sum((images/n).stat().st_size for n in full),
        existing_dra_partition_unchanged=True,device_writes=False,cold_boot_confirmed=False,
        pending=['Verify actual firmware update interface and capacity.','Do not use the old single-image writer.','Hardware cold boot remains unconfirmed.'])
    (OUT/'MANIFEST.json').write_text(json.dumps(info,indent=2)+'\n')
    (OUT/'manifest-minimal.txt').write_text('\n'.join(minimal)+'\n')
    (OUT/'manifest-full.txt').write_text('\n'.join(full)+'\n')
    check_protected();print(json.dumps({k:info[k] for k in ['name','status','minimal_bytes','full_bytes','native_sha256']},indent=2))
if __name__=='__main__':main()
