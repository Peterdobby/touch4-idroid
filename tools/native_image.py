"""N81AP native RAM image packaging for this project's pinned 4.1 iBSS.

Reuse phase1/native_jump.S and GNU assembler's exact alignment fill. Packaging
changes no payload bytes and does not prove that a payload itself can boot.
"""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
PAYLOAD_OFFSET = ALIGNMENT = 0x1000
LOAD_ADDRESS = 0x41000000
JUMP_TO = 0x8401496D
MAX_IMAGE_SIZE = 0x1000000
# Five ARM instructions, then their two literal values, from native_jump.S.
LAUNCHER = struct.pack('<7I', 0xE3A00000, 0xE59F1008, 0xE3A02000,
                       0xE59F3004, 0xE12FFF13,
                       LOAD_ADDRESS + PAYLOAD_OFFSET, JUMP_TO)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def validate_native(data, metadata=None):
    if len(data) <= PAYLOAD_OFFSET or not data.startswith(LAUNCHER):
        raise ValueError('Not an N81 native wrapped image; raw payloads cannot '
                         'be booted directly. Use tools/make-openiboot-native.py.')
    if len(data) % ALIGNMENT or len(data) > MAX_IMAGE_SIZE:
        raise ValueError('Native image size must be 0x1000 aligned and <=16 MiB')
    # GNU ARM GAS fills the start of this code alignment with NOPs, then zeros.
    header = LAUNCHER + bytes.fromhex('00f020e3') * 9
    if data[:PAYLOAD_OFFSET] != header.ljust(PAYLOAD_OFFSET, b'\0'):
        raise ValueError('Unexpected launcher/alignment bytes before payload')
    if data[PAYLOAD_OFFSET:].startswith(LAUNCHER):
        raise ValueError('Double-wrapped image refused')
    if metadata is not None:
        n = metadata['raw_size']
        if (metadata['payload_offset'] != PAYLOAD_OFFSET or
                metadata['wrapped_size'] != len(data) or
                not isinstance(n, int) or not 0 < n <= len(data)-PAYLOAD_OFFSET or
                (PAYLOAD_OFFSET+n+ALIGNMENT-1)//ALIGNMENT*ALIGNMENT != len(data)):
            raise ValueError('Invalid native metadata layout')
        extracted = data[PAYLOAD_OFFSET:PAYLOAD_OFFSET+n]
        if (sha256(data) != metadata['wrapped_sha256'] or
                sha256(extracted) != metadata['raw_sha256'] or
                metadata['raw_sha256'] != metadata['extracted_sha256']):
            raise ValueError('Native image/payload checksum mismatch')
    return data


def pack_native(raw_path, output_path, *, elf_path=None, cross=None):
    raw_path, output_path = Path(raw_path).resolve(), Path(output_path).resolve()
    if raw_path == output_path:
        raise ValueError('Input and output must differ; raw payload is preserved')
    raw = raw_path.read_bytes()
    if not raw or len(raw)+PAYLOAD_OFFSET > MAX_IMAGE_SIZE:
        raise ValueError('Raw payload must be nonempty and fit the 16 MiB window')
    if raw.startswith((LAUNCHER, b'\x7fELF', b'3gmI', b'Img3')):
        raise ValueError('Expected raw payload, not native wrapper/ELF/IMG3')
    cross = cross or os.environ.get('CROSS', str(ROOT/'saved/toolchain/arm-eabi-4.8/bin/arm-eabi-'))
    with tempfile.TemporaryDirectory(prefix='t4-native-') as temporary:
        tmp = Path(temporary)
        (tmp/'openiboot.bin').write_bytes(raw)
        subprocess.run([cross+'gcc', '-nostdlib', '-fno-use-linker-plugin',
                        '-mcpu=cortex-a8', '-marm', '-Wl,-Ttext=0x41000000',
                        '-Wl,--build-id=none', '-o', str(tmp/'native.elf'),
                        str(ROOT/'phase1/native_jump.S')], cwd=tmp, check=True)
        subprocess.run([cross+'objcopy', '-O', 'binary', str(tmp/'native.elf'),
                        str(tmp/'native.bin')], check=True)
        image = (tmp/'native.bin').read_bytes()
        validate_native(image)
        extracted = image[PAYLOAD_OFFSET:PAYLOAD_OFFSET+len(raw)]
        if extracted != raw:
            raise ValueError('Assembler modified/truncated the raw payload')
        metadata = dict(raw_size=len(raw), wrapped_size=len(image),
                        payload_offset=PAYLOAD_OFFSET,
                        padding_size=len(image)-PAYLOAD_OFFSET-len(raw),
                        alignment=ALIGNMENT, load_address=LOAD_ADDRESS,
                        entry_address=LOAD_ADDRESS+PAYLOAD_OFFSET,
                        ibss_jump_to_thumb=JUMP_TO,
                        raw_sha256=sha256(raw), extracted_sha256=sha256(extracted),
                        wrapped_sha256=sha256(image))
        validate_native(image, metadata)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image)
        Path(str(output_path)+'.json').write_text(json.dumps(metadata, indent=2)+'\n')
        if elf_path is not None:
            Path(elf_path).write_bytes((tmp/'native.elf').read_bytes())
    return metadata


def compare_native(image, reference, raw_size):
    """Return exact differing byte counts by wrapper/payload/tail region."""
    cuts = [('wrapper', 0, PAYLOAD_OFFSET),
            ('payload', PAYLOAD_OFFSET, PAYLOAD_OFFSET+raw_size),
            ('tail padding', PAYLOAD_OFFSET+raw_size, max(len(image), len(reference)))]
    return {name: sum(a != b for a, b in zip(image[lo:hi], reference[lo:hi]))
                  + abs(len(image[lo:hi])-len(reference[lo:hi]))
            for name, lo, hi in cuts}
