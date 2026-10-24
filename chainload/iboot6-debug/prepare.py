#!/usr/bin/env python3
"""Prepare an UNTESTED RAM-debug dispatch candidate on the Mac only.

Not an installer or boot command. No exploit/signature/NVRAM modifications.
"""
import hashlib,json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'saved/build/iboot6-ram-debug'
sys.path.insert(0,str(ROOT/'chainload'))
from build import check_protected
def sha(data):return hashlib.sha256(data).hexdigest()
def main():
    check_protected()
    source=ROOT.parent/'touch4-idroid-untethered/build/untethered/T4_OIB_LOADER_01/iBoot.n81ap-10B500.raw'
    original=source.read_bytes()
    assert sha(original)=='d167d3303354296121da953ba8df62755f902932fccb8fdb29232bba1d057bda'
    name,handler=struct.unpack_from('<II',original,0x42000)
    assert handler==0x5ff00ae5
    assert original[name-0x5ff00000:name-0x5ff00000+7]==b'fsboot\0'
    candidate=bytearray(original)
    struct.pack_into('<I',candidate,0x42004,0x44000000)
    changed=[i for i,(before,after) in enumerate(zip(original,candidate)) if before!=after]
    assert changed==list(range(0x42004,0x42008))
    # Excluding the one dispatch word, every source byte is preserved.
    assert candidate[:0x42004]==original[:0x42004]
    assert candidate[0x42008:]==original[0x42008:]
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/'iBoot6-fsboot-debug-CANDIDATE.raw'
    path.write_bytes(candidate)
    loader=ROOT/'saved/build/chainload-live-iboot6/t4-oib-live-iboot6.bin'
    report=dict(status='STATIC_CANDIDATE_ONLY_NOT_HARDWARE_APPROVED',
        source=str(source),source_sha256=sha(original),candidate_sha256=sha(candidate),
        candidate=str(path),size=len(candidate),
        change=dict(file_offset='0x42004',old_handler='0x5ff00ae5 Thumb',
                    new_handler='0x44000000 ARM',changed_byte_offsets=[hex(i) for i in changed]),
        loader=dict(path=str(loader),sha256=sha(loader.read_bytes())),
        all_other_firmware_bytes_unchanged=True,
        signature_code_and_certificate_bytes_unchanged=True,
        exploit_sources_untouched=True,device_access_performed=False,
        nvram_or_storage_commands_sent=False,
        blockers=[
            'Prove automatic startup actually dispatches through this fsboot table entry.',
            'Audit preceding initialization for NAND/NOR/NVRAM writes before any hardware launch.',
            'Verify full iBoot6 RAM relocation, aliases, entry ABI and initialized-state requirements.',
            'Provide controlled RAM-only staging of firmware and loader without changing signature checks.'
        ],
        note='Changing this dispatch word alone does not provide an iBoot6 debugger or a working RAM launch path.')
    (OUT/'ASSESSMENT.json').write_text(json.dumps(report,indent=2)+'\n')
    check_protected()
    print('Prepared offline candidate:',path)
    print('Changed exactly 4 bytes at file offset 0x42004; all other firmware bytes identical.')
    print('NOT a verified debug image or bootable test workflow. See ASSESSMENT.json blockers.')
if __name__=='__main__':main()
