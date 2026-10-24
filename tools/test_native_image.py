"""Offline regression checks; never opens USB."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from native_image import (ALIGNMENT, LAUNCHER, PAYLOAD_OFFSET, ROOT,
                          compare_native, pack_native, sha256, validate_native)

CROSS = os.environ.get('CROSS', str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-'))
HAS_TOOLCHAIN = all(shutil.which(CROSS + name) for name in ('gcc', 'objcopy'))
REFERENCES = Path(os.environ.get('T4_REFERENCE_BUILD_DIR', str(ROOT/'saved/build')))
REFERENCE_NAMES = ('phase1-published', 'T4_DIAG_01', 'T4_MENU_01')
HAS_REFERENCES = all((REFERENCES/name/file).is_file()
                     for name in REFERENCE_NAMES
                     for file in ('openiboot.bin', 'openiboot-native.bin'))


class NativeImageTests(unittest.TestCase):
    @unittest.skipUnless(HAS_TOOLCHAIN and HAS_REFERENCES,
                         'Optional integration check needs CROSS and private reference images')
    def test_existing_images_reproduce_exactly(self):
        with tempfile.TemporaryDirectory() as d:
            for name in REFERENCE_NAMES:
                with self.subTest(name=name):
                    source = REFERENCES/name
                    out = Path(d)/(name+'.bin')
                    m = pack_native(source/'openiboot.bin', out, cross=CROSS)
                    self.assertEqual(out.read_bytes(), (source/'openiboot-native.bin').read_bytes())
                    self.assertEqual(m['raw_sha256'], m['extracted_sha256'])

    @unittest.skipUnless(HAS_TOOLCHAIN, 'Optional assembler check needs CROSS')
    def test_alignment_boundaries_and_reject_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            raw, out = Path(d)/'raw.bin', Path(d)/'native.bin'
            for n in (4095, 4096, 4097):
                with self.subTest(n=n):
                    payload = bytes(i % 251 for i in range(n))
                    raw.write_bytes(payload)
                    m = pack_native(raw, out, cross=CROSS)
                    image = out.read_bytes()
                    self.assertEqual(len(image), (n+4096+4095)//4096*4096)
                    self.assertEqual(image[4096:4096+n], payload)
                    validate_native(image, m)
                    damaged = bytearray(image)
                    damaged[4096] ^= 1
                    with self.assertRaises(ValueError):
                        validate_native(bytes(damaged), m)
                    self.assertEqual(compare_native(image, bytes(damaged), n),
                                     {'wrapper': 0, 'payload': 1, 'tail padding': 0})
            with self.assertRaises(ValueError):
                pack_native(out, Path(d)/'double.bin', cross=CROSS)

    def test_validation_rejects_wrapper_payload_and_layout_corruption(self):
        payload = b'public source-only validation fixture' * 43
        wrapper = (LAUNCHER + bytes.fromhex('00f020e3') * 9).ljust(PAYLOAD_OFFSET, b'\0')
        image = (wrapper + payload).ljust(
            (PAYLOAD_OFFSET + len(payload) + ALIGNMENT - 1)//ALIGNMENT*ALIGNMENT, b'\0')
        metadata = dict(raw_size=len(payload), wrapped_size=len(image),
                        payload_offset=PAYLOAD_OFFSET, raw_sha256=sha256(payload),
                        extracted_sha256=sha256(payload), wrapped_sha256=sha256(image))
        self.assertEqual(validate_native(image, metadata), image)
        for offset in (0, 100, PAYLOAD_OFFSET, len(image)-1):
            with self.subTest(offset=offset):
                damaged = bytearray(image)
                damaged[offset] ^= 1
                with self.assertRaises(ValueError):
                    validate_native(bytes(damaged), metadata)
        with self.assertRaises(ValueError):
            validate_native(image, dict(metadata, payload_offset=0))
        with self.assertRaises(ValueError):
            validate_native(image[:-1])
        with self.assertRaises(ValueError):
            validate_native(wrapper + image)

    def test_raw_refused_before_usb_access(self):
        with tempfile.TemporaryDirectory() as d:
            raw = Path(d)/'raw.bin'
            raw.write_bytes(b'\0' * 4096)
            p = subprocess.run([sys.executable, str(ROOT/'phase1/run.py'), '--boot',
                                '--file', str(raw)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)
        self.assertIn('before USB access', p.stderr)
        self.assertIn('raw payloads cannot be booted directly', p.stderr)


if __name__ == '__main__':
    unittest.main()
