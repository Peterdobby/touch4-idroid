#!/usr/bin/env python3
"""T4_TOUCH_CLOCK_15: reproduce the native iOS N1 PMU GPIO0 clock-enable function with restoration.

Uses the unchanged T4_ANDROID_ADB_01 kernel and ADB. Registers no input device.
Requires /data on tmpfs and an unregistered SPI bus. Restores saved SPI/GPIO
state after the bounded diagnostic. Only PMU GPIO0 register0x50 is changed and restored; no voltage/USB/IRQ writes.
"""
import argparse
import datetime
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('touch_diag', ROOT / 'tools/t4-touch-diag.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
OUT = ROOT / 'saved/build/T4_TOUCH_CLOCK_15'
INPUTS = ROOT / 'saved/research/touch-bringup/ios-working-n1-inputs'
EXPECTED = {
    'zephyr2.bin': (57880, '359b6154c8aaffb22eb6e9350be7c718be0bf00fbddbac257e9d10582e62428f'),
    'MtCl.bin': (1024, '7d96476816fbbcb0a3114c96940a9b91fb1f5e733bdf2b8b67d6e7e53129d1e8'),
}


def protected_hashes():
    files = [ROOT / 'saved/build/T4_ANDROID_ADB_01' / name
             for name in ['manifest.json', 'zImage', 'handoff.bin', 'initramfs.cpio.gz']]
    files += [ROOT / 'saved/build/phase1-published' / name
              for name in ['openiboot.bin', 'openiboot-native.bin']]
    return {str(f.relative_to(ROOT)): base.sha(f) for f in files}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-only', action='store_true')
    parser.add_argument('--probe-seconds', type=int, default=30, choices=range(1, 61), metavar='1..60')
    parser.add_argument('--interface-only', action='store_true', help='stop after validated E2/family/D3, no finger window')
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    before = protected_hashes()
    for name, (size, checksum) in EXPECTED.items():
        path = INPUTS / name
        if not path.is_file() or path.stat().st_size != size or base.sha(path) != checksum:
            raise RuntimeError('Verified working-iOS input missing/changed: ' + str(path))
    asm = OUT / 'working-ios-inputs.S'
    assembly = ['.section .rodata']
    for name, symbol in [('zephyr2.bin', 'n81_fw'), ('MtCl.bin', 'n81_device_cal')]:
        assembly += ['.global ' + symbol + ',' + symbol + '_end', symbol + ':',
                     '.incbin "' + str(INPUTS / name) + '"', symbol + '_end:']
    assembly += ['.section .note.GNU-stack,"",%progbits', '']
    asm.write_text('\n'.join(assembly))
    (OUT / 't4-touch-raw.c').write_bytes((base.HERE / 't4-touch-clock15.c').read_bytes())
    (OUT / 't4-n1-device-cal.h').write_bytes((base.HERE / 't4-n1-clock15.h').read_bytes())
    (OUT / 't4-pmu-clock15.h').write_bytes((base.HERE / 't4-pmu-clock15.h').read_bytes())
    exe = OUT / ('t4-touch-clock15-interface' if args.interface_only else 't4-touch-clock15')
    command = [base.CROSS, '-nostdlib', '-static', '-fno-use-linker-plugin',
               '-mcpu=cortex-a8', '-marm', '-Os', '-fno-builtin', '-Wl,-e,_start',
               '-DT4_RESET_PROBE', '-DT4_FIRMWARE_PROBE', '-DT4_RESET_HIZ',
               '-DT4_RESET_CLOCK_HIGH', '-DT4_SPI_BASE=0x4038', '-DT4_RT',
               '-DT4_FW_DIV=5', '-DT4_ACK_DIV=3', '-DT4_FW_SIZE=57880', '-DT4_CAL_PROBE',
               '-DT4_DEVICE_CAL_PROBE', OUT / 't4-touch-raw.c', asm, '-lgcc', '-o', exe]
    command.insert(1, '-DT4_FRAME_WINDOW_MS=' + str(args.probe_seconds * 1000))
    if args.interface_only:
        command.insert(1, '-DT4_INTERFACE_ONLY')
    base.run(command)
    manifest = {'variant': 'T4_TOUCH_CLOCK_15', 'inputs': EXPECTED,
                'program': str(exe), 'program_sha256': base.sha(exe),
                'build_command': list(map(str, command)), 'protected': before,
                'spi_setup_cycles': 500, 'probe_seconds': args.probe_seconds,
                'source_sha256': {n: base.sha(base.HERE / n)
                                  for n in ['t4-touch-clock15.c', 't4-n1-clock15.h', 't4-pmu-clock15.h']},
                'hardware_status': 'UNTESTED: host build only; real finger frames required'}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Built:', exe, flush=True)
    if protected_hashes() != before:
        raise RuntimeError('Protected baseline changed during build')
    if args.build_only:
        print('BUILD_ONLY; no device access')
        return 0
    check = base.adb('shell', 'id; uname -r; cat /proc/mounts; '
                     'echo T4_SPI_BEGIN; ls /sys/bus/spi/devices; echo T4_SPI_END; '
                     'echo T4_I2C_BEGIN; if [ -d /sys/bus/i2c/devices ]; then ls /sys/bus/i2c/devices; '
                     'elif [ ! -d /sys/bus/i2c ]; then echo T4_I2C_BUS_ABSENT; else echo T4_I2C_UNKNOWN; fi; echo T4_I2C_END')
    if 'uid=0(root)' not in check or '3.0.8' not in check:
        raise RuntimeError('Boot existing T4_ANDROID_ADB_01 with root ADB first')
    if not any(' /data tmpfs ' in line for line in check.splitlines()):
        raise RuntimeError('Refuse: /data is not confirmed tmpfs')
    if check.split('T4_SPI_BEGIN\n', 1)[-1].split('T4_SPI_END', 1)[0].strip():
        raise RuntimeError('Refuse: SPI device list nonempty or unconfirmed')
    if check.split('T4_I2C_BEGIN\n', 1)[-1].split('T4_I2C_END', 1)[0].strip() not in ('', 'T4_I2C_BUS_ABSENT'):
        raise RuntimeError('Refuse: Linux I2C adapter/device list nonempty or unconfirmed')
    destination = '/data/local/tmp/' + exe.name
    base.adb('push', exe, destination)
    base.adb('shell', 'chmod 700 ' + destination)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    log = OUT / ('hardware-' + stamp + '.log')
    print('Log:', log, flush=True)
    print('Interface-only probe; no finger interaction needed.' if args.interface_only else
          'When FRAME_READY appears, move a finger across the screen for ' + str(args.probe_seconds) + ' seconds.', flush=True)
    # The remote program has bounded transfers and a 30-second frame window.
    # Stream stdout so the user sees FRAME_READY before that window ends.
    with log.open('x') as stream:
        stream.write(check + '\n')
        process = subprocess.Popen([str(base.ADB), '-s', base.SERIAL, 'shell', destination],
                                   cwd=ROOT, env=base.ENV, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True)
        chunks = []
        for line in process.stdout:
            line = line.replace('\r\n', '\n')
            chunks.append(line)
            stream.write(line)
            stream.flush()
            print(line, end='', flush=True)
        process.wait()
        output = ''.join(chunks)
        alive = base.adb('shell', 'echo T4_TOUCH_ADB_STILL_OK; cat /proc/uptime')
        stream.write(alive)
    unchanged = protected_hashes() == before
    restored = all(m in output for m in [
        'T4_TOUCH original SPI/GPIO state restored', 'T4_TOUCH SPI_SETUP_RESTORE_CONFIRMED',
        'T4_TOUCH PMU_CLOCK_RESTORE_CONFIRMED'])
    confirmed = all(marker in output for marker in [
        'N81_FIRMWARE_ACK_CONFIRMED', 'DEVICE_CAL_RAM_ACK_CONFIRMED',
        'FAMILY_55_CONFIRMED', 'OPERATING_MODE_0_CONFIRMED', 'REAL_FINGER_FRAMES_CONFIRMED'])
    interface_ok = all(m in output for m in ['interface_version=00000001', 'max_packet=00000294', 'FAMILY_55_CONFIRMED'])
    result = {'interface_only': args.interface_only, 'native_interface_confirmed': interface_ok,
              'operating_mode_0_confirmed': 'OPERATING_MODE_0_CONFIRMED' in output,
              'pmu_clock_51_confirmed': 'PMU_GPIO0_NATIVE_CLOCK_51_CONFIRMED' in output,
              'log': str(log), 'program_sha256': base.sha(exe),
              'real_finger_frames': confirmed, 'state_restored': restored,
              'adb_shell': 'T4_TOUCH_ADB_STILL_OK' in alive, 'protected_unchanged': unchanged,
              'android_touch_registered': False,
              'spi_setup_500_readback': 'SPI_SETUP_readback=000001f4' in output,
              'remote_adb_exit': process.returncode}
    (OUT / ('result-' + stamp + '.json')).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    if not unchanged or not restored or not result['adb_shell']:
        raise RuntimeError('Baseline/state/ADB check failed; inspect saved log')
    return 0 if (interface_ok if args.interface_only else confirmed) else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print('T4_TOUCH_CLOCK_15:', exc, file=sys.stderr)
        raise SystemExit(1)
