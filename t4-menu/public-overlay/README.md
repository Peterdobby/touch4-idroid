# iPod touch 4：公开 OpeniBoot + RAM 菜单（iOS boot request test）

2026-10-18：三项菜单显示、音量键选择和 Home 事件已在实机确认。本文新增的 iOS boot 请求路径尚待实机测试；它由 Mac 端通过原版 ACM console 发送 `boot` 命令。

**保留已验证的公开版硬件初始化。不要使用之前白屏的完整自编译 T4_DIAG_01 / T4_MENU_01 镜像。**

## 复现命令

```bash
cd .

# 只编译 UI 模块和主机上传器，不重新编译 OpeniBoot。
python3 t4-menu/public-overlay/build.py --live

# 设备进入硬件 DFU 后，运行已经成功的公开原版 RAM 基线。
python3 phase1/run.py --boot --published

# 在原版 ACM 正常时，加载一次 UI 模块；然后等待 iOS/Home 事件最多 120 秒。
python3 t4-menu/public-overlay/run.py
```

每次从一次新的公开原版 RAM boot 开始，UI 模块只加载一次；不要在已有菜单任务上重复加载。当前已显示菜单的设备无需再次执行。

预期：屏幕显示 `iOS / Test Entry / Console`，当前项反色。音量减/顶部键向后，音量加向前。按 Home 选中 iOS 时，Mac 端会通过现有 ACM console 发送 OpeniBoot 原生 `boot` 命令；另外两个项目仍为占位。iOS 真正启动尚未验证。

## 实机证据

`logs/public-menu-live-test.log`：

```text
version: openiboot 0.3 commit c5cee8c for iPod Touch 4G
[PUBLIC_MENU_01] original console returned; original hardware init reused
[PUBLIC_MENU_01] fb=48104580 width=640 height=960 colorspace=6
[PUBLIC_MENU_01] draw returned; entries=3 selected=iOS; UI_ONLY
PUBLIC_MENU_DRAW_CONFIRMED
[PUBLIC_MENU_01] button task running
[PUBLIC_MENU_01] task_start returned 0; ACM stays active
[PUBLIC_MENU_01] draw returned; entries=3 selected=Test Entry; UI_ONLY
[PUBLIC_MENU_01] draw returned; entries=3 selected=Console; UI_ONLY
```

日志证明程序行为；用户另行确认了屏幕可见和选择移动，不以“绘制函数返回”代替屏幕验收。

## 实现范围

- 原文件：`<HOME>/Downloads/openiboot_ipodtouch4g_0.3.bin`，SHA256 `61adbd378093bbd94f935fa16721c7d738e188ceb1c9090dd22c9d79a942ba8c`，保持不变。
- 启动底座沿用已验证的 NAND 自动初始化回调禁用副本。
- `menu.c` 仅编译 UI，链接/加载到 RAM `0x45000000`；入口和校验值写在 `build/T4_PUBLIC_MENU_01/live/live.json`。
- 显示、MIPI、时钟、GPIO 初始化、USB 和任务调度都复用原版；没有重编这些函数。
- 显示缓冲区使用原版运行时返回的地址和描述，检查宽高、stride、RGB888、对齐、RAM 范围后才绘制。没有假设它等于静态 CLCD_FRAMEBUFFER 常量。
- 字体来自 c5cee8c 的 `pcf/9x15.h`；三项 UI 为新编译的 RAM 附加代码。
- ACM 仅使用 `version`、`sendfile` 到固定 RAM 地址，以及 `jump` 到原版缓存同步例程和 UI 入口。上传器不是交互式 shell。
- 不加载 menu.lst、不安装、不写 NAND/NOR、不分区、不挂载或写文件系统、不引导 Android/Linux。重启清除 RAM 菜单。

`build.py` 不带 `--live` 还可以构建附加模块的单镜像 DFU 包，但修正 framebuffer 检查后的这一单镜像包未重新做 DFU 实测；上面的两阶段命令是推荐复现路径。


## Step 1: host-assisted iOS boot request (experimental)

The first activation test deliberately reuses the already-running published
OpeniBoot command console instead of calling a guessed firmware function
address from the RAM overlay:

1. The menu emits `[PUBLIC_MENU_01] IOS_BOOT_REQUEST` only when Home is pressed
   while `iOS` is selected.
2. The Mac-side `live.c` uploader remains connected to USB ACM, detects that
   marker, and sends the existing OpeniBoot console command `boot\n`.
3. OpeniBoot's native `boot` command calls `setup_boot()`. The default root
   entry is `kBootAuto`, which tries `ibox` and then `ibot`.

This is a **host-assisted first test**, not yet a standalone on-device action:
the Mac must remain connected and `python3 t4-menu/public-overlay/run.py`
must keep running while you select iOS and press Home. The other two entries
remain inert.

### Build and test

```bash
cd .
python3 t4-menu/public-overlay/build.py --live
python3 phase1/run.py --boot --published
python3 t4-menu/public-overlay/run.py
```

After the menu appears, select `iOS` and press Home within 120 seconds. The
host helper will log that it sent `boot`. If USB disappears, independently
check whether the Apple logo/iOS actually appears; USB disconnect alone is
not proof that iOS completed booting. If the console reports `ACM: Done: boot.`
or the helper times out, chainload is unconfirmed and the log should be saved.

This path issues the existing OpeniBoot `boot` command only. It does not call
`install`, erase, partition, or any NAND/NOR write command. If the published
image cannot find `ibox`/`ibot`, the command may return to the console; the
next step is to inspect the read-only boot-image discovery path, not to write
NAND/NOR or guess a function address.
