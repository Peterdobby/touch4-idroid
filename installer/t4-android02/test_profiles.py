#!/usr/bin/env python3
"""Offline recipe/cache checks, including execution of the C updater with fake IOKit."""
import importlib.util
import json
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest import mock
import zlib
from pathlib import Path
import profiles as p


def img(kind, payload=b'fixture'):
    body = struct.pack('<3I', 0x44415441, 12+len(payload), len(payload))+payload
    return struct.pack('<5I',0x496d6733,20+len(body),len(body),0,kind)+body


class Profiles(unittest.TestCase):
    def test_kit_success_exit_one_requires_complete_new_output(self):
        log=b'main: Writing out patched file to target...\nmain: Quitting...\n'
        self.assertTrue(p.patcher_result_ok(1,log,True))
        self.assertFalse(p.patcher_result_ok(1,log,False))
        self.assertFalse(p.patcher_result_ok(1,b'patch failed',True))
        self.assertFalse(p.patcher_result_ok(2,log,True))

    def test_511_recipe_uses_existing_kit_switches(self):
        flags=p.patch_flags('5.1.1')
        self.assertIn('--logo',flags);self.assertNotIn('--433',flags)
        self.assertIn('--boot-partition',flags);self.assertIn('--boot-ramdisk',flags)

    def test_ios4_recipe_boundary(self):
        self.assertIn('--433',p.patch_flags('4.3.3'))
        self.assertNotIn('--433',p.patch_flags('4.3.5'))
        self.assertIn('--logo4',p.patch_flags('4.1'))

    def test_ios6_uses_native_target_not_ios7_tree(self):
        self.assertIn('--logo',p.patch_flags('6.1.6'))
        self.assertNotIn('--logo4',p.patch_flags('6.1.6'))

    def test_rejects_unsupported_or_injected_version(self):
        for value in ['7.1.2','5.1.1; echo bad','../9B206','5.1.1b1']:
            with self.assertRaises(p.ProfileError):p.patch_flags(value)

    def test_apple_download_domain_only(self):
        self.assertEqual(p.apple_url('http://appldnld.apple.com/a.ipsw'),'https://appldnld.apple.com/a.ipsw')
        for value in ['https://apple.com.evil.test/a','file:///tmp/a','https://evil.test/a']:
            with self.assertRaises(p.ProfileError):p.apple_url(value)

    def test_image3_rejects_truncated_tag(self):
        data=bytearray(img(0x69626f62));struct.pack_into('<I',data,24,0xffffffff)
        with self.assertRaises(p.ProfileError):p.image_data(data)

    def test_wrong_image_type_refused(self):
        with self.assertRaises(p.ProfileError):p.image_data(img(0x64747265),0x69626f62)

    def test_manifest_cache_corruption_refused(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);(base/'part').write_bytes(b'original')
            (base/'manifest.json').write_text(json.dumps(dict(files={'part':dict(size=8,sha256=p.sha(b'original'))})))
            p.verify_profile(base);(base/'part').write_bytes(b'damaged!')
            with self.assertRaises(p.ProfileError):p.verify_profile(base)

    def test_cached_probe_upgrade_preserves_other_hardlinks(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);base=root/'package';cache=root/'cache'
            (base/'payload').mkdir(parents=True);(cache/'payload').mkdir(parents=True)
            (base/'payload/device-info').write_bytes(b'new-probe')
            old=root/'frozen-probe';old.write_bytes(b'old-probe')
            p.link_or_copy(old,cache/'payload/device-info')
            (cache/'manifest.json').write_text(json.dumps(dict(files={'payload/device-info':dict(size=9,sha256=p.sha(b'old-probe'))})))
            with mock.patch.object(p,'OLD_IDENTITY_SHA256',p.sha(b'old-probe')):
                p.refresh_cached_identity(base,cache)
            self.assertEqual(old.read_bytes(),b'old-probe')
            self.assertEqual((cache/'payload/device-info').read_bytes(),b'new-probe')
            p.verify_profile(cache)

    def test_corrupt_cached_probe_not_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'payload').mkdir()
            f=root/'payload/device-info';f.write_bytes(b'bad-probe')
            (root/'manifest.json').write_text(json.dumps(dict(files={'payload/device-info':dict(size=9,sha256=p.sha(b'old-probe'))})))
            with self.assertRaises(p.ProfileError):p.refresh_cached_identity(root,root)
            self.assertEqual(f.read_bytes(),b'bad-probe')


FAKE=r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
unsigned int mach_task_self_=1;
static unsigned int step;
int sysctlbyname(const char*a,void*b,unsigned long*c,void*d,unsigned long e){strcpy(b,"iPod4,1");return 0;}
const void *IOServiceMatching(const char*a){return (void*)1;}
unsigned int IOServiceGetMatchingService(unsigned int a,const void*b){puts("MOCK_SERVICE_OPENED");return 1;}
int IOServiceOpen(unsigned int a,unsigned int b,unsigned int c,unsigned int*d){*d=2;return 0;}
int IOServiceClose(unsigned int a){if(step!=8)abort();return 0;}
int IOObjectRelease(unsigned int a){return 0;}
int IOConnectCallStructMethod(unsigned int a,unsigned int sel,const void*b,unsigned long n,void*c,unsigned long*d){
 unsigned int expected=step==0?2:step==1?0:1;
 if(sel!=expected || step>=8)abort();step++;return 0;
}
'''


class Updater(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.work=Path(cls.tmp.name)
        (cls.work/'fake.c').write_text(FAKE)
        cls.exe=cls.work/'updater'
        subprocess.run(['clang','-Wno-deprecated-non-prototype',str(Path(__file__).with_name('apply-set-generic.c')),str(cls.work/'fake.c'),'-o',str(cls.exe)],check=True,capture_output=True)
        kinds=[0x696c6c62,0x69626f74,0x64747265,0x6c6f676f,0x7265636d,0x69626f62,0x53434142]
        cls.pack=p.package_set([img(k) for k in kinds])

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def run_blob(self,blob,exit_code,opened=False,args=True):
        path=self.work/'test.pack';path.write_bytes(blob)
        command=[str(self.exe)]+(['--apply'] if args else [])+[str(path)]
        r=subprocess.run(command,capture_output=True)
        self.assertEqual(r.returncode,exit_code,r.stderr)
        self.assertEqual(b'MOCK_SERVICE_OPENED' in r.stdout,opened)

    def test_complete_group_llb_first(self):self.run_blob(self.pack,0,True)

    def test_corrupt_package_no_iokit(self):
        b=bytearray(self.pack);b[-1]^=1;self.run_blob(b,8)

    def test_truncation_no_iokit(self):self.run_blob(self.pack[:-3],8)

    def test_missing_apply_flag_no_iokit(self):self.run_blob(self.pack,2,args=False)

    def test_wrong_selector_even_with_valid_crc(self):
        b=bytearray(self.pack);struct.pack_into('<I',b,16,1);struct.pack_into('<I',b,12,zlib.crc32(b[16:]));self.run_blob(b,11)

    def test_length_overflow_even_with_valid_crc(self):
        b=bytearray(self.pack);struct.pack_into('<I',b,20,0xfffffff0);struct.pack_into('<I',b,12,zlib.crc32(b[16:]));self.run_blob(b,11)

    def test_oversized_input_no_iokit(self):self.run_blob(bytes(0x180001),7)


class BaseFirmware(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.base=self.root/'package';self.profile=self.root/'cache/9B206'
        (self.base/'payload/base-images').mkdir(parents=True)
        (self.profile/'payload').mkdir(parents=True)
        kinds=[0x696c6c62,0x69626f74,0x64747265,0x6c6f676f,0x7265636d,0x69626f62,0x53434142]
        self.expected=[img(k,('base'+str(i)).encode()) for i,k in enumerate(kinds)]
        names=[str(i)+'.img3' for i in range(7)]
        (self.base/'payload/base-images.json').write_text(json.dumps(dict(order=names)))
        for n,blob in zip(names,self.expected):(self.base/'payload/base-images'/n).write_bytes(blob)
        self.menu=img(0x69626f62,b'owned-menu');self.target=img(0x64747265,b'target-dt')
        (self.profile/'payload/menu.img3').write_bytes(self.menu)
        (self.profile/'payload/target-dt.img3').write_bytes(self.target)
        (self.profile/'PROVENANCE.json').write_text('{}')

    def write_profile(self,images):
        data=p.package_set(images)
        (self.profile/'payload/boot-set.pack').write_bytes(data)
        files={str(x.relative_to(self.profile)):dict(size=x.stat().st_size,sha256=p.sha(x.read_bytes()))
               for x in self.profile.rglob('*') if x.is_file() and x.name!='manifest.json'}
        (self.profile/'manifest.json').write_text(json.dumps(dict(files=files)))
        return data

    def test_old_target_dt_mix_is_backed_up_and_repaired(self):
        images=list(self.expected);images[2]=self.target;images[5]=self.menu
        old=self.write_profile(images);p.ensure_base_firmware(self.base,self.profile)
        actual=p.unpack_set((self.profile/'payload/boot-set.pack').read_bytes())
        self.assertEqual(actual[2],self.expected[2]);self.assertEqual(actual[5],self.menu)
        self.assertTrue(all(actual[i]==self.expected[i] for i in [0,1,2,3,4,6]))
        backup=self.profile.parent/'.history'/self.profile.name/p.sha(old)
        self.assertEqual((backup/'payload/boot-set.pack').read_bytes(),old)
        p.verify_profile(self.profile)

    def test_matching_base_group_is_not_rewritten(self):
        images=list(self.expected);images[5]=self.menu
        old=self.write_profile(images);p.ensure_base_firmware(self.base,self.profile)
        self.assertEqual((self.profile/'payload/boot-set.pack').read_bytes(),old)
        self.assertFalse((self.profile.parent/'.history').exists())

    def test_other_firststage_changes_are_not_silently_repaired(self):
        images=list(self.expected);images[0]=img(0x696c6c62,b'unknown-llb');images[2]=self.target;images[5]=self.menu
        old=self.write_profile(images)
        with self.assertRaises(p.ProfileError):p.ensure_base_firmware(self.base,self.profile)
        self.assertEqual((self.profile/'payload/boot-set.pack').read_bytes(),old)

    def test_unknown_dt_is_not_silently_repaired(self):
        images=list(self.expected);images[2]=img(0x64747265,b'unknown-dt');images[5]=self.menu
        old=self.write_profile(images)
        with self.assertRaises(p.ProfileError):p.ensure_base_firmware(self.base,self.profile)
        self.assertEqual((self.profile/'payload/boot-set.pack').read_bytes(),old)


if __name__=='__main__':unittest.main(verbosity=2)
