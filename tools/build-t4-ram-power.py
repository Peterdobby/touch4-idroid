#!/usr/bin/env python3
"""Build and validate the guarded Gingerbread RAM-display preload. Offline only."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'linux-ramtest/android-touch01'
SOURCE = HERE / 'ram-power-compat.c'
HEADER = HERE / 't4-gb-api.h'
TOOLCHAIN = ROOT / 'saved/toolchain/arm-eabi-4.8/bin'
SYSTEM_LIB = ROOT / 'saved/build/android-prepared/system-root/lib'
GCC = TOOLCHAIN / 'arm-eabi-gcc'
READELF = TOOLCHAIN / 'arm-eabi-readelf'
NM = TOOLCHAIN / 'arm-eabi-nm'
EXPECTED_NEEDED = {'libc.so', 'libdl.so'}
EXPECTED_IMPORTS = {'__errno', 'access', 'close', 'dlclose', 'dlopen', 'dlsym', 'open', 'read'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def output(command):
    return subprocess.check_output(list(map(str, command)), cwd=ROOT, text=True)


def symbols(path, defined):
    flag = '--defined-only' if defined else '--undefined-only'
    return {line.split()[-1].split('@', 1)[0]
            for line in output([NM, '-D', flag, path]).splitlines() if line.split()}


def validate(path):
    header = output([READELF, '-h', path])
    for pattern in [r'Class:\s+ELF32', r'Type:\s+DYN\b', r'Machine:\s+ARM\b']:
        if not re.search(pattern, header):
            raise RuntimeError('Unexpected ELF ABI: ' + pattern)
    dynamic = output([READELF, '-d', path])
    needed = re.findall(r'\(NEEDED\).*\[([^]]+)\]', dynamic)
    if set(needed) != EXPECTED_NEEDED or len(needed) != len(EXPECTED_NEEDED):
        raise RuntimeError('Unexpected DT_NEEDED: ' + repr(needed))
    if not re.search(r'\(HASH\)', dynamic) or re.search(r'\(GNU_HASH\)', dynamic):
        raise RuntimeError('Gingerbread requires the SysV symbol hash')
    if not re.search(r'\(SONAME\).*\[t4-ram-power\.so\]', dynamic):
        raise RuntimeError('Unexpected library SONAME')
    constructor_size = re.search(r'\(INIT_ARRAYSZ\)\s+(\d+)\s+\(bytes\)', dynamic)
    if not re.search(r'\(INIT_ARRAY\)', dynamic) or not constructor_size or int(constructor_size[1]) < 4:
        raise RuntimeError('Missing boot-verification constructor')
    exports = symbols(path, True)
    if exports != {'set_screen_state'}:
        raise RuntimeError('Unexpected defined dynamic exports: ' + repr(sorted(exports)))
    imports = symbols(path, False)
    if imports != EXPECTED_IMPORTS:
        raise RuntimeError('Unexpected dynamic imports: ' + repr(sorted(imports)))
    available = set()
    for library in sorted(EXPECTED_NEEDED):
        available.update(symbols(SYSTEM_LIB / library, True))
    if imports - available:
        raise RuntimeError('Imports absent from shipped Bionic libraries: ' + repr(sorted(imports - available)))
    return {'elf_class': 'ELF32', 'machine': 'ARM', 'type': 'DYN',
            'needed': needed, 'hash_style': 'sysv', 'constructor_bytes': int(constructor_size[1]),
            'defined_exports': sorted(exports), 'undefined_imports': sorted(imports),
            'imports_available_in_shipped_libraries': True}


def build(out):
    out = Path(out).resolve()
    inputs = [SOURCE, HEADER, SYSTEM_LIB / 'libc.so', SYSTEM_LIB / 'libdl.so']
    for path in [GCC, READELF, NM] + inputs:
        if not path.is_file():
            raise FileNotFoundError('Required local build input missing: ' + str(path))
    input_hashes = {str(path.relative_to(ROOT)): sha(path) for path in inputs}
    out.mkdir(parents=True, exist_ok=True)
    export_map = out / 'ram-power-exports.map'
    export_map.write_text('{ global: set_screen_state; local: *; };\n')
    library = out / 't4-ram-power.so'
    command = [GCC, '-nostdlib', '-shared', '-fPIC', '-fno-use-linker-plugin',
               '-mcpu=cortex-a8', '-marm', '-Os', '-fno-builtin', '-fno-stack-protector',
               '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
               '-Wall', '-Wextra', '-Werror', '-DT4_GB_ABI',
               '-Wl,--build-id=none', '-Wl,--hash-style=sysv', '-Wl,-soname,t4-ram-power.so',
               '-Wl,--version-script=' + str(export_map),
               '-Wl,-rpath-link,' + str(SYSTEM_LIB),
               SOURCE, '-L' + str(SYSTEM_LIB), '-ldl', '-lc', '-o', library]
    subprocess.run(list(map(str, command)), cwd=ROOT, check=True)
    checks = validate(library)
    if input_hashes != {str(path.relative_to(ROOT)): sha(path) for path in inputs}:
        raise RuntimeError('Build inputs changed during compilation')
    metadata = {'library': str(library), 'sha256': sha(library),
                'build_command': list(map(str, command)), 'input_sha256': input_hashes,
                'compiler': output([GCC, '--version']).splitlines()[0],
                'compiler_sha256': sha(GCC), 'exports_map': export_map.read_text(),
                'validation': checks,
                'scope': 'Exact TOUCH01/TOUCH02/TOUCH03 RAM display; original backend called first; guarded ON fallback only',
                'device_access': False}
    (out / 'ram-power-build.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print('Built guarded RAM-display power preload:', library)
    return library


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'saved/build/T4_TOUCH_INPUT_02')
    args = parser.parse_args()
    build(args.out)
