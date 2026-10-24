# T4_LINUX_RAM_02：蓝屏日志中的参数拼接错误修复

2026-10-18：01 版实机完成 RAM 校验并进入原版 `boot_linux`，最后设备消息是
`init: Shutting down modules.`，用户报告蓝屏。日志显示真实错误：

```text
console=t4fb0 l081045808 ignore_loglevel ... t4fb=0x00000000
```

旧适配模块寻找第一个 `t4fb`，错误命中 `console=t4fb0`，把地址覆盖到
`loglevel`，留下真正的 framebuffer 参数为零。这足以让早期 printk 屏幕控制台
不注册，但不能独立证明它是蓝屏的全部原因，也不能证明 Linux 已执行。

02 版只修复 RAM adapter 的参数构造，并让主机在跳转前校验设备返回的完整参数。
共享 `cmdline.h` 的回归测试使用完整期望字符串，另有损坏参数拒绝跳转的离线 USB
模拟。新内核和 initramfs 与 01 逐字节一致，没有更换公开版底座或修改硬件初始化。

当前 `build.py` 和 `run.py` 默认使用 **build/T4_LINUX_RAM_02/**。
构建器默认复用经 SHA256 验证的 01 内核/initramfs，仅重编 RAM 适配模块及主机工具；
显式 `--rebuild-kernel` 才从原内核树创建独立的 02 源码目录并重编内核。
屏幕内核/PID1 的旧 `T4_LINUX_RAM_01` 标签仍可能出现，这是复用内核的正常结果。

重新进入硬件 DFU 后：

```bash
cd .
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --boot
```

跳转前应出现 `prepared cmdline: console=t4fb0 loglevel=8 ... t4fb=0x08104580 ...`
（地址取自当次实际 framebuffer，可能改变；主机自动核对）。
然后仍需屏幕上的真实 Linux 解压/printk/PID1 文字，不能把主机成功退出或 USB 停止算作
Linux 成功。02 本轮没有实机测试。

01 失败产物原样保留在 `build/T4_LINUX_RAM_01/`，源码脚本及实测日志快照另存在
`experiments/linux-ram-01-blue-20261018-173640/`。
02 测试结果、校验值与记录在 `build/T4_LINUX_RAM_02/RESULT.json`、`manifest.json`。

---

# T4_LINUX_RAM_01：从成功公开版 OpeniBoot 进入 Linux 的独立 RAM 实验

2026-10-18：本版本已构建并完成离线检查，**尚未在设备运行 Linux**。
用户本轮要求只给实机命令，因此没有访问 USB 或执行硬件启动。
没有覆盖旧内核、旧 initramfs、公开版 OpeniBoot 或菜单产物。

## 直接运行

设备连接并进入硬件 DFU 后，在当前 Mac 执行：

```bash
cd .
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --boot
```

第一条沿用已经验证的公开版底座，第二条上传独立内核、RAM initramfs 和小适配模块，
核对内容后调用原版 `boot_linux`。不需要运行旧 `boot.py --linux`，也不需要加载
菜单模块或选择 iOS。若已有本项目的公开版 ACM 正在运行，可以只执行第二条；
先结束正在占用 ACM 的菜单监视程序，避免两个 USB 客户端争用。

想先只验证上传、不进入 Linux：

```bash
python3 linux-ramtest/run.py --stage
```

这只应得到 `T4_LINUX_STAGED_NOT_EXECUTED` 及随后 version 往返。
之后仍可执行 `--boot`，它会重新上传、核对并请求跳转。

只做电脑端校验，不接触 USB：

```bash
python3 linux-ramtest/run.py --check
```

重新编译：

```bash
python3 linux-ramtest/build.py
```

它使用已有 ARM GCC 4.8，从原内核树建立独立副本
`sources/iDroid-kernel-T4_LINUX_RAM_01/`，保留原有 Python/Perl/汇编兼容修改。
所有新镜像均在 `build/T4_LINUX_RAM_01/`，不要把其中 `zImage` 直接传给 DFU。
主机工具面向当前 Mac；依赖和原版启动流程与现有工程相同。

## 屏幕和日志如何判断

| 实际观察 | 能确认什么 |
|---|---|
| `T4_LINUX_STAGED_NOT_EXECUTED` | 原版控制台完成 RAM 内容与布局检查，Linux 尚未执行 |
| `Uncompressing Linux...` | 已执行真实 Linux zImage 解压器；尚不能证明内核主体已完成初始化 |
| `done, booting the kernel.` | 解压器已请求跳转到内核主体；仍需后续日志确认 |
| `Linux version 3.0.0...`、`T4_LINUX_RAM_01: Linux printk console active` | 内核主体已经执行，进入早期屏幕 printk 控制台 |
| `s5l8930_map_io` / `s5l8930_init_irq` / timer 等日志 | 根据最后一条文字判断板级初始化进度 |
| `PID1_REACHED; no block device opened; no storage mounted` | 已运行 RAM initramfs 的用户空间 PID 1 |
| 仅白屏、旧菜单、USB 消失或主机退出 0 | 不能证明 Linux 启动成功 |

屏幕字体为 8×8，日志多时会滚动，建议拍照保存最后几行。
USB 主机日志写入 `logs/linux-ram-*.log`；它只保存跳转前的 OpeniBoot 输出，
**不会自动抓到 Linux 屏幕日志**。旧内核配置 `CONFIG_USB_SUPPORT` 关闭，
且 N81 核心设备表没有注册 USB gadget，本版本不宣称提供 Linux USB ACM。
主机退出码 0 只表示 staging/跳转请求完成，不表示 Linux 或 Android 成功。

## 新启动路径及内存布局

保留原 c5cee8c 硬件初始化、iOS reboot 代码和菜单文件，采用独立实验路径：

```text
成功公开版 ACM
  → sendfile 到三个固定 RAM 区域
  → jump 到原版 ClearCPUCaches（0x684）
  → RAM 模块校验 CRC32、zImage magic、framebuffer 布局
  → 校验原 boot_linux 机器码 CRC32 与 SHA256 固定的公开版一致
  → 仅 --boot 时设置 Linux 私有 RAM 指针，调用原版 boot_linux（Thumb 0x2e3d）
  → 原版创建 ATAG、EnterCriticalSection、exit_modules、platform_shutdown
  → r0=0, r1=3564, r2=0x100，执行 zImage
```

| 用途 | OpeniBoot 地址 | Linux 物理地址 / 说明 |
|---|---|---|
| zImage | `0x42000000` | 原生启动函数换算为 `0x02000000` |
| native ATAG 暂存区 | `0x41ffe000` | kernel 前预留 8 KiB，最终复制到 `0x100` |
| initramfs staging | `0x43000000` | 原生启动函数复制到 `0x48000000`，ATAG_INITRD2 使用 `0x08000000` |
| 解压器显示参数 | `0x43f00000` | Linux 物理 `0x03f00000`，保留一页 RAM |
| RAM 适配模块 | `0x44000000` | 不覆盖既有 `0x45000000` 菜单代码 |
| framebuffer | 运行时读取，曾为 `0x48104580` | 用原生 A4 RAM 别名换算为低物理地址，并在内核 memblock 中保留 |

地址换算依据原版 `actions.c:boot_linux/setup_initrd2_tag`、A4 `entry.sx`
的 MIU 配置，以及内核 `PLAT_PHYS_OFFSET=0` / `Makefile.boot`；不是从 iPhone 4S
或其他板的示例复制。N81 原版和内核的 machine ID 均为 **3564**。

没有通过 `kernel <RAM地址+大小>; boot` 走配置文件加载分支：c5cee8c 的
`script_load_file` 对 RAM URI 返回原地址，而 `setup_boot` 随后直接 `free(data)`。
本模块避免释放固定 RAM 指针，也避免在内核 malloc 块之前随意使用 8 KiB。
硬编码原版符号只适用于锁定的 SHA256；构建器从原 binary 的 GOT/literal
计算并核对私有变量位置，设备端再核对 native boot_linux 的代码 CRC。

原版源码调用关系见 `research/openiBoot-c5cee8c/actions.c`、`scripting.c`、
`plat-a4/a4.c`；对应本实验代码见 `handoff.c`。不会遍历 `mtd_list`、查找
`images_list`，也不使用任何设备文件系统路径。

## 内核修改范围

新副本保留 `ipt4_defconfig` 和已有禁用 NAND 注册的补丁：

- `CONFIG_MACH_IPOD_TOUCH_4G=y`、`CONFIG_MTD` 关闭、N81 `register_h2fmi` 不调用。
- 解压器改用继承 framebuffer 输出，避免只能看不可接入的 UART，或在 UART 等待。
- 新增早期 Linux printk framebuffer console，重放初始日志，保留显示内存。
- 本实验暂不注册 N81 原生 CLCD/MIPI 驱动，复用已在工作的显示状态；没有重做 LCD 初始化。
- PID 1 只打开 RAM 内 `/dev/kmsg` 写入用户空间标记，不运行 Android 的 init 脚本。

差异保存为 `kernel-diagnostic.patch`（相对原本地内核树，原树已有的兼容/NAND
补丁见项目 `patches/kernel-ramtest.patch`）。这不是完善驱动的 Android 内核；
Binder、ashmem、HAL、rootfs 接入仍留在获得真实内核运行证据之后。

## 实际找到的 Android 包

`<HOME>/Downloads/androidi4.zip`，80,036,044 字节，SHA256：
`ec675ca867c340d943eac9cd0676fa8ca71427432d93d5961379c851eda88d9d`。
完整 ZIP CRC 检查通过，内含：

| 成员 | 字节数 | 格式与判断 |
|---|---:|---|
| `ramdisk.img` | 1,039,024 | gzip/newc，旧 Android initrd；本轮不执行 |
| `system.img` | 88,695,552 | YAFFS2，2048 数据 + 64 spare；实际属性为 generic Android 2.3.7 |
| `userdata.img` | 104,857,600 | ext 系列文件系统镜像 |
| `system_unpacked.zip` | 31,743,675 | 属性为 iPhone4 Android 2.3.7 的另一个解包副本；与 system.img 不一致 |

**没有 zImage、Image、uImage、boot.img 或可独立启动的内核。**
真实 system 的 ARM EABI5 用户空间可作后续候选，但其中 HAL 有 goldfish
传感器/GPS/gralloc，不能认定已适配 N81，也不能由文件名确定 N90/N92 目标。
原 `initDroid.sh` 会对 `/dev/nand0p2` 做 HFS fsck（含修复分支）、挂载及写入，
不满足本阶段限制；它还将 system 当 ext 挂载，与实际 YAFFS2 格式不一致。

严格区分：iPod4,1=N81AP；iPhone3,1=N90AP（GSM）；iPhone3,3=N92AP（CDMA）；
iPhone4,1 是 iPhone 4S。本包缺少内核，无法从其中验证 N90/N92 板级内核配置。
已有 N81 源码、zImage 和最小 RAM 用户空间因此优先于直接使用此包启动。

原始文件及 ZIP 成员的完整路径、大小、格式和 SHA256：`INVENTORY.json`。
已重核现有 system 解包产物中 464 个普通文件的 SHA256；未重复解包、转换或运行它们。

## 验证记录

- 隔离内核、静态 ARM PID 1、RAM 适配模块和主机工具构建通过。
- initramfs 用独立现有 newc 解析器核对，只含 init 和三个 RAM dev 条目。
- ARM handoff ELF 没有未解析外部符号；原版 ABI、ATAG 参数、入口和文件校验值已核对。
- 主机 USB 协议模拟覆盖 stage、boot 请求、错误版本拒绝、错误 stage 拒绝；
  日志明确为 `build/T4_LINUX_RAM_01/offline-*.log`，不是实机启动证据。
- 新产物 SHA256/大小：`build/T4_LINUX_RAM_01/manifest.json`。
- 构建日志：`build/T4_LINUX_RAM_01/kernel-build.log`。旧源码仍有编译器警告，
  构建退出 0；没有借此声称驱动已验证。
- 旧内核和已成功的 OpeniBoot/menu 产物与初始清单逐字节校验值一致。

下一步所需条件仅是用户执行上述命令并提供屏幕最后的真实文字。
到达 PID1 才确认这个最小 RAM Linux 用户空间成功；本版本不启动 Android。
