# c5cee8c：T4 菜单测试

> **本阶段已完成（2026-10-18）：** 用户实机确认三项可见、选择可移动，USB ACM 正常。使用[成功公开原版 + RAM 菜单模块](public-overlay/README.md)复现。以下保留早期完整源码构建记录；该路径实测白屏，已停止使用。当前成功方案只自编译 UI 模块，不代表完整 OpeniBoot 自编译镜像已成功。

源码：`sources/openiBoot-c5cee8c-ui`，`git log -1 --oneline` 为 `c5cee8c fixup previous`。

原版 T4 target **没有链接 menu 模块**，所以执行 `OpenIBootConsole()`。即使链接 menu，`menu_main()` 的 `(0)/boot/menu.lst` 加载失败分支也是切回 console，不会自动创建 iOS/Android/Console 三项。对应用户选项为 **E**。`setup_init()` 只建立空链表/root sentinel，不会创建一个有标题的默认系统项。`menu_draw()` 遍历配置创建的 BootEntry 后，另外绘制 Console。

## 1. 编译诊断版

```bash
cd .
python3 t4-menu/build.py T4_DIAG_01
```

内部执行 `T4_BUILD=T4_DIAG_01 scons -Q iPodTouch4G`。ELF 与裸镜像：

```text
build/T4_DIAG_01/ipt_4g_openiboot
build/T4_DIAG_01/ipt_4g_openiboot.bin
build/T4_DIAG_01/openiboot-native.bin  ← DFU 流程实际使用的 RAM 入口包装
```

构建会检查 binary 的 `openiboot 0.3`、`c5cee8c`、`iPod Touch 4G`、版本标识，以及现代链接器是否正确生成 Thumb→ARM `BLX`。

## 2. DFU RAM boot T4_DIAG_01

设备进入硬件 DFU 后：

```bash
cd .
python3 phase1/run.py --boot --build T4_DIAG_01
```

沿用已有 RAM 加载链。脚本自动记录 `logs/T4_DIAG_01-*.log`，并通过 ACM 发送只读的 `t4_diag`。

## 3. 单独抓 USB ACM 日志

设备已经运行诊断版时：

```bash
cd .
./build/T4_DIAG_01/console --watch 60 | tee logs/T4_DIAG_01-acm.log
```

菜单版使用 `./build/T4_MENU_01/console --watch 60`。不要同时运行两个 ACM 客户端。该客户端只发送 `t4_diag`，没有交互 shell、安装或文件上传功能。

## 4. 根据日志定位

| 最后日志 / 返回值 | 结论与下一文件 |
|---|---|
| `mipi_dsim_init return ... ret != 0` | 原版忽略的 MIPI 返回错误；看 `plat-a4/mipi_dsim.c`。本诊断不改变原调用行为。 |
| `pinot_init return ret != 0` | 面板初始化返回失败；看 `plat-a4/clcd.c:pinot_init()`。 |
| `display init FAIL`、随后 `framebuffer skipped` | `displaypipe_init()` 非零返回；尚未调用 `framebuffer_setup()`。 |
| `framebuffer init OK`、`FramebufferHasInit=1` | 软件 framebuffer 已建立；另报实际地址、尺寸和 stride，尚不等于肉眼已看到图像。 |
| `menu module NOT LINKED` | DIAG 的预期结果，准确保留原 target 的选择；没有执行配置加载或菜单绘制。 |
| `menu display begin` 无 `menu display returned` | MENU 停在 `menu/menu.c:menu_draw()` 或其 framebuffer 调用中。 |
| `menu display returned` 且 `menu button task running` | 绘制函数返回并进入按键任务；需结合屏幕和 `selected=` 变化确认显示/输入。 |
| 没有 ACM | 不能凭空声称最后一个 OpeniBoot 函数已成功，也不能据此判菜单失败；早于 ACM 的挂起不能通过尚未连接的 ACM 回读。 |

`t4_diag` 会重放 RAM 中的初始化记录，因此不用依赖第一次连接时是否完整读到启动输出。

## 5. 编译 T4_MENU_01

```bash
cd .
python3 t4-menu/build.py T4_MENU_01
```

对应 ELF/裸镜像位于 `build/T4_MENU_01/`。菜单版额外链接既有 `menu` 模块，使用既有 renderer，创建两个 RAM BootEntry：`iOS`、`Test Entry`；Console 是 renderer 自带的第三行。没有读取或创建 `menu.lst`，也不执行 temp-os/NVRAM 保存路径。

## 6. DFU RAM boot 菜单版

重新进入硬件 DFU 后：

```bash
cd .
python3 phase1/run.py --boot --build T4_MENU_01
./build/T4_MENU_01/console --watch 60 | tee logs/T4_MENU_01-keys.log
```

预期屏幕显示三行，当前项反色：

```text
iOS
Test Entry
Console
```

音量减/顶部键选择下一项，音量加选择上一项；ACM 报 `selected=iOS / Test Entry / Console`。Home 只记录当前项，三个项目都禁止实际引导。原版按键轮询中的音量键取反条件只在 MENU 的测试分支改为按下沿触发，没有修改 GPIO/按键硬件初始化。

## 源码与安全范围

- 源码 diff：`t4-menu/c5cee8c-ui.patch`。在干净的 `git checkout c5cee8c` 上可执行 `git apply /绝对路径/c5cee8c-ui.patch`。
- DIAG 的功能改动是日志；两版共享必要的构建兼容补丁与 NAND 驱动禁用保护。
- 未改变 `a4.c` 的硬件初始化次序、CLCD/MIPI 参数或 framebuffer 初始化条件，只记录返回值。
- 老汇编的 ARM 函数原为 `NOTYPE`；GCC 4.8/现有链接器会错误保留 Thumb `BL`。为汇编函数补 `.type ..., %function` 后生成 `BLX`，不改变这些函数的指令。
- 两版都以无硬件访问的 stub 替代 `h2fmi.c`，没有 NAND 硬件驱动/注册。A4 target 没有加入 NOR 模块。MENU 的编译分支不含 `script_run_file`、`nvram_save`、`setup_boot` 调用。
- 所有操作只构建文件或临时上传到 RAM；不运行 install、擦写、分区或文件系统写入命令。

GitHub 的 git HTTPS 传输两次连接失败，因此本机 checkout 使用同一官方 c5cee8c archive；其 Git tree 已核对为 `754459d1b30448bc5b3756f52124f58228068c66`，原始 commit 对象核对为 `c5cee8cc9e9b13784272550ab0938175cec1cdb5`，并以该真实提交建立 shallow checkout。没有换用 fork 或另一个版本。
