"""Host-only component preparation through existing, unmodified Kit tools."""
import hashlib
import contextlib
import json
import os
import plistlib
import re
import shutil
import struct
import subprocess
import tempfile
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

KEYS_COMMIT = '033cbc09511de587e1ea4255e26662be543cbb51'
MODEL = 'iPod4,1'
OLD_IDENTITY_SHA256 = 'beac0c595167df8326e823df14e03759d7becc81686151a1812260ada59c1a09'


class ProfileError(RuntimeError):
    pass


def require(ok, reason):
    if not ok:
        raise ProfileError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def image_data(image, kind=None):
    require(len(image) >= 32, 'Image3 file is too short')
    magic, total, length, _, actual = struct.unpack_from('<5I', image)
    require(magic == 0x496d6733 and total == len(image) and length == total-20, 'Invalid Image3 header')
    require(kind is None or actual == kind, 'Image3 type mismatch')
    offset, found = 20, []
    while offset < len(image):
        require(offset + 12 <= len(image), 'Truncated Image3 tag')
        tag, size, n = struct.unpack_from('<3I', image, offset)
        require(size >= 12 and offset+size <= len(image) and n <= size-12, 'Image3 tag out of bounds')
        if tag == 0x44415441:
            found.append(image[offset+12:offset+12+n])
        offset += size
    require(offset == len(image) and len(found) == 1, 'Image3 DATA is not unique')
    return found[0]


def patch_flags(version):
    require(re.fullmatch(r'[456]\.\d+(?:\.\d+)?', version), 'Only official iOS 4/5/6 releases are supported')
    flags = ['--rsa', '--boot-partition', '--boot-ramdisk']
    if version.startswith('4.'):
        flags += ['--logo4']
        if version not in ['4.3.4', '4.3.5']:
            flags += ['--433']
    else:
        flags += ['--logo']
    return flags + ['-b', 'pio-error=0 debug=0x2014e serial=3']


def patcher_result_ok(code, output, target_exists):
    # The installed Kit patch_iboot() checks the newly produced file, rather
    # than treating this patcher's successful exit 1 as a shell failure.
    return (code in [0, 1] and target_exists and b'Writing out patched file' in output
            and b'main: Quitting' in output and b'failed' not in output.lower())


def find_kit(explicit=None):
    candidates = [Path(explicit)] if explicit else []
    if os.environ.get('T4_KIT_DIR'):
        candidates.append(Path(os.environ['T4_KIT_DIR']))
    candidates += sorted((Path.home() / 'Desktop').glob('**/Legacy-iOS-Kit*'))
    names = ['pzb', 'xpwntool', 'iBoot32Patcher', 'img3maker']
    for path in candidates:
        directory = path / 'bin/macos'
        if all((directory / name).is_file() for name in names):
            return directory
    raise ProfileError('Specify an existing Legacy iOS Kit folder with --kit')


def apple_url(url):
    parsed = urllib.parse.urlsplit(url)
    require(parsed.scheme in ['https', 'http'] and parsed.hostname and parsed.hostname.endswith('.apple.com'), 'Firmware download URL is not on an Apple domain')
    return urllib.parse.urlunsplit(('https', parsed.netloc, parsed.path, parsed.query, parsed.fragment))


def fetch_json(url, destination):
    request = urllib.request.Request(url, headers={'User-Agent': 'T4-Android-Installer/02'})
    with urllib.request.urlopen(request, timeout=35) as response:
        data = response.read(4*1024*1024 + 1)
    require(len(data) <= 4*1024*1024, 'Metadata too large')
    value = json.loads(data)
    destination.write_bytes(data)
    return value


def package_set(images):
    kinds = [0x696c6c62, 0x69626f74, 0x64747265, 0x6c6f676f, 0x7265636d, 0x69626f62, 0x53434142]
    require(len(images) == 7 and sum(map(len, images)) < 0x180000, 'Boot image set exceeds capacity')
    data = bytearray(struct.pack('<4I', 0x4f423454, 2, 7, 0))
    for index, (blob, kind) in enumerate(zip(images, kinds)):
        image_data(blob, kind)
        require(len(blob) <= 0xc0000, 'Boot image too large')
        data += struct.pack('<4I', 0 if index == 0 else 1, len(blob), kind, zlib.crc32(blob))
        data += blob
        data += bytes((-len(data)) % 4)
    struct.pack_into('<I', data, 12, zlib.crc32(data[16:]))
    require(len(data) <= 0x180000, 'Package exceeds capacity')
    return bytes(data)


def unpack_set(data):
    require(len(data) >= 16, 'Truncated boot image set header')
    magic, version, count, checksum = struct.unpack_from('<4I', data)
    require((magic, version, count) == (0x4f423454, 2, 7) and checksum == zlib.crc32(data[16:]),
            'Boot image set verification failed')
    images, offset = [], 16
    kinds = [0x696c6c62, 0x69626f74, 0x64747265, 0x6c6f676f, 0x7265636d, 0x69626f62, 0x53434142]
    for index, kind in enumerate(kinds):
        require(offset + 16 <= len(data), 'Truncated boot image set record')
        selector, size, actual, checksum = struct.unpack_from('<4I', data, offset)
        offset += 16
        require(selector == (0 if index == 0 else 1) and actual == kind and
                size <= len(data) - offset, 'Invalid boot image set record')
        image = data[offset:offset+size]
        require(zlib.crc32(image) == checksum, 'Boot image CRC mismatch')
        image_data(image, kind)
        images.append(image)
        offset += (size + 3) & ~3
    require(offset == len(data), 'Unexpected trailing data in boot image set')
    return images


def base_images(base):
    names = json.loads((base / 'payload/base-images.json').read_text())['order']
    require(len(names) == 7, 'Incorrect base image count')
    return [(base / 'payload/base-images' / name).read_bytes() for name in names]


def ensure_base_firmware(base, directory):
    """Preserve the hardware-proven 10B500 first stage; retain old host inputs."""
    manifest = verify_profile(directory)
    original = (directory / 'payload/boot-set.pack').read_bytes()
    actual, expected = unpack_set(original), base_images(base)
    require(all(actual[i] == expected[i] for i in [0, 1, 3, 4, 6]) and
            actual[5] == (directory / 'payload/menu.img3').read_bytes(),
            'Cache does not match a recognized base boot chain; original retained')
    if actual[2] == expected[2]:
        return
    require(actual[2] == (directory / 'payload/target-dt.img3').read_bytes(),
            'Cached DeviceTree does not match the recognized old profile; original retained')
    # Preserve every previous input before atomically replacing this host pack.
    history = directory.parent / '.history' / directory.name / sha(original)
    if not history.exists():
        history.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix='.stage1-backup-', dir=history.parent))
        shutil.copytree(directory, staging / 'profile', copy_function=link_or_copy)
        os.rename(staging / 'profile', history)
        staging.rmdir()
    require((history / 'payload/boot-set.pack').read_bytes() == original,
            'Previous profile backup incomplete; original retained')
    actual[2] = expected[2]
    fixed = package_set(actual)
    target = directory / 'payload/boot-set.pack'
    temporary = target.with_suffix('.stage1-update')
    temporary.write_bytes(fixed)
    os.replace(temporary, target)
    provenance_path = directory / 'PROVENANCE.json'
    provenance = json.loads(provenance_path.read_text())
    provenance.update(base_firmware_build='10B500', base_firmware_preserved=True,
                      target_device_tree_written_to_firmware=False,
                      prior_pack_sha256=sha(original), prior_profile=str(history),
                      first_stage_repair_hardware_confirmed=False)
    temporary = provenance_path.with_suffix('.stage1-update')
    temporary.write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + '\n')
    os.replace(temporary, provenance_path)
    for name in ['payload/boot-set.pack', 'PROVENANCE.json']:
        blob = (directory / name).read_bytes()
        manifest['files'][name] = dict(size=len(blob), sha256=sha(blob))
    temporary = directory / 'manifest.stage1-update'
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    os.replace(temporary, directory / 'manifest.json')
    verify_profile(directory)
    print('Host profile corrected: complete 10B500 base components retained; old profile backup: ' + str(history), flush=True)


def link_or_copy(source, target):
    source, target = Path(source), Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def verify_profile(directory):
    manifest = json.loads((directory / 'manifest.json').read_text())
    for name, record in manifest['files'].items():
        path = directory / name
        require(path.resolve().is_relative_to(directory.resolve()), 'Profile path escapes its directory')
        data = path.read_bytes()
        require(len(data) == record['size'] and sha(data) == record['sha256'], 'Cache checksum failed: ' + name)
    return manifest


def refresh_cached_identity(base, directory):
    """Upgrade only the known broken read-only probe in an intact host cache."""
    manifest = verify_profile(directory)
    name = 'payload/device-info'
    if manifest['files'][name]['sha256'] != OLD_IDENTITY_SHA256:
        return
    data = (base / name).read_bytes()
    if sha(data) == OLD_IDENTITY_SHA256:
        return
    target = directory / name
    temporary = target.with_suffix('.identity-update')
    temporary.write_bytes(data)
    temporary.chmod(0o755)
    os.replace(temporary, target)  # never mutate a hardlinked old release
    manifest['files'][name] = dict(size=len(data), sha256=sha(data))
    path = directory / 'manifest.json'
    temporary = path.with_suffix('.identity-update')
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    os.replace(temporary, path)
    verify_profile(directory)
    print('Read-only device identity probe updated in host cache.', flush=True)


@contextlib.contextmanager
def preparation_dir(cache):
    work = Path(tempfile.mkdtemp(prefix='prepare-', dir=cache))
    try:
        yield work
    except BaseException as error:
        (work / 'ERROR.txt').write_text(type(error).__name__ + ': ' + str(error) + '\n')
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        raise ProfileError(str(error) + '\nRetained components and failure logs: ' + str(work)) from error
    else:
        shutil.rmtree(work)


def prepare(base, cache, version, build=None, kit=None):
    patch_flags(version)
    require(build is None or re.fullmatch(r'[0-9A-Z]+', build), 'Invalid build identifier')
    cache.mkdir(parents=True, exist_ok=True)
    for parent in [cache, base / 'ready-profiles']:
        if not parent.exists():
            continue
        choices = []
        for directory in parent.iterdir():
            f = directory / 'manifest.json'
            if f.is_file():
                record = json.loads(f.read_text())['profiles'][0]
                if record['version'] == version and (build is None or record['build'] == build):
                    choices.append((directory, record))
        if len(choices) != 1:
            continue
        directory, record = choices[0]
        if parent == cache:
            refresh_cached_identity(base, directory)
            ensure_base_firmware(base, directory)
            print('Reusing verified component profile: ' + record['build'], flush=True)
            return directory
        destination = cache / record['build']
        require(not destination.exists(), 'Profile destination already exists but did not pass matching checks')
        with preparation_dir(cache) as staging:
            output = staging / 'bundle'
            shutil.copytree(directory, output)
            for name in ['android.img3', 'device-info', 'check-llb', 'LLB.img3']:
                link_or_copy(base / 'payload' / name, output / 'payload' / name)
            link_or_copy(base / 'payload/apply-set-generic', output / 'payload/apply-set')
            verify_profile(output)
            ensure_base_firmware(base, output)
            os.rename(output, destination)
        print('Extracted included official component profile: ' + record['build'], flush=True)
        return destination
    tools = find_kit(kit)
    if build and (cache / build / 'manifest.json').exists():
        refresh_cached_identity(base, cache / build)
        ensure_base_firmware(base, cache / build)
        result = verify_profile(cache / build)
        p = result['profiles'][0]
        require(p['version'] == version and p['build'] == build, 'Cached version mismatch')
        print('Reusing verified component profile: ' + build, flush=True)
        return cache / build
    with preparation_dir(cache) as work:
        catalog = fetch_json('https://api.ipsw.me/v4/device/' + urllib.parse.quote(MODEL, safe='') + '?type=ipsw', work / 'catalog.json')
        choices = [f for f in catalog['firmwares'] if f['identifier'] == MODEL and f['version'] == version and (build is None or f['buildid'] == build)]
        require(len(choices) == 1, 'Firmware version not found or build ambiguous; specify --build')
        firmware = choices[0];build = firmware['buildid']
        require(re.fullmatch(r'[0-9A-Z]+', build), 'Invalid build identifier')
        destination = cache / build
        if destination.exists():
            refresh_cached_identity(base, destination)
            ensure_base_firmware(base, destination)
            return destination
        url = apple_url(firmware['url'])

        def run(command, log, timeout=90, kit_patcher=False):
            p = subprocess.run([str(x) for x in command], cwd=work, capture_output=True, timeout=timeout)
            (work / log).write_bytes(p.stdout + p.stderr)
            ok = patcher_result_ok(p.returncode, p.stdout+p.stderr, (work/'iBoot.kit.raw').is_file()) if kit_patcher else p.returncode == 0
            require(ok, 'Component tool failed: ' + log + '\n' + (p.stdout+p.stderr).decode(errors='replace')[-1000:])

        def download(member, name):
            require(not member.startswith('/') and '..' not in Path(member).parts, 'Invalid firmware member path')
            print('Downloading component: ' + Path(member).name, flush=True)
            # pzb's output argument is relative to cwd; never pass an absolute output.
            run([tools / 'pzb', '-g', member, '-o', name, url], name + '.download.log')
            path = work / name
            require(path.is_file() and 0 < path.stat().st_size <= 2*1024*1024, 'Component was not saved correctly: ' + name)
            return path.read_bytes()

        manifest_bytes = download('BuildManifest.plist', 'BuildManifest.plist')
        apple = plistlib.loads(manifest_bytes)
        require(apple['ProductVersion'] == version and apple['ProductBuildVersion'] == build and MODEL in apple.get('SupportedProductTypes', []), 'Apple manifest does not match target version')
        identities = [i for i in apple['BuildIdentities'] if i['Info']['DeviceClass'] == 'n81ap']
        require(identities, 'Firmware manifest lacks N81AP')
        component = identities[0]['Manifest']
        for kind in ['iBoot', 'DeviceTree']:
            require(all(i['Manifest'][kind]['Info']['Path'] == component[kind]['Info']['Path'] for i in identities), 'Boot components differ between firmware identities')
        stock = download(component['iBoot']['Info']['Path'], 'iBoot.original.img3')
        dt = download(component['DeviceTree']['Info']['Path'], 'DeviceTree.original.img3')
        image_data(stock, 0x69626f74);image_data(dt, 0x64747265)
        keys_url = 'https://raw.githubusercontent.com/LukeZGD/Legacy-iOS-Kit-Keys/' + KEYS_COMMIT + '/' + MODEL + '/' + build + '/index.html'
        keys = fetch_json(keys_url, work / 'keys.json')
        require(keys['identifier'] == MODEL and keys['buildid'] == build, 'Kit key manifest does not match device or version')
        key = next(k for k in keys['keys'] if k['image'] == 'iBoot')
        require(key['filename'] == Path(component['iBoot']['Info']['Path']).name, 'iBoot filename does not match key manifest')
        iv, aes = key['iv'].zfill(32), key['key'].zfill(64)
        require(re.fullmatch('[0-9a-fA-F]{32}', iv) and re.fullmatch('[0-9a-fA-F]{64}', aes), 'Invalid iBoot decryption parameters')
        run([tools / 'xpwntool', 'iBoot.original.img3', 'iBoot.raw', '-iv', iv, '-k', aes], 'iboot-decrypt.log')
        raw = (work / 'iBoot.raw').read_bytes()
        require(0x400 <= len(raw) <= 0x80000 and struct.unpack_from('<I', raw)[0] & 0xff000000 == 0xea000000 and b'iBoot-' in raw, 'Invalid decrypted iBoot format')
        flags = patch_flags(version)
        run([tools / 'iBoot32Patcher', 'iBoot.raw', 'iBoot.kit.raw', *flags], 'existing-kit-patcher.log', kit_patcher=True)
        target = (work / 'iBoot.kit.raw').read_bytes()
        require(len(target) == len(raw) and target[:4] == raw[:4], 'Unexpected Kit iBoot output size or entry point')
        run([tools / 'img3maker', '-f', 'iBoot.kit.raw', '-o', 'ios-iboot.img3', '-t', 'ibob'], 'iboot-package.log')
        require(image_data((work / 'ios-iboot.img3').read_bytes(), 0x69626f62) == target, 'iBoot packaging changed the payload')
        template = json.loads((base / 'payload/menu-template.json').read_text())
        menu = bytearray((base / 'payload/menu-template.img3').read_bytes())
        require(sha(menu) == template['sha256'], 'Menu template verification failed')
        for field, value in [('t4_ios_size', len(target)), ('t4_ios_crc', zlib.crc32(target))]:
            off = template['patches'][field]
            require(struct.unpack_from('<I', menu, off)[0] == 0, 'Template patch location is not empty')
            struct.pack_into('<I', menu, off, value)
        images = base_images(base)
        images[5] = bytes(menu)
        pack = package_set(images)
        bundle = work / 'bundle';(bundle / 'payload').mkdir(parents=True)
        for name in ['android.img3', 'device-info', 'check-llb', 'LLB.img3']:
            link_or_copy(base / 'payload' / name, bundle / 'payload' / name)
        link_or_copy(base / 'payload/apply-set-generic', bundle / 'payload/apply-set')
        (bundle / 'payload/ios-iboot.img3').write_bytes((work / 'ios-iboot.img3').read_bytes())
        (bundle / 'payload/boot-set.pack').write_bytes(pack)
        (bundle / 'payload/menu.img3').write_bytes(menu)
        (bundle / 'payload/target-dt.img3').write_bytes(dt)
        provenance = dict(version=version, build=build, source=url, ipsw_bytes=firmware['filesize'],
             retained_download_bytes=len(manifest_bytes)+len(stock)+len(dt), full_ipsw_downloaded=False,
             source_sha256={'iBoot':sha(stock),'DeviceTree':sha(dt),'BuildManifest':sha(manifest_bytes)},
             kit_keys_source=keys_url, kit_flags=flags,
             kit_tools={n:sha((tools/n).read_bytes()) for n in ['pzb','xpwntool','iBoot32Patcher','img3maker']},
             exploit_or_signature_patch_code_modified=False, existing_kit_patcher_invoked=True,
             target_raw_size=len(target), target_raw_crc32=zlib.crc32(target), target_raw_sha256=sha(target),
             hardware_boot_tested=False, base_firmware_build='10B500', base_firmware_preserved=True,
             target_device_tree_written_to_firmware=False)
        (bundle / 'PROVENANCE.json').write_text(json.dumps(provenance, indent=2)+'\n')
        logs = bundle / 'preparation';logs.mkdir()
        for file in work.iterdir():
            if file.is_file() and file.name != 'catalog.json':
                shutil.copy2(file, logs / file.name)
        original = json.loads((base / 'manifest.json').read_text())
        result = dict(original, name='T4_ANDROID_INSTALLER_02_'+build,
            profiles=[dict(id='kit-native-'+build, version=version, build=build,
                kernel_path='/System/Library/Caches/com.apple.kernelcaches/kernelcache', kernel_sha256=[],
                qualification='Experimental persistent installation, explicitly requested by owner')],
            runtime_files=[dict(source='payload/android.img3', destination='/boot/t4/android.img3'),
                           dict(source='payload/ios-iboot.img3', destination='/boot/t4/ios-iboot.img3')])
        result['files']={str(p.relative_to(bundle)):dict(size=p.stat().st_size,sha256=sha(p.read_bytes())) for p in bundle.rglob('*') if p.is_file()}
        (bundle / 'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        os.rename(bundle, destination)
        verify_profile(destination)
        print('Persistent installation profile generated: iOS '+version+' / '+build, flush=True)
        return destination
