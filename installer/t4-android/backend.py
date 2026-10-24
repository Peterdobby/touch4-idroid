#!/usr/bin/env python3
"""Packaged owner-specific MENU03 installer, using an existing Kit SSH ramdisk.

No exploit invocation, partition changes, OS replacement or NVRAM setters.
Installation reuses the exact successful complete Apple boot-image updater.
"""
import argparse
import datetime
import getpass
import hashlib
import json
import os
import plistlib
import shlex
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

BASE = Path(__file__).resolve().parent
BOOTRAMDISK = '/a/b/c/d/e/f/g/h/i/j/k/l/m/n/o/p/q/r/s/t/u/v/w/x/y/z/0/1/2/3/4/5/6/7/8/9/A/B/C/disk.dmg'


class Stop(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Stop(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.partial')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(temporary, path)


def load_package(base=BASE):
    manifest = json.loads((base / 'manifest.json').read_text())
    for name, item in manifest['files'].items():
        path = base / name
        require(path.resolve().is_relative_to(base.resolve()), '安装包包含非法路径')
        data = path.read_bytes()
        require(len(data) == item['size'] and sha(data) == item['sha256'], '安装包校验失败：' + name)
    return manifest


class SSH:
    def __init__(self, port, kit, log):
        self.port, self.kit, self.log = port, kit, log
        self.tmp = tempfile.TemporaryDirectory(prefix='t4i-', dir='/tmp')
        self.options = ['-T', '-o', 'HostKeyAlgorithms=+ssh-rsa', '-o', 'StrictHostKeyChecking=accept-new',
                        '-o', 'UserKnownHostsFile=' + str(log / 'known_hosts'), '-o', 'ConnectTimeout=5',
                        '-o', 'ControlPath=' + self.tmp.name + '/ssh', '-p', str(port), 'root@127.0.0.1']

    def connect(self):
        try:
            with socket.create_connection(('127.0.0.1', self.port), timeout=2):
                pass
        except OSError as e:
            raise Stop('SSH 转发未就绪。请在 Kit 进入 SSH ramdisk，保持端口转发，然后重试。') from e
        command = ['ssh', '-o', 'BatchMode=yes', '-o', 'ControlMaster=yes', '-o', 'ControlPersist=600'] + self.options + ['/sbin/mount']
        p = subprocess.run(command, capture_output=True, timeout=12)
        if p.returncode:
            candidates = []
            if self.kit:
                candidates.append(Path(self.kit) / 'bin/macos/sshpass')
            if os.environ.get('T4_KIT_DIR'):
                candidates.append(Path(os.environ['T4_KIT_DIR']) / 'bin/macos/sshpass')
            candidates += sorted((Path.home() / 'Desktop').glob('**/Legacy-iOS-Kit*/bin/macos/sshpass'))
            executable = next((str(p) for p in candidates if p.is_file()), shutil.which('sshpass'))
            require(executable, '找不到 sshpass。请在菜单 3 设置现有 Kit 文件夹路径。')
            password = os.environ.get('T4_SSH_PASSWORD')
            if password is None:
                password = getpass.getpass('SSH ramdisk 密码: ')
            command = [executable, '-e', 'ssh', '-o', 'ControlMaster=yes', '-o', 'ControlPersist=600'] + self.options + ['/sbin/mount']
            env = dict(os.environ, SSHPASS=password)
            p = subprocess.run(command, env=env, capture_output=True, timeout=18)
        (self.log / 'ssh-connect.log').write_bytes(p.stdout + p.stderr)
        require(p.returncode == 0, 'SSH 登录失败，详见 ' + str(self.log / 'ssh-connect.log'))
        require(b'/dev/md0 on / ' in p.stdout, '当前是普通系统，未进入 SSH ramdisk；没有执行安装。')

    def run(self, command, data=None, timeout=60, allow_error=False):
        p = subprocess.run(['ssh', '-o', 'BatchMode=yes'] + self.options + [command], input=data,
                           capture_output=True, timeout=timeout)
        if p.returncode and not allow_error:
            raise Stop('设备操作失败：' + command + '\n' + p.stderr.decode(errors='replace')[-600:])
        return p

    def read(self, path):
        return self.run('/bin/cat ' + shlex.quote(path)).stdout

    def close(self):
        subprocess.run(['ssh', '-o', 'BatchMode=yes', '-O', 'exit'] + self.options,
                       capture_output=True, timeout=8)
        self.tmp.cleanup()


class Installer:
    def __init__(self, remote, manifest, base, log, state):
        self.r, self.m, self.base, self.log, self.state = remote, manifest, base, log, state
        # Direct child of the verified md0 root; /var can be redirected by a
        # ramdisk's mount scripts, so do not assume that /var/tmp is RAM.
        self.ram = '/t4-installer-' + uuid.uuid4().hex[:12]
        self.info = None

    def blob(self, name):
        return (self.base / name).read_bytes()

    def ram_upload(self, name, data, executable=False):
        path = self.ram + '/' + name
        self.r.run('/bin/mkdir -p ' + shlex.quote(self.ram))
        self.r.run('/bin/cat > ' + shlex.quote(path), data)
        require(self.r.read(path) == data, 'RAM 文件回读不一致：' + name)
        if executable:
            self.r.run('/bin/chmod 700 ' + shlex.quote(path))
        return path

    def check(self):
        mounts = self.r.run('/sbin/mount').stdout
        require(b'/dev/md0 on / ' in mounts, '必须在 SSH ramdisk 下运行')
        if b'/dev/disk0s1s1 on /mnt1 ' not in mounts:
            self.r.run('/bin/mkdir -p /mnt1 && /sbin/mount_hfs -o ro /dev/disk0s1s1 /mnt1')
            mounts = self.r.run('/sbin/mount').stdout
        require(b'/dev/disk0s1s1 on /mnt1 ' in mounts, '系统卷挂载位置不匹配')
        identity = self.ram_upload('device-info', self.blob('payload/device-info'), True)
        identity_result = self.r.run(shlex.quote(identity), allow_error=True)
        require(identity_result.returncode == 0, '未能读取设备 ECID；停止，未写持久存储')
        device = json.loads(identity_result.stdout)
        require(device['machine'] == 'iPod4,1', '本工具只适配 iPod touch 4G')
        require(int(self.m['ecid'], 0) in [int(x, 0) for x in device['ecid_candidates']],
                '设备 ECID 与当前签名包不匹配；此测试包仅用于已验证的这台 iPod')
        version_data = self.r.read('/mnt1/System/Library/CoreServices/SystemVersion.plist')
        version = plistlib.loads(version_data)
        print('自动识别：%s / iOS %s (%s)' % (device['machine'], version['ProductVersion'], version['ProductBuildVersion']), flush=True)
        self.log.joinpath('SystemVersion.plist').write_bytes(version_data)
        profile = next((p for p in self.m['profiles'] if p['version'] == version['ProductVersion'] and p['build'] == version['ProductBuildVersion']), None)
        require(profile is not None, '已识别该系统，但本测试版没有经过验证的匹配配置；停止安装。')
        kernel = self.r.read('/mnt1' + profile['kernel_path'])
        require(sha(kernel) in profile['kernel_sha256'], '系统版本已识别，但内核与已验证配置不匹配；停止安装。')
        self.log.joinpath('original-kernelcache').write_bytes(kernel)
        nvram = self.r.run('/usr/sbin/nvram -p').stdout
        values = dict(line.split(b'\t', 1) for line in nvram.splitlines() if b'\t' in line)
        require(values.get(b'boot-partition') == b'2' and values.get(b'boot-ramdisk') == BOOTRAMDISK.encode(),
                '未识别到匹配的 Kit DRA6 启动环境；本工具不修改 NVRAM。')
        dra = self.r.run('/bin/dd if=/dev/rdisk0s1s3 bs=16384 count=32').stdout
        require(len(dra) == 524288 and sha(dra) == self.m['dra_sha256'], 'DRA6 分区与已验证输入不匹配；停止安装。')
        self.log.joinpath('nvram-before.txt').write_bytes(nvram)
        self.log.joinpath('existing-dra.bin').write_bytes(dra)
        llb = self.ram_upload('LLB.img3', self.blob('payload/LLB.img3'))
        probe = self.ram_upload('check-llb', self.blob('payload/check-llb'), True)
        result = self.r.run(shlex.quote(probe) + ' ' + shlex.quote(llb), allow_error=True)
        self.log.joinpath('signed-llb-check.log').write_bytes(result.stdout + result.stderr)
        require(result.returncode == 0 and b'result=00000000' in result.stdout, '签名启动镜像预检查未通过；没有执行持久写入。')
        self.r.run('test -d /mnt1/boot && test ! -L /mnt1/boot')
        self.r.run('test ! -L /mnt1/boot/t4')
        existing, needed = {}, 0
        for item in self.m['runtime_files']:
            dest = '/mnt1' + item['destination']
            self.r.run('test ! -L ' + shlex.quote(dest))
            found = self.r.run('test -e ' + shlex.quote(dest), allow_error=True).returncode == 0
            if found:
                data = self.r.read(dest)
                require(sha(data) == self.m['files'][item['source']]['sha256'], '已有同名启动文件内容不同，保留原文件并停止：' + dest)
                self.log.joinpath(Path(dest).name + '.existing.sha256').write_text(sha(data) + '\n')
            else:
                needed += self.m['files'][item['source']]['size']
            existing[dest] = found
        header = self.r.run('/bin/dd if=/dev/rdisk0s1s1 bs=8192 count=1').stdout
        require(len(header) == 8192 and header[1024:1026] in [b'H+', b'HX'], '不是已支持的 HFS 系统卷')
        block_size, total, free = struct.unpack_from('>III', header, 1024+40)
        require(0 < block_size <= 1048576 and free <= total, 'HFS 空间信息异常')
        require(block_size * free >= needed + 16*1024*1024, '系统卷空间不足，需要启动文件大小另加 16 MiB 余量')
        self.info = dict(model=device['machine'], ecid=self.m['ecid'], version=version['ProductVersion'],
                         build=version['ProductBuildVersion'], profile=profile['id'], kernel_sha256=sha(kernel),
                         free_bytes=block_size*free, new_file_bytes=needed, existing=existing,
                         persistent_writes=False, mounts=mounts.decode(errors='replace'))
        save(self.log / 'CHECK.json', self.info)
        self.nvram = nvram
        print('匹配配置：%s；新增文件 %.1f MiB；现有同内容文件将复用。' % (profile['id'], needed/1048576), flush=True)
        return self.info

    def install(self):
        require(self.info is not None, '请先完成本次连接的设备检查')
        previous_path = self.state / (self.m['ecid'] + '.json')
        if previous_path.exists():
            previous = json.loads(previous_path.read_text())
            require(previous.get('status') in ['COMPLETE', 'FILES_BEGIN'], '存在未完成的固件提交记录，停止重试：' + str(previous_path))
        self.r.run('/bin/mkdir /t4-android-install.lock')
        # Transfer every updater input to the ramdisk before persistent writes.
        helper = self.ram_upload('apply-set', self.blob('payload/apply-set'), True)
        package = self.ram_upload('boot-set.pack', self.blob('payload/boot-set.pack'))
        state = dict(status='FILES_BEGIN', log=str(self.log), device=self.info, package_sha256=sha(self.blob('payload/boot-set.pack')))
        save(previous_path, state)
        # Revalidate identity-relevant state after the user has reviewed the plan.
        require(self.r.run('/usr/sbin/nvram -p').stdout == self.nvram, 'NVRAM 在检查后发生变化，停止安装')
        require(b'/dev/md0 on / ' in self.r.run('/sbin/mount').stdout, '设备已离开 ramdisk')
        mounts = self.r.run('/sbin/mount').stdout
        line = next(x for x in mounts.splitlines() if b'/dev/disk0s1s1 on /mnt1 ' in x)
        if b'read-only' in line:
            self.r.run('/sbin/mount -u -w /mnt1')
        self.r.run('test ! -L /mnt1/boot/t4 && /bin/mkdir -p /mnt1/boot/t4')
        for item in self.m['runtime_files']:
            dest = '/mnt1' + item['destination']
            data = self.blob(item['source'])
            if self.info['existing'][dest]:
                require(self.r.read(dest) == data, '检查后启动文件发生变化；停止')
                continue
            temporary = dest + '.t4installer-partial'
            self.r.run('test ! -e ' + shlex.quote(dest) + ' && test ! -L ' + shlex.quote(dest) +
                       ' && test ! -e ' + shlex.quote(temporary) + ' && test ! -L ' + shlex.quote(temporary))
            self.r.run('/bin/cat > ' + shlex.quote(temporary), data)
            require(self.r.read(temporary) == data, '启动文件回读不一致，未更新固件')
            self.r.run('/bin/chmod 444 ' + shlex.quote(temporary) + ' && test ! -e ' + shlex.quote(dest) +
                       ' && /bin/mv ' + shlex.quote(temporary) + ' ' + shlex.quote(dest))
        self.r.run('/mnt1/bin/sync')
        # Both full files and unchanged iOS/NVRAM must be confirmed before NOR API.
        for item in self.m['runtime_files']:
            require(self.r.read('/mnt1' + item['destination']) == self.blob(item['source']), '启动文件最终校验失败')
        profile = next(p for p in self.m['profiles'] if p['id'] == self.info['profile'])
        require(sha(self.r.read('/mnt1' + profile['kernel_path'])) == self.info['kernel_sha256'], '原 iOS 内核发生变化，停止')
        require(self.r.run('/usr/sbin/nvram -p').stdout == self.nvram, 'NVRAM 发生变化，停止')
        state['status'] = 'FIRMWARE_BEGIN'
        save(previous_path, state)
        save(self.log / 'APPLY-ATTEMPT.json', state)
        try:
            result = self.r.run(shlex.quote(helper) + ' --apply ' + shlex.quote(package), timeout=60, allow_error=True)
        except BaseException:
            state['status'] = 'FIRMWARE_OUTCOME_UNKNOWN_KEEP_RAMDISK'
            save(previous_path, state); save(self.log / 'APPLY-ATTEMPT.json', state)
            raise
        self.log.joinpath('apply.stdout').write_bytes(result.stdout)
        self.log.joinpath('apply.stderr').write_bytes(result.stderr)
        state.update(exit=result.returncode, api_accepted=result.returncode == 0 and b'COMPLETE_IMAGE_SET_API_ACCEPTED' in result.stdout)
        if not state['api_accepted']:
            state['status'] = 'FIRMWARE_INCOMPLETE_KEEP_RAMDISK'
            save(previous_path, state); save(self.log / 'APPLY-ATTEMPT.json', state)
            raise Stop('启动镜像提交未完整成功。保持 ramdisk，不重启；日志：' + str(self.log))
        after = self.r.run('/usr/sbin/nvram -p').stdout
        state.update(status='COMPLETE' if after == self.nvram else 'FIRMWARE_ACCEPTED_STATE_CHECK_FAILED',
                     nvram_unchanged=after == self.nvram, cold_boot_confirmed=False)
        save(previous_path, state); save(self.log / 'APPLY-ATTEMPT.json', state)
        require(state['nvram_unchanged'], '镜像已提交，但 NVRAM 校验不一致；保持 ramdisk 并检查日志')
        self.r.run('/bin/rmdir /t4-android-install.lock')
        print('安装提交成功。原 iOS 内核、NVRAM 保持一致；Android 仍是 RAM 运行版。', flush=True)
        print('尚未自动重启。请退出 Kit 的 ramdisk，或按电源键＋Home 重启，测试三项菜单。', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['verify', 'check', 'install'])
    parser.add_argument('--port', type=int, default=6414)
    parser.add_argument('--kit', type=Path)
    parser.add_argument('--state-dir', type=Path, default=Path.home() / 'Library/Application Support/T4-Android-Installer-01')
    args = parser.parse_args()
    require(1 <= args.port <= 65535, 'SSH 端口范围错误')
    manifest = load_package()
    print('电脑端安装包 SHA-256 校验通过；目标 ECID：' + manifest['ecid'], flush=True)
    if args.action == 'verify':
        return
    require(sys.platform == 'darwin', '首版测试环境为 macOS，设备端使用现有 Kit SSH ramdisk')
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
    log = args.state_dir / 'logs' / stamp
    log.mkdir(parents=True)
    remote = SSH(args.port, args.kit, log)
    try:
        remote.connect()
        installer = Installer(remote, manifest, BASE, log, args.state_dir / 'devices')
        info = installer.check()
        print('本次日志：' + str(log), flush=True)
        if args.action == 'install':
            print('\n将安装 iOS / Android / Console 菜单及两份启动文件。会更新持久启动固件；不擦除、不分区、不写 NVRAM。')
            if input('确认在这台 %s / iOS %s 上安装？[y/N]: ' % (info['ecid'], info['version'])).strip().lower() != 'y':
                print('已取消，没有写入持久存储。'); return
            installer.install()
    except BaseException as e:
        save(log / 'ERROR.json', dict(type=type(e).__name__, message=str(e)))
        raise
    finally:
        remote.close()


if __name__ == '__main__':
    try:
        main()
    except (Stop, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as e:
        print('\n停止：' + str(e), file=sys.stderr)
        sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        print('\n已中断。若已进入固件提交阶段，请保持 ramdisk 并查看日志。', file=sys.stderr)
        sys.exit(130)
