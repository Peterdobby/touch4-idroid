#!/usr/bin/env python3
"""Build the menu initramfs (menu as /init plus a static BusyBox). No USB access."""
import argparse
import gzip
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
SAVED = HERE.parents[1] / 'saved'
CROSS = SAVED / 'toolchain/gcc-4.8.5-nolibc/arm-linux-gnueabi/bin/arm-linux-gnueabi-'
FONT = SAVED / 'sources/iDroid-kernel-T4_LINUX_RAM_02/drivers/video/console/font_8x16.c'
TOUCH_DRIVER = HERE.parent / 'work/n81-touch'          # built from touch/n81-touch.c
TOUCH_DATA = SAVED / 'research/touch-bringup/n81-fw'     # this device's firmware and calibration
BUSYBOX = SAVED / 'downloads/busybox-armv7'  # Alpine busybox-static 1.37.0-r31, armv7
BUSYBOX_SHA = '2b6c948da829c4eb46084f947316d7439607fff47eb8687c45330adb273c4540'
def applets():
    """Every applet gets a link: this BusyBox build does not install them itself."""
    names = subprocess.check_output(['qemu-arm', str(BUSYBOX), '--list'], text=True).split()
    return [n for n in names if n != 'busybox']


# what bt-services and bt-audio run inside /alp
USERLAND_PROGRAMS = ('usr/bin/dbus-daemon', 'usr/lib/bluetooth/bluetoothd', 'usr/bin/bluetoothctl',
                     'usr/bin/bluealsa', 'usr/bin/bluealsa-cli', 'usr/bin/bluealsa-aplay', 'usr/bin/mpg123')


def userland_unused(tar):
    """Programs and libraries of the userland that nothing above needs: the whole
    kernel, this included, must fit the loader."""
    files = {m.name.removeprefix('./'): m for m in tar}

    def resolve(name):
        while files[name].issym():
            link = files[name].linkname
            name = os.path.normpath(link.lstrip('/') if link.startswith('/')
                                    else os.path.join(os.path.dirname(name), link))
        return name

    # ALSA and mpg123 plugins are opened at run time: keep them and what they need
    todo = list(USERLAND_PROGRAMS) + [n for n, m in files.items()
                                      if m.isreg() and ('/alsa-lib/' in n or '/mpg123/' in n)]
    keep = set()
    with tempfile.TemporaryDirectory() as tmp:
        while todo:
            name = resolve(todo.pop())
            if name in keep:
                continue
            keep.add(name)
            copy = Path(tmp, 'elf')
            copy.write_bytes(tar.extractfile(files[name]).read())
            dynamic = subprocess.check_output([f'{CROSS}readelf', '-d', str(copy)], text=True)
            for library in re.findall(r'\(NEEDED\).*\[(.+?)\]', dynamic):
                found = [d + library for d in ('lib/', 'usr/lib/') if d + library in files]
                assert found, f'{name}: {library} is not in the userland'
                todo.append(found[0])
    return {n for n, m in files.items() if m.isreg() and n not in keep and
            (n.startswith(('usr/bin/', 'usr/sbin/')) or '.so' in n)}


def entry(name, inode, mode, data=b'', rdev=(0, 0)):
    path = name.encode() + b'\0'
    fields = (inode, mode, 0, 0, 1, 0, len(data), 0, 0, *rdev, len(path), 0)
    record = b'070701' + ''.join(f'{v:08x}' for v in fields).encode() + path
    return record + b'\0' * (-len(record) % 4) + data + b'\0' * (-len(data) % 4)


def font_header():
    text = FONT.read_text(encoding='latin-1').split('fontdata_8x16[FONTDATAMAX] = {', 1)[1]
    body = re.sub(r'/\*.*?\*/', '', text.split('};', 1)[0], flags=re.S)
    values = [int(x, 16) for x in re.findall(r'0x[0-9a-fA-F]+', body)]
    assert len(values) == 4096
    return ('/* Linux VGA 8x16 font, drivers/video/console/font_8x16.c (GPL-2.0). */\n'
            'static const unsigned char font[4096]={' + ','.join(map(str, values)) + '};\n')


def wifi_items():
    """Wi-Fi drivers, this device's firmware and the network keys (never in Git)."""
    work, fw = HERE.parent / 'work', SAVED / 'research/wifi'
    modules = ('cfg80211', 'brcmutil', 'brcmfmac', 'brcmfmac-wcc', 'sdhci-pltfm', 'sdhci-s5l8930')
    keys = ''
    for line in (work / 'wifi-networks').read_text().splitlines():
        if not line.startswith('#') and '\t' in line:
            ssid, password = line.split('\t', 1)
            key = hashlib.pbkdf2_hmac('sha1', password.encode(), ssid.encode(), 4096, 32)
            keys += f'{ssid}\t{key.hex()}\n'
    nvram = (fw / 'wifi/4329b1/loco.txt').read_text().rstrip('\n')
    nvram += '\nmacaddr=' + (fw / 'macaddr').read_text().strip() + '\n'
    items = [(d, 0o40755, b'', (0, 0)) for d in
             ('etc', 'lib', 'lib/wifi', 'lib/firmware', 'lib/firmware/brcm')]
    items += [(f'lib/wifi/{m}.ko', 0o100644, (work / f'modules/{m}.ko').read_bytes(), (0, 0))
              for m in modules]
    items += [
        ('lib/firmware/brcm/brcmfmac4329-sdio.bin', 0o100644, (fw / 'wifi/4329b1/loco.bin').read_bytes(), (0, 0)),
        ('lib/firmware/brcm/brcmfmac4329-sdio.txt', 0o100644, nvram.encode(), (0, 0)),
        ('etc/wifi-networks', 0o100600, keys.encode(), (0, 0)),
        ('lib/wifi/udhcpc.sh', 0o100755, (HERE.parent / 'wifi/udhcpc.sh').read_bytes(), (0, 0)),
        ('bin/wifi-up', 0o100755, (HERE.parent / 'wifi/wifi-up.sh').read_bytes(), (0, 0)),
        ('bin/wifi-tune', 0o100755, (HERE.parent / 'wifi/wifi-tune.sh').read_bytes(), (0, 0)),
        ('bin/n81-wifi', 0o100755, (work / 'n81-wifi').read_bytes(), (0, 0)),
        ('bin/wlan-power', 0o100755, (work / 'wlan-power').read_bytes(), (0, 0)),
    ]
    work_bin = HERE.parent / 'work'
    # sound: ALSA modules and the speaker driver (audio/driver/build.sh), player, scripts
    items.append(('lib/sound', 0o40755, b'', (0, 0)))
    items += [(f'lib/sound/{m.name}', 0o100644, m.read_bytes(), (0, 0))
              for m in sorted((work_bin / 'sound').glob('*.ko'))]
    items.append(('bin/n81-play', 0o100755, (work_bin / 'n81-play').read_bytes(), (0, 0)))
    items += [('bin/' + name, 0o100755, (HERE.parent / f'audio/{name}.sh').read_bytes(), (0, 0))
              for name in ('sound-up', 'sound-test')]
    # Bluetooth: kernel modules, tool and the menu's scan script
    items.append(('lib/bluetooth', 0o40755, b'', (0, 0)))
    items += [(f'lib/bluetooth/{m}.ko', 0o100644, (work / f'modules/{m}.ko').read_bytes(), (0, 0))
              for m in ('af_alg', 'algif_hash', 'algif_skcipher', 'algif_aead', 'ecc', 'ecdh_generic',
                        'bluetooth', 'btintel', 'hci_uart')]
    items.append(('bin/n81-buttons', 0o100755, (work_bin / 'n81-buttons').read_bytes(), (0, 0)))
    items += [('bin/n81-bt', 0o100755, (work_bin / 'n81-bt').read_bytes(), (0, 0)),
              ('bin/bt-scan', 0o100755, (HERE.parent / 'bluetooth/bt-scan.sh').read_bytes(), (0, 0)),
              ('bin/bt-audio', 0o100755, (HERE.parent / 'bluetooth/bt-audio.sh').read_bytes(), (0, 0))]
    items += [('bin/' + name, 0o100755, (HERE.parent / f'bluetooth/{name}.sh').read_bytes(), (0, 0))
              for name in ('bt-boot', 'bt-services', 'bt-accept')]
    # this module's patch RAM image, extracted from iOS (private, never in Git)
    patch = SAVED / 'research/bluetooth/n81-bt.hcd'
    if patch.is_file():
        items.append(('lib/firmware/brcm/n81-bt.hcd', 0o100644, patch.read_bytes(), (0, 0)))
    # Alpine userland for BlueZ/BlueALSA as /alp (bluetooth/make-userland.sh)
    userland = SAVED / 'research/bluetooth/userland.tar.gz'
    if userland.is_file():
        import tarfile
        items.append(('alp', 0o40755, b'', (0, 0)))
        with tarfile.open(userland) as tar:
            unused = userland_unused(tar)
            for m in tar:
                name = m.name.removeprefix('./').rstrip('/')
                if name in ('', '.') or name in unused:
                    continue
                if m.isdir():
                    items.append(('alp/' + name, 0o40000 | m.mode, b'', (0, 0)))
                elif m.issym():
                    items.append(('alp/' + name, 0o120777, m.linkname.encode(), (0, 0)))
                elif m.isreg() or m.islnk():
                    items.append(('alp/' + name, 0o100000 | m.mode, tar.extractfile(m).read(), (0, 0)))
    # the phone interface, when phone-ui/ has been built for the device
    apps = HERE.parents[1] / 'phone-ui'
    phone = apps / 'build/phone-device/phone'
    if phone.is_file():
        items += [('bin/phone', 0o100755, phone.read_bytes(), (0, 0)),
                  ('bin/start-ui', 0o100755, (apps / 'start-ui').read_bytes(), (0, 0))]
    else:
        print('phone-ui not built: image starts in the text menu')
    address = SAVED / 'research/bluetooth/n81-bt.addr'
    if address.is_file():
        items.append(('lib/firmware/brcm/n81-bt.addr', 0o100600, address.read_bytes(), (0, 0)))
    return items


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path, help='output directory')
    parser.add_argument('--full', action='store_true',
                        help='also write rootfs.cpio with Wi-Fi, to be built into the 6.17 kernel')
    options = parser.parse_args()
    out = options.out
    out.mkdir(parents=True, exist_ok=True)
    (out / 'font.h').write_text(font_header())
    subprocess.run([f'{CROSS}gcc', '-Wall', '-Wextra', '-Werror', '-O2', '-marm', '-march=armv7-a',
                    '-mfloat-abi=soft', '-mno-unaligned-access', '-ffreestanding', '-fno-builtin',
                    '-fno-tree-loop-distribute-patterns', '-nostdlib', '-static',
                    '-Wl,--build-id=none', f'-I{out}', str(HERE / 'menu.c'), '-lgcc',
                    '-o', str(out / 'init')], check=True)
    busybox = BUSYBOX.read_bytes()
    assert hashlib.sha256(busybox).hexdigest() == BUSYBOX_SHA, 'unexpected BusyBox binary'
    items = [(d, 0o40755, b'', (0, 0)) for d in ('bin', 'dev', 'proc', 'sys', 'tmp')]
    for name, rdev in (('console', (5, 1)), ('mem', (1, 1)), ('null', (1, 3)),
                       ('zero', (1, 5)), ('kmsg', (1, 11)), ('fb0', (29, 0))):
        items.append(('dev/' + name, 0o20600, b'', rdev))
    items.append(('init', 0o100755, (out / 'init').read_bytes(), (0, 0)))
    items.append(('bin/busybox', 0o100755, busybox, (0, 0)))
    items += [('bin/' + a, 0o120777, b'busybox', (0, 0)) for a in applets()]
    files = (TOUCH_DRIVER, TOUCH_DATA / 'zephyr2.bin', TOUCH_DATA / 'MtCl.bin')
    if all(f.is_file() for f in files):
        items += [('touch', 0o40755, b'', (0, 0)), ('touch/driver', 0o100755, files[0].read_bytes(), (0, 0)),
                  ('touch/fw.bin', 0o100644, files[1].read_bytes(), (0, 0)),
                  ('touch/cal.bin', 0o100644, files[2].read_bytes(), (0, 0))]
    else:
        print('touch driver or firmware missing: image built without touch')
    def pack(entries):
        data = b''.join(entry(n, i, m, d, r) for i, (n, m, d, r) in enumerate(entries, 1))
        return data + entry('TRAILER!!!', 0, 0)

    if options.full:
        (out / 'rootfs.cpio').write_bytes(pack(items + wifi_items()))
        (out / 'rootfs.cpio').chmod(0o600)  # holds the network keys
        # The loader still needs an external initramfs: an empty archive.
        (out / 'empty.cpio.gz').write_bytes(gzip.compress(pack([]), mtime=0))
        print('rootfs:', (out / 'rootfs.cpio').stat().st_size, 'bytes')
    archive = pack(items)
    packed = gzip.compress(archive, compresslevel=9, mtime=0)
    assert len(packed) <= 0x100000, 'initramfs too large for the loader'
    (out / 'initramfs.cpio.gz').write_bytes(packed)
    print('initramfs:', len(packed), 'bytes')


if __name__ == '__main__':
    main()
