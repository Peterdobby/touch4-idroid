#!/usr/bin/env python3
"""Offline TOUCH02 RAM overlay; reuse the byte-exact, booted TOUCH01 kernel.

No kernel compilation, device access, or persistent-device storage operations.
"""
import argparse
import copy
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BASE = ROOT / 'saved/build/T4_ANDROID_TOUCH_01'
OLD = HERE.parent / 'android-touch01'
NAME = 'T4_ANDROID_TOUCH_02'
CROSS = os.environ.get('CROSS', str(ROOT / 'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-'))
BASE_MANIFEST_SHA = '31af52b980c4b5fc71827bc2d0552683ebc3a205832b87eda3893bd23e2f722b'
BASE_KERNEL_SHA = '60c3076272e70eed6b5288587406a04285dcf8b6a62f2a9044458c62b307382c'
REPLACE = {'sbin/t4-touch-input', 'sbin/t4-zygote.sh',
           'system/usr/keylayout/t4-ram-keys.kl'}
ADD = {'sbin/t4-ram-power.so'}
KERNEL_FILES = ['zImage', 'zImage.original', 'Image.expected', 'Image.instrumented',
                'vmlinux', 'kernel.config', 'core-addresses.h', 'core-patches.h']
VECTORS = ['t4_zimage_probe', 't4_after_enable', 't4_before_decompress',
           't4_after_decompress', 't4_putstr', 't4_before_kernel', 't4_core_entry',
           't4_processor_ok', 't4_atags_pages', 't4_mmap_switched', 't4_early_c',
           't4_printk_returned', 't4_start_native_console']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def run(command):
    subprocess.run(list(map(str, command)), cwd=ROOT, check=True)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def file_info(path):
    return {'bytes': path.stat().st_size, 'sha256': sha(path)}


def raw_records(data):
    """Keep untouched newc records byte-for-byte, including their metadata."""
    offset = 0
    while data[offset:offset + 6] == b'070701':
        start = offset
        fields = [int(data[offset + 6 + i * 8:offset + 14 + i * 8], 16)
                  for i in range(13)]
        name_bytes = data[offset + 110:offset + 110 + fields[11]]
        require(name_bytes.endswith(b'\0'), 'CPIO name is not terminated')
        name = name_bytes[:-1].decode()
        payload_start = (offset + 110 + fields[11] + 3) & ~3
        offset = (payload_start + fields[6] + 3) & ~3
        require(offset <= len(data), 'Truncated CPIO record: ' + name)
        yield name, fields, data[start:offset]
        if name == 'TRAILER!!!':
            require(not any(data[offset:]), 'Nonzero data beyond CPIO trailer')
            return
    raise RuntimeError('Expected a complete newc CPIO archive')


def record(name, data, fields):
    fields = list(fields)
    fields[6] = len(data)
    fields[11] = len(name.encode()) + 1
    fields[12] = 0
    header = b'070701' + b''.join(f'{n:08x}'.encode() for n in fields)
    header += name.encode() + b'\0'
    return header + bytes(-len(header) % 4) + data + bytes(-len(data) % 4)


def make_initrd(out, original, touch, power):
    sys.path.insert(0, str(ROOT))
    from prepare_android import unpack_cpio
    unpacked = gzip.decompress(original)
    before, files = unpack_cpio(unpacked)
    require(not ADD.intersection(files), 'Power preload already exists in baseline')
    require(REPLACE.issubset(files), 'Expected baseline overlay files are missing')
    zygote = files['sbin/t4-zygote.sh']
    marker = b'exec /system/bin/app_process '
    require(zygote.count(marker) == 1 and b'LD_PRELOAD' not in zygote,
            'Unexpected baseline zygote wrapper')
    zygote = zygote.replace(marker,
        b'export LD_PRELOAD=/sbin/t4-ram-power.so\n'
        b'echo "<5>T4_RAM_DISPLAY_POWER_COMPAT: guarded RAM framebuffer ON fallback"\n'
        + marker, 1)
    overlays = {'sbin/t4-touch-input': touch.read_bytes(),
                'sbin/t4-zygote.sh': zygote,
                'system/usr/keylayout/t4-ram-keys.kl': (HERE / 't4-ram-keys.kl').read_bytes(),
                'sbin/t4-ram-power.so': power.read_bytes()}
    chunks = []
    baseline_records = list(raw_records(unpacked))
    max_inode = max(fields[0] for _, fields, _ in baseline_records)
    for name, fields, raw in baseline_records:
        if name == 'TRAILER!!!':
            fields_new = [max_inode + 1, 0o100755, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0]
            chunks.append(record('sbin/t4-ram-power.so', overlays['sbin/t4-ram-power.so'], fields_new))
            chunks.append(raw)
        elif name in REPLACE:
            require(fields[1] & 0o170000 == 0o100000 and fields[4] == 1,
                    'Overlay must replace a single regular file: ' + name)
            chunks.append(record(name, overlays[name], fields))
        else:
            chunks.append(raw)
    payload = b''.join(chunks)
    after, actual = unpack_cpio(payload)
    require(set(actual) == set(files) | ADD, 'Unexpected CPIO additions/removals')
    require(not any(e['mode'] & 0o170000 == 0o60000 for e in after), 'Block node in CPIO')
    for name, content in files.items():
        if name not in REPLACE:
            require(actual[name] == content, 'Unexpected CPIO content change: ' + name)
    after_records = {n: raw for n, _, raw in raw_records(payload)}
    for name, _, raw in baseline_records:
        if name not in REPLACE:
            require(after_records[name] == raw, 'Unexpected CPIO metadata change: ' + name)
    for name, content in overlays.items():
        require(actual[name] == content, 'Overlay mismatch: ' + name)
    compressed = gzip.compress(payload, compresslevel=9, mtime=0)
    require(len(compressed) < 0x03800000, 'Initrd exceeds established RAM upload limit')
    (out / 'initramfs.cpio.gz').write_bytes(compressed)
    (out / 't4-zygote.sh').write_bytes(zygote)
    (out / 't4-ram-keys.kl').write_bytes(overlays['system/usr/keylayout/t4-ram-keys.kl'])
    report = {'base_variant': 'T4_ANDROID_TOUCH_01',
              'base_initramfs_sha256': hashlib.sha256(original).hexdigest(),
              'unchanged_records_byte_exact': len(files) - len(REPLACE),
              'unchanged_init_rc': actual['init.rc'] == files['init.rc'],
              'unchanged_touch_start_script': actual['sbin/t4-touch-start.sh'] == files['sbin/t4-touch-start.sh'],
              'block_device_nodes': 0,
              'cpio_unpacked_bytes': len(payload), 'cpio_compressed_bytes': len(compressed),
              'changed': {n: {'before_sha256': hashlib.sha256(files[n]).hexdigest(),
                              'after_sha256': hashlib.sha256(actual[n]).hexdigest()}
                          for n in sorted(REPLACE)},
              'added': {n: {'sha256': hashlib.sha256(actual[n]).hexdigest(),
                            'bytes': len(actual[n])} for n in sorted(ADD)}}
    write_json(out / 'cpio-overlay-validation.json', report)
    return compressed, report


def symbols(path):
    text = subprocess.check_output([CROSS + 'nm', str(path)], text=True)
    return {parts[2]: int(parts[0], 16) for line in text.splitlines()
            if len(parts := line.split()) == 3}


def compile_handoff(out, variant, stem):
    elf_path = out / (stem + '.elf')
    run([CROSS + 'gcc', '-nostdlib', '-fno-use-linker-plugin', '-mcpu=cortex-a8',
         '-mthumb', '-Os', '-fno-builtin', '-fno-unwind-tables',
         '-fno-asynchronous-unwind-tables', '-Wl,-T,' + str(OLD / 'handoff.ld'),
         '-Wl,-N', '-Wl,--build-id=none', '-Wl,-e,t4_linux_stage',
         '-DT4_TEST_NAME="' + variant + '"', '-DT4_EXTRA_ARGS=" slub_debug=FZPU noalign"',
         '-I' + str(out), '-I' + str(ROOT / 'saved/sources/iDroid-kernel-T4_ANDROID_TOUCH_01/arch/arm/mach-s5l8930/include'),
         OLD / 'entry.S', OLD / 'handoff.c', '-o', elf_path])
    elf = elf_path.read_bytes()
    require(elf[:7] == b'\x7fELF\x01\x01\x01', 'Unexpected handoff ELF ABI')
    ph = struct.unpack_from('<I', elf, 28)[0]
    ps, pn = struct.unpack_from('<HH', elf, 42)
    segs = [struct.unpack_from('<8I', elf, ph + i * ps) for i in range(pn)]
    segs = [seg for seg in segs if seg[0] == 1 and seg[5]]
    require(segs and min(seg[2] for seg in segs) == 0x44000000, 'Unexpected helper load address')
    image = bytearray(max(seg[2] + seg[5] for seg in segs) - 0x44000000)
    require(len(image) <= 0x8000, 'Helper exceeds reserved area')
    for seg in segs:
        require(seg[4] <= seg[5] and seg[1] + seg[4] <= len(elf), 'Invalid ELF load segment')
        at = seg[2] - 0x44000000
        image[at:at + seg[4]] = elf[seg[1]:seg[1] + seg[4]]
    syms = symbols(elf_path)
    for i, name in enumerate(VECTORS):
        require(syms[name] == 0x44000000 + i * 4, 'Handoff vector moved: ' + name)
    require(not subprocess.check_output([CROSS + 'nm', '-u', str(elf_path)], text=True).strip(),
            'Handoff has unresolved references')
    entry = struct.unpack_from('<I', elf, 24)[0]
    require(entry == syms['t4_linux_stage'] | 1, 'Unexpected ELF entry point')
    entries = {name: syms[name] | 1 for name in ['t4_linux_stage', 't4_linux_start']}
    require(all(0x44000000 <= addr < 0x44000000 + len(image) and addr & 1
                for addr in entries.values()), 'Invalid handoff entries')
    (out / (stem + '.bin')).write_bytes(image)
    return bytes(image), entries


def main(out):
    out = out.resolve()
    for protected_dir in [BASE, ROOT / 'saved/build/T4_ANDROID_ADB_01', ROOT / 'saved/build/phase1-published']:
        require(out != protected_dir and protected_dir not in out.parents and out not in protected_dir.parents,
                'Output must not overlap a protected baseline: ' + str(protected_dir))
    require(ROOT / 'saved/build' in out.parents, 'Output must be a distinct directory beneath build/')
    if (out / 'manifest.json').exists():
        require(json.loads((out / 'manifest.json').read_text()).get('variant') == NAME,
                'Refusing to overwrite another build variant')
    require(sha(BASE / 'manifest.json') == BASE_MANIFEST_SHA, 'TOUCH01 manifest changed; inspect before rebuilding')
    base = json.loads((BASE / 'manifest.json').read_text())
    require(base['variant'] == 'T4_ANDROID_TOUCH_01', 'Wrong baseline variant')
    require(sha(BASE / 'zImage') == BASE_KERNEL_SHA, 'Wrong booted TOUCH01 kernel')
    for name, meta in base['files'].items():
        require(file_info(BASE / name) == meta, 'Baseline artifact differs from manifest: ' + name)
    # All TOUCH01 files (including helpers), published OIB, and ADB01 are read-only.
    protected = {str(p): sha(p) for p in BASE.rglob('*') if p.is_file()}
    for name in ['openiboot.bin', 'openiboot-native.bin']:
        p = ROOT / 'saved/build/phase1-published' / name
        require(sha(p) == base['protected_baselines'][str(p)], 'Published OIB changed: ' + name)
        protected[str(p)] = sha(p)
    adb = ROOT / 'saved/build/T4_ANDROID_ADB_01'
    adb_manifest = json.loads((adb / 'manifest.json').read_text())
    for name in ['manifest.json', *adb_manifest['files']]:
        p = adb / name
        if str(p) in base['protected_baselines']:
            require(sha(p) == base['protected_baselines'][str(p)], 'ADB01 baseline changed: ' + name)
        protected[str(p)] = sha(p)
    source_paths = [Path(__file__), HERE / 't4-ram-keys.kl',
                    ROOT / 'tools/build-t4-touch-input.py', ROOT / 'tools/build-t4-ram-power.py']
    source_paths += [OLD / n for n in ['entry.S', 'handoff.c', 'handoff.ld', 'usb.c',
                                       'crc32-table.h', 'diag_maps.h', 'atags.h']]
    source_paths += [HERE.parent / n for n in ['cmdline.h', 'test_cmdline.c']]
    source_paths += [ROOT / 'saved/sources/iDroid-kernel-T4_ANDROID_TOUCH_01/arch/arm/mach-s5l8930/include/mach/t4_ramfont.h']
    source_sha = {str(p.relative_to(ROOT)): sha(p) for p in source_paths}
    out.mkdir(parents=True, exist_ok=True)
    # Copy all manifest artifacts except the files rebuilt below.
    rebuilt = {'t4-touch-input', 'touch-integration.json', 'initramfs.cpio.gz',
               'handoff.bin', 'handoff.elf', 'linux-usb', 'upload-protocol.json'}
    for name in base['files']:
        if name not in rebuilt:
            shutil.copy2(BASE / name, out / name)
    shutil.copy2(BASE / 'sizes.h', out / 'sizes.h')
    check, _ = compile_handoff(out, 'T4_ANDROID_TOUCH_01', 'handoff-baseline-check')
    require(check == (BASE / 'handoff.bin').read_bytes(),
            'Current toolchain/handoff source does not reproduce the booted TOUCH01 helper')
    touch = module('touch02_service', ROOT / 'tools/build-t4-touch-input.py').build(out)
    power = module('touch02_power', ROOT / 'tools/build-t4-ram-power.py').build(out)
    packed, report = make_initrd(out, (BASE / 'initramfs.cpio.gz').read_bytes(), touch, power)
    old_sizes = (BASE / 'sizes.h').read_text().splitlines()
    updates = {'INITRD_SIZE': len(packed), 'INITRD_CRC': zlib.crc32(packed),
               'INITRD_UNPACKED_SIZE': report['cpio_unpacked_bytes']}
    seen = set()
    new_sizes = []
    for line in old_sizes:
        parts = line.split()
        if len(parts) == 3 and parts[:1] == ['#define'] and parts[1] in updates:
            seen.add(parts[1])
            line = '#define ' + parts[1] + ' ' + str(updates[parts[1]]) + 'u'
        new_sizes.append(line)
    require(seen == set(updates), 'Missing baseline INITRD size/CRC definitions')
    require(struct.unpack_from('<I', packed, len(packed) - 4)[0] == updates['INITRD_UNPACKED_SIZE'],
            'Gzip unpacked size mismatch')
    (out / 'sizes.h').write_text('\n'.join(new_sizes) + '\n')
    _, entries = compile_handoff(out, NAME, 'handoff')
    define = '-DT4_TEST_NAME="' + NAME + '"'
    extra = '-DT4_EXTRA_ARGS=" slub_debug=FZPU noalign"'
    usb = ROOT / 'saved/research/libusb-1.0.29'
    run(['cc', '-Wall', '-Wextra', '-Werror', define, extra, OLD / 'usb.c',
         '-o', out / 'linux-usb', '-I' + str(usb / 'libusb'),
         usb / 'libusb/.libs/libusb-1.0.a', '-framework', 'IOKit',
         '-framework', 'CoreFoundation', '-framework', 'Security'])
    run(['cc', '-Wall', '-Wextra', '-Werror', define, extra,
         HERE.parent / 'test_cmdline.c', '-o', out / 'test-cmdline'])
    (out / 'cmdline-test.log').write_bytes(subprocess.check_output([str(out / 'test-cmdline')]))
    (out / 'handoff.disasm').write_bytes(subprocess.check_output([CROSS + 'objdump', '-d', str(out / 'handoff.elf')]))
    protocol = json.loads((BASE / 'upload-protocol.json').read_text())
    require(protocol['host_source_sha256'] == sha(OLD / 'usb.c'), 'Upload source differs from verified protocol')
    write_json(out / 'upload-protocol.json', protocol)
    for name in KERNEL_FILES:
        require(sha(out / name) == sha(BASE / name), 'Kernel artifact changed: ' + name)
    for path, digest in protected.items():
        require(sha(path) == digest, 'Protected baseline changed during build: ' + path)
    require(source_sha == {str(p.relative_to(ROOT)): sha(p) for p in source_paths},
            'Build source changed during compilation')
    manifest = copy.deepcopy(base)
    manifest.update(variant=NAME, status='built offline; fresh DFU RAM boot and sustained touch/button verification pending',
        repair='TOUCH01 kernel byte-exact. Userspace only: IRQ-ready touch polling, FIFO50, ARM sigreturn119, checked uinput writes; guarded RAM display ON compatibility; physical button layout.',
        success='Live TOUCH01 RAM overlay briefly operated the desktop; user later reported stalled touch. Fresh TOUCH02 boot is not yet verified.',
        entries=entries, protected_baselines=protected,
        baseline_variant='T4_ANDROID_TOUCH_01', baseline_manifest_sha256=BASE_MANIFEST_SHA,
        kernel_recompiled=False, kernel_outputs_byte_exact=KERNEL_FILES,
        handoff_baseline_reproduction_exact=True, cpio_overlay=report,
        build_source_sha256=source_sha, device_access=False)
    info = json.loads((out / 'android-input.json').read_text())
    info.update(base_initramfs_variant='T4_ANDROID_TOUCH_01',
                base_initramfs_sha256=base['files']['initramfs.cpio.gz']['sha256'],
                root_overlays=sorted(REPLACE | ADD),
                touch='Real N1 frames; IRQ-ready polling and FIFO50; sustained hardware verification pending',
                cpio_unpacked_bytes=report['cpio_unpacked_bytes'], cpio_compressed_bytes=len(packed))
    write_json(out / 'android-input.json', info)
    files = set(base['files']) | {'sizes.h', 'ram-power-build.json', 'ram-power-exports.map',
        't4-ram-power.so', 't4-zygote.sh', 't4-ram-keys.kl', 'cpio-overlay-validation.json',
        'test-cmdline', 'cmdline-test.log', 'handoff.disasm', 'handoff-baseline-check.bin',
        'handoff-baseline-check.elf', 't4-touch-raw.c', 't4-touch-uinput.h',
        't4-n1-device-cal.h', 't4-pmu-clock15.h', 'working-ios-inputs.S'}
    manifest['files'] = {name: file_info(out / name) for name in sorted(files)}
    write_json(out / 'manifest.json', manifest)
    print('Built', out)
    print('TOUCH01_HANDOFF_REPRODUCTION_EXACT')
    print('TOUCH01_KERNEL_BYTE_EXACT; allowed CPIO overlays only; protected baselines unchanged')
    print('No device access. Fresh DFU RAM boot / sustained desktop input verification pending.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'saved/build' / NAME)
    args = parser.parse_args()
    main(args.out)
