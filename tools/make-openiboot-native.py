#!/usr/bin/env python3
"""Wrap an unchanged N81 raw OpeniBoot payload; no USB or storage operations."""
import argparse
from pathlib import Path
from native_image import compare_native, pack_native


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--reference', type=Path, help='compare with an existing native binary')
    args = parser.parse_args()
    try:
        m = pack_native(args.raw, args.output)
    except (OSError, ValueError) as error:
        parser.exit(2, str(error)+'\n')
    for label, key in [('raw size', 'raw_size'), ('wrapped size', 'wrapped_size'),
                       ('payload offset', 'payload_offset'), ('padding size', 'padding_size')]:
        print(f'{label}: {m[key]} ({m[key]:#x})')
    print('SHA256(raw):', m['raw_sha256'])
    print('SHA256(extracted payload):', m['extracted_sha256'])
    print('SHA256(wrapped):', m['wrapped_sha256'])
    print('PAYLOAD_UNCHANGED')
    if args.reference:
        generated, reference = args.output.read_bytes(), args.reference.read_bytes()
        if generated == reference:
            print('NATIVE_REPRODUCTION_EXACT')
        else:
            print('NATIVE_REPRODUCTION_DIFFERENT:',
                  compare_native(generated, reference, m['raw_size']))
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
