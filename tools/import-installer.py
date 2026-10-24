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
            '目标已经存在，保留原目录：' + str(destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        entries = z.infolist()
        require(sum(i.file_size for i in entries) <= MAX_TOTAL and len(entries) <= 2000,
                '安装包超出允许大小或文件数')
        names = set()
        for item in entries:
            path = PurePosixPath(item.filename)
            require(not path.is_absolute() and '..' not in path.parts and path.parts
                    and path.parts[0] == PREFIX and '\\' not in item.filename,
                    '安装包路径非法：' + item.filename)
            require(not stat.S_ISLNK(item.external_attr >> 16), '安装包包含软链接')
            require(item.filename not in names, '安装包包含重复路径')
            names.add(item.filename)
        manifest = json.loads(z.read(PREFIX + '/manifest.json'))
        require(manifest.get('revision') == '02.4' and manifest.get('model') == 'iPod4,1',
                '仅导入已说明的 02.4 / iPod4,1 包')
        expected = set(manifest['files']) | {'manifest.json'}
        actual = {str(PurePosixPath(i.filename).relative_to(PREFIX))
                  for i in entries if not i.is_dir()}
        require(actual == expected, '安装包文件集合与清单不匹配')
        for name, record in manifest['files'].items():
            data = z.read(PREFIX + '/' + name)
            require(len(data) == record['size'] and hashlib.sha256(data).hexdigest() == record['sha256'],
                    '安装包文件校验失败：' + name)
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
            require(not destination.exists() and not destination.is_symlink(), '目标在导入期间出现，停止覆盖')
            os.rename(stage, destination)
    print('本机安装包已校验并导入：' + str(destination))
    print('设备身份仍由原安装包校验；导入没有连接或修改设备。')


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
        print('停止：' + str(error), file=sys.stderr)
        sys.exit(1)
