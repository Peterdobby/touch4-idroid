#!/usr/bin/env python3
"""Automatic iOS 4/5/6 component preparation and persistent MENU04 installer."""
import argparse
import datetime
import json
import plistlib
import shlex
import struct
import subprocess
import sys
import uuid
from pathlib import Path
import base_backend as core
import profiles

BASE = Path(__file__).resolve().parent


def identify(remote, manifest, log):
    mounts = remote.run('/sbin/mount').stdout
    core.require(b'/dev/md0 on / ' in mounts, '请先进入 Kit SSH ramdisk')
    if b'/dev/disk0s1s1 on /mnt1 ' not in mounts:
        remote.run('/bin/mkdir -p /mnt1 && /sbin/mount_hfs -o ro /dev/disk0s1s1 /mnt1')
    root_line = next(x for x in mounts.splitlines() if b'/dev/md0 on / ' in x)
    if b'read-only' in root_line:
        remote.run('/sbin/mount -u -w /')  # verified md0 RAM filesystem only
    temporary = core.Installer(remote, manifest, BASE, log, log / 'unused')
    probe = temporary.ram_upload('device-info', (BASE / 'payload/device-info').read_bytes(), True)
    device = core.read_identity(remote, probe, log, 'identify-device-info')
    core.require(device['machine'] == manifest['model'] and int(manifest['ecid'], 0) in [int(x, 0) for x in device['ecid_candidates']], '本测试包的设备型号或 ECID 不匹配')
    version = plistlib.loads(remote.read('/mnt1/System/Library/CoreServices/SystemVersion.plist'))
    print('检测到主系统：iOS %s / %s' % (version['ProductVersion'], version['ProductBuildVersion']), flush=True)
    return version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['verify', 'check', 'install', 'prepare'])
    parser.add_argument('--version', help='Offline prepare only; installed version is read automatically for install')
    parser.add_argument('--build')
    parser.add_argument('--port', type=int, default=6414)
    parser.add_argument('--kit', type=Path)
    parser.add_argument('--state-dir', type=Path, default=Path.home() / 'Library/Application Support/T4-Android-Installer-02')
    args = parser.parse_args()
    core.require(1 <= args.port <= 65535, 'SSH 端口范围错误')
    manifest = core.load_package(BASE)
    print('安装工具 02.4 文件校验通过。', flush=True)
    if args.action == 'verify':
        return
    if args.action == 'prepare':
        core.require(args.version, '离线准备需要 --version，例如 --version 5.1.1')
        directory = profiles.prepare(BASE, args.state_dir / 'profiles', args.version, args.build, args.kit)
        print('配置目录：' + str(directory));return
    core.require(not args.version and not args.build, '安装时自动读取主系统，不接受手动覆盖版本')
    core.require(sys.platform == 'darwin', '首版主机环境为 macOS')
    log = args.state_dir / 'logs' / (datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6])
    log.mkdir(parents=True)
    remote = core.SSH(args.port, args.kit, log)
    try:
        remote.connect()
        version = identify(remote, manifest, log)
        number, build = version['ProductVersion'], version['ProductBuildVersion']
        if number.startswith(('4.', '5.', '6.')):
            directory = profiles.prepare(BASE, args.state_dir / 'profiles', number, build, args.kit)
            selected = profiles.verify_profile(directory)
            profile = selected['profiles'][0]
            # Preserve the existing kernel produced by the owner's Kit install.
            # Its digest is captured now, then rechecked immediately before NOR.
            kernel = remote.read('/mnt1' + profile['kernel_path'])
            core.require(len(kernel) > 1024 and kernel[:4] in [b'3gmI', b'comp', b'\xce\xfa\xed\xfe'], '现有 kernelcache 格式不受支持；保留原文件并停止')
            profile['kernel_sha256'] = [core.sha(kernel)]
            core.save(log / 'SELECTED-PROFILE.json', dict(version=number, build=build,
                       kernel_sha256=core.sha(kernel), profile=str(directory), hardware_tested=False,
                       experimental_persistent_install_explicitly_authorized=True))
            print('使用匹配版本的 Kit iBoot；这份持久入口待首次实机验证。', flush=True)
        else:
            core.require(number == '7.1.2' and build == '11D257', '只处理 iOS 4/5/6，以及原已验证的 7.1.2 配置')
            directory, selected = BASE, manifest
        installer = core.Installer(remote, selected, directory, log, args.state_dir / 'devices')
        info = installer.check()
        print('本次日志：' + str(log), flush=True)
        if args.action == 'install':
            if installer.reuse_completed_install():
                return
            print('\n将持久安装 iOS / Android / Console 菜单，新增启动文件并更新完整启动镜像组。')
            print('原 iOS 内核、系统与用户文件保留；不擦除、不分区、不写 NVRAM。')
            if input('确认安装到本机 iOS %s (%s)？[y/N]: ' % (info['version'], info['build'])).strip().lower() != 'y':
                print('已取消，没有执行持久写入。');return
            installer.install()
    except BaseException as error:
        core.save(log / 'ERROR.json', dict(type=type(error).__name__, message=str(error)))
        raise
    finally:
        remote.close()


if __name__ == '__main__':
    try:
        main()
    except (core.Stop, profiles.ProfileError, OSError, ValueError, KeyError, StopIteration, subprocess.TimeoutExpired) as error:
        print('\n停止：' + str(error), file=sys.stderr);sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        print('\n已中断；如已提交固件，请保持 ramdisk 并查看日志。', file=sys.stderr);sys.exit(130)
