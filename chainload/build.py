#!/usr/bin/env python3
"""Build only the standalone RAM chainloader and external RAM test fixture."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import struct
import subprocess
import zlib

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'chainload'
OUT = ROOT / 'saved/build/chainload'
CROSS = str(ROOT / 'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-')
PINS = {
    'saved/build/phase1-published/openiboot-native.bin': '890de9dbf62a25226049d43d3265020f8fa97ae8035264a5a7c4ec67304b1715',
    'saved/build/phase1-published/openiboot.bin': 'cd32dbac3d10a81b64226ffa4057fa8e202e699e3ff2182a7560eea077d5fbe1',
    'saved/build/iBSS.n81ap.go.dfu': 'e8b10d73a72fbca026161bd4d4f169992092d8c0eed022540c8072bb5f5ddfcc',
    'saved/build/iBSS.n81ap.raw': 'bd61d56a154d1fb70318677ee233d63e3798ed1826dcf5421457ac4764757d9a',
    'phase1/run.py': 'd440400f3258859ddef349d56ffbf6344c3a94c8c500c895401aed3739092d80',
    'phase1/load.c': 'c2e31e89f1004d78a581b0dcee9ad3bc6a7528adc0742f3f166af5dc85887442',
    'phase1/native_jump.S': '96e796863ab17b7b33dea16d0cd0412bea52cbf1f270670735cbb2eca8b403b0',
    'saved/build/T4_ANDROID_TOUCH_03/manifest.json': 'a975793156f6fc194d6a864f75ba0cba2c46ba3325ef684e4bbb5708f42eadf7',
    'saved/build/T4_ANDROID_TOUCH_03/zImage': '60c3076272e70eed6b5288587406a04285dcf8b6a62f2a9044458c62b307382c',
    'saved/build/T4_ANDROID_TOUCH_03/initramfs.cpio.gz': '51c38a785b78969823aec87ccd065755b86b11e3acd8095d89a3208c40f83d4d',
    'saved/build/T4_ANDROID_TOUCH_03/handoff.bin': 'abe202a424c94465d458b68dbe5d960643d2aa826d1684f493557464f6156c51',
    'saved/build/T4_ANDROID_TOUCH_03/t4-touch-input': '2ad676c57ca2b8336b005a039c1145967a9185509bdb28653a0d9269d5ea8862',
}
ARCHIVE = ROOT.parent / 'project-archives/touch4-idroid-TOUCH03-known-good-20261023'
ARCHIVE_SHA = '288ba75a456e8f48ea27bbfe5ff72815c9a205f255690548db74275b949a4fc7'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')

def run(command, **kwargs):
    return subprocess.run([str(x) for x in command], check=True, **kwargs)

def symbols(elf):
    result = subprocess.check_output([CROSS+'nm', '-n', str(elf)], text=True)
    return {parts[2]: int(parts[0], 16) for line in result.splitlines()
            if len(parts := line.split()) == 3}

def check_protected():
    for name, expected in PINS.items():
        actual = sha((ROOT / name).read_bytes())
        if actual != expected:
            raise SystemExit('Protected baseline changed: ' + name)

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    check_protected()
    archived = {}
    for name, expected in PINS.items():
        p = ARCHIVE / name
        archived[name] = {'sha256': sha(p.read_bytes()), 'write_bits': p.stat().st_mode & 0o222}
        assert archived[name]['sha256'] == expected and archived[name]['write_bits'] == 0, name
    manifest_gz = Path(str(ARCHIVE) + '.manifest.jsonl.gz')
    assert sha(manifest_gz.read_bytes()) == ARCHIVE_SHA
    verification = json.loads(Path(str(ARCHIVE) + '.verification.json').read_text())
    assert verification['byte_for_byte_verified'] and not verification['errors']
    write_json(OUT / 'known-good-archive.json', {
        'archive': str(ARCHIVE), 'prior_full_verification': verification,
        'this_build_manifest_sha256': ARCHIVE_SHA,
        'this_build_critical_file_checks': archived,
        'note': 'Full archive was verified when created; this build rechecks manifest and 12 critical files.'})

    native = (ROOT / 'saved/build/phase1-published/openiboot-native.bin').read_bytes()
    raw = (ROOT / 'saved/build/phase1-published/openiboot.bin').read_bytes()
    assert native[0x1000:0x1000+len(raw)] == raw
    assert len(native) == 0x45000 and len(raw) == 0x437a0
    expected_wrapper = struct.pack('<7I', 0xe3a00000, 0xe59f1008, 0xe3a02000,
                                   0xe59f3004, 0xe12fff13, 0x41001000, 0x8401496d)
    assert native[:0x1000] == (expected_wrapper + bytes.fromhex('00f020e3')*9).ljust(0x1000, b'\0')
    (OUT / 'openiboot-native.bin').write_bytes(native)

    def compile_image(stem, source, linker, defines=()):
        run([CROSS+'gcc', '-c', '-mcpu=cortex-a8', '-marm', *defines,
             '-o', OUT/(stem+'.o'), SRC/source], cwd=OUT)
        run([CROSS+'ld', '--build-id=none', '-T', SRC/linker,
             '-o', OUT/(stem+'.elf'), OUT/(stem+'.o')])
        run([CROSS+'objcopy', '-O', 'binary', OUT/(stem+'.elf'), OUT/(stem+'.bin')])
        dis = subprocess.check_output([CROSS+'objdump', '-d', str(OUT/(stem+'.elf'))], text=True)
        (OUT/(stem+'.disasm')).write_text(dis)
        return symbols(OUT/(stem+'.elf'))

    loader_symbols = compile_image('t4-oib-loader', 'entry.S', 'loader.ld')
    loader = (OUT / 't4-oib-loader.bin').read_bytes()
    assert loader == struct.pack('<3I', 0xe59fc000, 0xe12fff1c, 0x41000000)
    assert loader_symbols['_start'] == 0x44000000
    ibss_raw = (ROOT / 'saved/build/iBSS.n81ap.raw').read_bytes()
    jump_words = struct.unpack_from('<4I', ibss_raw, 0x1496c)
    defines = ['-DNATIVE_IMAGE_SIZE='+str(len(native)), '-DLOADER_IMAGE_SIZE='+str(len(loader))]
    defines += [f'-DIBSS_JUMP_WORD{i}=0x{word:08x}' for i, word in enumerate(jump_words)]
    fixture_symbols = compile_image('t4-oib-ram-fixture', 'ram-fixture.S', 'fixture.ld', defines)
    fixture = (OUT / 't4-oib-ram-fixture.bin').read_bytes()
    native_offset = fixture_symbols['native_image'] - 0x41000000
    loader_offset = fixture_symbols['loader_image'] - 0x41000000
    assert native_offset == 0x1000
    assert fixture[native_offset:native_offset+len(native)] == native
    assert fixture[loader_offset:loader_offset+len(loader)] == loader
    assert fixture_symbols['relocated_end'] < 0x41001000

    ibss = (ROOT / 'saved/build/iBSS.n81ap.go.dfu').read_bytes()
    (OUT/'inputs.h').write_text(
        f'#define IBSS_SIZE {len(ibss)}UL\n#define IBSS_CRC 0x{zlib.crc32(ibss):08x}U\n'
        f'#define FIXTURE_SIZE {len(fixture)}UL\n#define FIXTURE_CRC 0x{zlib.crc32(fixture):08x}U\n')
    flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'libirecovery-1.0'], text=True))
    cc = os.environ.get('CC', 'cc')
    run([cc, '-O2', '-Wall', '-Wextra', '-Werror', '-I', OUT, SRC/'controlled-ram.c',
         *flags, '-o', OUT/'controlled-ram'])
    run([cc, '-O2', '-Wall', '-Wextra', '-Werror',
         '-I', ROOT/'saved/research/libusb-1.0.29/libusb', SRC/'acm-version.c',
         ROOT/'saved/research/libusb-1.0.29/libusb/.libs/libusb-1.0.a',
         '-framework', 'IOKit', '-framework', 'CoreFoundation', '-framework', 'Security',
         '-o', OUT/'acm-version'])

    files = {str(p.relative_to(ROOT)): {'size': p.stat().st_size, 'sha256': sha(p.read_bytes())}
             for p in sorted(OUT.iterdir()) if p.is_file() and p.suffix in ('.bin', '.elf', '.disasm')}
    for p in (OUT/'controlled-ram', OUT/'acm-version', OUT/'known-good-archive.json'):
        files[str(p.relative_to(ROOT))] = {'size': p.stat().st_size, 'sha256': sha(p.read_bytes())}
    source_files = {str(p.relative_to(ROOT)): sha(p.read_bytes())
                    for p in sorted(SRC.iterdir()) if p.is_file() and p.suffix in ('.S', '.ld', '.py', '.c')}
    write_json(OUT/'manifest.json', {
        'name': 'T4_OIB_CHAINLOAD_01', 'protected_inputs': PINS,
        'files': files, 'sources': source_files,
        'loader_entry': '0x44000000 (ARM)', 'native_entry': '0x41000000 (ARM)',
        'payload_entry': '0x41001000 (ARM)', 'ibss_jump_to': '0x8401496d (Thumb)',
        'image': {'size': len(native), 'sha256': sha(native), 'payload_offset': 4096,
                  'raw_size': len(raw), 'raw_sha256': sha(raw), 'tail_padding': len(native)-4096-len(raw)},
        'symbols': {'loader': loader_symbols, 'fixture': fixture_symbols},
        'hardware_success': False,
        'hardware_note': 'Only a new USB enumeration and fresh ACM version round trip may confirm success.'})
    check_protected()
    print(f'Built: {OUT / "t4-oib-loader.bin"} ({len(loader)} bytes)')
    print(f'Native image unchanged: {sha(native)}')
    print(f'External RAM placement fixture: {len(fixture)} bytes')
    print('PROTECTED_ANDROID_AND_PHASE1_UNCHANGED')

if __name__ == '__main__':
    main()
