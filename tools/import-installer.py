#!/usr/bin/env python3
"""Verify and import an owned 02.4 installer into saved/. No device access."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'T4-Android-Installer-02'
MAX_TOTAL = 256 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def import_package(archive, destination):
    require(not destination.exists() and not destination.is_symlink(),
            'Destination already exists and will be preserved: ' + str(destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        entries = z.infolist()
        require(sum(i.file_size for i in entries) <= MAX_TOTAL and len(entries) <= 2000,
                'Package exceeds the size or file count limit')
        names = set()
        for item in entries:
            path = PurePosixPath(item.filename)
            require(not path.is_absolute() and '..' not in path.parts and path.parts
                    and path.parts[0] == PREFIX and '\\' not in item.filename,
                    'Invalid package path: ' + item.filename)
            require(not stat.S_ISLNK(item.external_attr >> 16), 'Package contains a symbolic link')
            require(item.filename not in names, 'Package contains duplicate paths')
            names.add(item.filename)
        manifest = json.loads(z.read(PREFIX + '/manifest.json'))
        require(manifest.get('revision') == '02.4' and manifest.get('model') == 'iPod4,1',
                'Only installer 02.4 for iPod4,1 is accepted')
        expected = set(manifest['files']) | {'manifest.json'}
        actual = {str(PurePosixPath(i.filename).relative_to(PREFIX))
                  for i in entries if not i.is_dir()}
        require(actual == expected, 'Package files do not match the manifest')
        for name, record in manifest['files'].items():
            data = z.read(PREFIX + '/' + name)
            require(len(data) == record['size'] and hashlib.sha256(data).hexdigest() == record['sha256'],
                    'Package checksum failed: ' + name)
        with tempfile.TemporaryDirectory(prefix='.t4-import-', dir=destination.parent) as temporary:
            stage = Path(temporary) / PREFIX
            for item in entries:
                target = Path(temporary) / item.filename
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(z.read(item))
                    target.chmod((item.external_attr >> 16) & 0o777 or 0o644)
            # The parent may be an existing local path; the package itself never
            # follows archive-supplied symlinks or replaces an installed package.
            require(not destination.exists() and not destination.is_symlink(), 'Destination appeared during import; refusing to overwrite')
            os.rename(stage, destination)
    print('Local package verified and imported: ' + str(destination))
    print('Original device identity checks remain enabled; importing did not connect to the device.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive', type=Path)
    p.add_argument('--destination', type=Path, default=ROOT / 'saved/packages' / PREFIX)
    args = p.parse_args()
    import_package(args.archive, args.destination.absolute())


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as error:
        print('Stopped: ' + str(error), file=sys.stderr)
        sys.exit(1)
