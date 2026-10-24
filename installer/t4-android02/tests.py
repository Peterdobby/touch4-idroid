#!/usr/bin/env python3
"""Independent fake-device integration tests. Never invokes SSH or IOKit."""
import importlib.util
import json
import plistlib
import shlex
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('installer_backend', Path(__file__).with_name('base_backend.py'))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


class Device:
    def __init__(self):
        self.files = {'/mnt1/System/Library/CoreServices/SystemVersion.plist': plistlib.dumps(dict(ProductVersion='7.1.2', ProductBuildVersion='11D257')),
                      '/mnt1/kernelcache': b'original-kernel'}
        self.directories = {'/mnt1', '/mnt1/boot', '/var/run'}
        self.links = set()
        self.identity = dict(machine='iPod4,1', ecid_candidates=['0x123'])
        self.identity_code = 0
        self.nvram = ('boot-partition\t2\nboot-ramdisk\t' + b.BOOTRAMDISK + '\n').encode()
        self.dra = b'D' * 524288
        self.free = 10000
        self.normal_os = False
        self.readonly = True
        self.llb_ok = True
        self.apply_ok = True
        self.apply_timeout = False
        self.corrupt_upload = False
        self.mount_system = True
        self.cleanup_fails = False
        self.cleanup_timeout = False
        self.persistent_files = []
        self.firmware_calls = 0
        self.commands = []

    def read(self, path):
        if path not in self.files:
            raise b.Stop('Fake file missing: ' + path)
        return self.files[path]

    def run(self, command, data=None, timeout=60, allow_error=False):
        self.commands.append(command)
        for part in command.split(' && '):
            code, stdout = self.one(shlex.split(part), data)
            if code:
                if not allow_error:
                    raise b.Stop('Fake remote error: ' + part)
                return subprocess.CompletedProcess(command, code, stdout, b'fake failure')
        return subprocess.CompletedProcess(command, 0, stdout, b'')

    def one(self, p, data):
        if p == ['/sbin/mount']:
            root = b'/dev/disk0s1s1 on / (hfs)\n' if self.normal_os else b'/dev/md0 on / (hfs)\n'
            return 0, root + (b'/dev/disk0s1s1 on /mnt1 (hfs' + (b', read-only' if self.readonly else b'') + b')\n' if self.mount_system else b'')
        if p == ['/usr/sbin/nvram', '-p']:
            return 0, self.nvram
        if p[0] == '/bin/dd':
            if 'if=/dev/rdisk0s1s3' in p:
                return 0, self.dra
            if 'if=/dev/rdisk0s1s1' in p:
                h = bytearray(8192);h[1024:1026] = b'H+'
                struct.pack_into('>III', h, 1064, 4096, 20000, self.free)
                return 0, bytes(h)
        if p[0] == 'test':
            negate = p[1] == '!';flag, path = p[2:] if negate else p[1:]
            result = path in (self.links if flag == '-L' else self.directories if flag == '-d' else set(self.files) | self.directories | self.links)
            return (0 if result != negate else 1), b''
        if p[0] == '/bin/mkdir':
            path = p[-1]
            if '-p' not in p and path in self.directories:
                return 1, b''
            self.directories.add(path)
            return 0, b''
        if p[0] == '/sbin/mount_hfs':
            self.mount_system = True;return 0, b''
        if p == ['/sbin/mount', '-u', '-w', '/mnt1']:
            self.readonly = False;return 0, b''
        if p[:2] == ['/bin/cat', '>']:
            path = p[-1]
            if path.startswith('/mnt1/'):
                if self.readonly:
                    return 1, b''
                self.persistent_files.append(path)
                if self.corrupt_upload:
                    data += b'corruption'
            self.files[path] = data
            return 0, b''
        if p[0] == '/bin/chmod':
            return 0, b''
        if p[0] == '/bin/mv':
            if p[1] == '/t4-android-install.lock':
                if self.cleanup_timeout:
                    raise subprocess.TimeoutExpired(p, 60)
                if self.cleanup_fails:
                    return 1, b''
                self.directories.remove(p[1]);self.directories.add(p[2]);return 0, b''
            self.files[p[2]] = self.files.pop(p[1]);return 0, b''
        if p == ['/mnt1/bin/sync']:
            return 0, b''
        if p[0].endswith('/device-info'):
            return self.identity_code, json.dumps(self.identity).encode()
        if p[0].endswith('/check-llb'):
            return (0 if self.llb_ok else 10), (b'result=00000000' if self.llb_ok else b'result=error')
        if p[0].endswith('/apply-set'):
            self.firmware_calls += 1
            if self.apply_timeout:
                raise subprocess.TimeoutExpired(p, 60)
            return (0 if self.apply_ok else 17), (b'COMPLETE_IMAGE_SET_API_ACCEPTED' if self.apply_ok else b'SET_INCOMPLETE_DO_NOT_REBOOT')
        raise AssertionError('Unexpected remote command ' + repr(p))


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.log = self.base / 'log';self.log.mkdir()
        self.device = Device()
        payload = self.base / 'payload';payload.mkdir()
        for name in ['device-info', 'check-llb', 'LLB.img3', 'apply-set', 'boot-set.pack', 'android.img3', 'devicetree-ios7.img3']:
            (payload / name).write_bytes(('test-' + name).encode())
        files = {str(p.relative_to(self.base)): dict(size=p.stat().st_size, sha256=b.sha(p.read_bytes())) for p in payload.iterdir()}
        self.manifest = dict(ecid='0x123', dra_sha256=b.sha(self.device.dra), files=files,
            profiles=[dict(id='test-712', version='7.1.2', build='11D257', kernel_path='/kernelcache', kernel_sha256=[b.sha(b'original-kernel')])],
            runtime_files=[dict(source='payload/android.img3', destination='/boot/t4/android.img3'), dict(source='payload/devicetree-ios7.img3', destination='/boot/t4/devicetree-ios7.img3')])

    def installer(self):
        return b.Installer(self.device, self.manifest, self.base, self.log, self.base / 'state')

    def reject(self, modify):
        modify()
        with self.assertRaises(b.Stop):
            self.installer().check()
        self.assertEqual(self.device.firmware_calls, 0)
        self.assertEqual(self.device.persistent_files, [])

    def test_check_only_never_writes_persistent(self):
        self.installer().check()
        self.assertEqual(self.device.firmware_calls, 0)
        self.assertEqual(self.device.persistent_files, [])
        self.assertTrue(self.device.readonly)

    def test_normal_ios_refused(self):
        self.reject(lambda: setattr(self.device, 'normal_os', True))

    def test_wrong_ecid_refused(self):
        self.reject(lambda: self.device.identity.update(ecid_candidates=['0x999']))

    def test_probe_runtime_failure_saves_exit_and_stderr(self):
        self.device.identity_code = 255
        with self.assertRaisesRegex(b.Stop, '255'):
            self.installer().check()
        self.assertEqual(json.loads((self.log / 'device-info.json').read_text())['returncode'], 255)
        self.assertEqual((self.log / 'device-info.stderr').read_bytes(), b'fake failure')
        self.assertEqual(self.device.persistent_files, [])
        self.assertEqual(self.device.firmware_calls, 0)

    def test_empty_ecid_refused_with_saved_probe_output(self):
        self.reject(lambda: self.device.identity.update(ecid_candidates=[]))
        self.assertTrue((self.log / 'device-info.stdout').is_file())

    def test_wrong_model_refused(self):
        self.reject(lambda: self.device.identity.update(machine='iPhone3,1'))

    def test_ios_detected_but_unverified_version_refused(self):
        self.reject(lambda: self.device.files.update({'/mnt1/System/Library/CoreServices/SystemVersion.plist': plistlib.dumps(dict(ProductVersion='6.1.6', ProductBuildVersion='10B500'))}))

    def test_changed_kernel_refused(self):
        self.reject(lambda: self.device.files.update({'/mnt1/kernelcache': b'unknown'}))

    def test_changed_dra_refused(self):
        self.reject(lambda: setattr(self.device, 'dra', b'?' * 524288))

    def test_wrong_nvram_refused_without_setters(self):
        self.reject(lambda: setattr(self.device, 'nvram', b'boot-partition\t0\n'))
        self.assertFalse(any('nvram ' in c and not c.endswith(' -p') for c in self.device.commands))

    def test_low_space_refused(self):
        self.reject(lambda: setattr(self.device, 'free', 1))

    def test_failed_signature_preflight_refused(self):
        self.reject(lambda: setattr(self.device, 'llb_ok', False))

    def test_existing_different_file_not_overwritten(self):
        self.reject(lambda: self.device.files.update({'/mnt1/boot/t4/android.img3': b'keep-me'}))
        self.assertEqual(self.device.files['/mnt1/boot/t4/android.img3'], b'keep-me')

    def test_symlink_refused(self):
        self.reject(lambda: self.device.links.add('/mnt1/boot/t4'))

    def test_missing_mount_is_mounted_readonly(self):
        self.device.mount_system = False
        self.installer().check()
        self.assertTrue(self.device.readonly)
        self.assertIn('/bin/mkdir -p /mnt1 && /sbin/mount_hfs -o ro /dev/disk0s1s1 /mnt1', self.device.commands)

    def test_install_transfers_then_submits_once(self):
        i = self.installer();i.check();i.install()
        self.assertEqual(self.device.firmware_calls, 1)
        self.assertEqual(len(self.device.persistent_files), 2)
        self.assertEqual(self.device.files['/mnt1/kernelcache'], b'original-kernel')
        self.assertEqual(json.loads((self.base / 'state/0x123.json').read_text())['status'], 'COMPLETE')
        self.assertFalse(any('reboot' in c for c in self.device.commands))

    def test_identical_runtime_files_reused(self):
        self.device.directories.add('/mnt1/boot/t4')
        for item in self.manifest['runtime_files']:
            self.device.files['/mnt1' + item['destination']] = (self.base / item['source']).read_bytes()
        i = self.installer();i.check();i.install()
        self.assertEqual(self.device.persistent_files, [])
        self.assertEqual(self.device.firmware_calls, 1)

    def test_successful_install_requires_no_rmdir(self):
        i = self.installer();i.check();i.install()
        self.assertFalse(any('rmdir' in c for c in self.device.commands))
        self.assertNotIn('/t4-android-install.lock',self.device.directories)
        self.assertIn(i.ram+'/completed-install.lock',self.device.directories)
        state=json.loads((self.base/'state/0x123.json').read_text())
        self.assertEqual(state['status'],'COMPLETE')
        self.assertTrue(state['ram_lock_released'])

    def test_cleanup_failure_does_not_undo_success(self):
        i = self.installer();i.check();self.device.cleanup_fails=True;i.install()
        state=json.loads((self.base/'state/0x123.json').read_text())
        self.assertEqual(state['status'],'COMPLETE')
        self.assertTrue(state['api_accepted'])
        self.assertFalse(state['ram_lock_released'])
        self.assertEqual(self.device.firmware_calls,1)

    def test_cleanup_timeout_does_not_invite_second_submission(self):
        i = self.installer();i.check();self.device.cleanup_timeout=True;i.install()
        state=json.loads((self.base/'state/0x123.json').read_text())
        self.assertEqual(state['status'],'COMPLETE')
        self.assertFalse(state['ram_lock_released'])
        self.assertEqual(self.device.firmware_calls,1)

    def next_connection(self):
        self.log = self.base / 'next-log';self.log.mkdir()
        i = self.installer();i.check();return i

    def test_completed_same_ram_session_skips_repeated_firmware(self):
        i=self.installer();i.check();i.install()
        self.device.directories.add('/t4-android-install.lock')
        again=self.next_connection();again.install()
        self.assertEqual(self.device.firmware_calls,1)
        receipt=json.loads((self.log/'REUSED-COMPLETE.json').read_text())
        self.assertTrue(receipt['same_ram_session'])
        self.assertFalse(receipt['persistent_writes'])

    def test_legacy_receipt_with_stale_lock_recognized(self):
        i=self.installer();i.check();i.install()
        state=self.base/'state/0x123.json'
        previous=json.loads(state.read_text());previous.pop('ram_directory');b.save(state,previous)
        self.device.directories.add('/t4-android-install.lock')
        self.next_connection().install()
        self.assertEqual(self.device.firmware_calls,1)

    def test_host_history_from_another_ram_boot_is_not_reused(self):
        i=self.installer();i.check();i.install()
        self.device.files.pop(i.ram+'/boot-set.pack')
        self.device.directories.add('/t4-android-install.lock')
        again=self.next_connection()
        self.assertFalse(again.reuse_completed_install())
        with self.assertRaisesRegex(b.Stop,'RAM 安装锁已存在'):again.install()
        self.assertEqual(self.device.firmware_calls,1)
        self.assertIn('/t4-android-install.lock',self.device.directories)

    def test_changed_ram_package_is_not_reused(self):
        i=self.installer();i.check();i.install()
        self.device.files[i.ram+'/boot-set.pack']=b'different'
        again=self.next_connection()
        self.assertFalse(again.reuse_completed_install())
        self.assertEqual(self.device.firmware_calls,1)

    def test_unfinished_submission_cannot_be_reused(self):
        i=self.installer();i.check();i.install()
        state=self.base/'state/0x123.json'
        previous=json.loads(state.read_text());previous['status']='FIRMWARE_OUTCOME_UNKNOWN_KEEP_RAMDISK';b.save(state,previous)
        again=self.next_connection()
        self.assertFalse(again.reuse_completed_install())
        with self.assertRaises(b.Stop):again.install()
        self.assertEqual(self.device.firmware_calls,1)

    def test_reported_cold_boot_failure_is_not_reported_as_installed(self):
        i=self.installer();i.check();i.install()
        state=self.base/'state/0x123.json'
        previous=json.loads(state.read_text());previous['cold_boot_failed']=True;b.save(state,previous)
        again=self.next_connection()
        self.assertFalse(again.reuse_completed_install())
        self.assertEqual(self.device.firmware_calls,1)

    def test_corrupted_upload_aborts_before_firmware(self):
        i = self.installer();i.check();self.device.corrupt_upload = True
        with self.assertRaises(b.Stop):i.install()
        self.assertEqual(self.device.firmware_calls, 0)

    def test_prior_incomplete_firmware_blocks_new_attempt(self):
        state = self.base / 'state';state.mkdir()
        b.save(state / '0x123.json', dict(status='FIRMWARE_OUTCOME_UNKNOWN_KEEP_RAMDISK'))
        i = self.installer();i.check()
        with self.assertRaises(b.Stop):i.install()
        self.assertEqual(self.device.firmware_calls, 0)
        self.assertEqual(self.device.persistent_files, [])

    def test_firmware_error_keeps_audit_no_retry(self):
        i = self.installer();i.check();self.device.apply_ok = False
        with self.assertRaises(b.Stop):i.install()
        self.assertEqual(self.device.firmware_calls, 1)
        self.assertEqual(json.loads((self.base / 'state/0x123.json').read_text())['status'], 'FIRMWARE_INCOMPLETE_KEEP_RAMDISK')
        self.assertFalse(any('reboot' in c for c in self.device.commands))

    def test_timeout_is_unknown_and_no_retry(self):
        i = self.installer();i.check();self.device.apply_timeout = True
        with self.assertRaises(subprocess.TimeoutExpired):i.install()
        self.assertEqual(self.device.firmware_calls, 1)
        self.assertEqual(json.loads((self.base / 'state/0x123.json').read_text())['status'], 'FIRMWARE_OUTCOME_UNKNOWN_KEEP_RAMDISK')

    def test_ram_lock_blocks_concurrent_install(self):
        i = self.installer();i.check();self.device.directories.add('/t4-android-install.lock')
        with self.assertRaises(b.Stop):i.install()
        self.assertEqual(self.device.firmware_calls, 0)
        self.assertEqual(self.device.persistent_files, [])

    def test_tampered_payload_is_rejected_offline(self):
        (self.base / 'manifest.json').write_text(json.dumps(self.manifest))
        b.load_package(self.base)
        (self.base / 'payload/android.img3').write_bytes(b'changed')
        with self.assertRaises(b.Stop):b.load_package(self.base)


if __name__ == '__main__':
    unittest.main(verbosity=2)
