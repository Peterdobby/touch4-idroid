# iPod touch 4：OpeniBoot RAM boot 实测结果

2026-10-18，当前 Intel Mac 与用户的 N81AP 实机：**OpeniBoot 0.3 已在 RAM 中运行，USB 控制台 help 往返成功。** 没有启动 Android，也没有发送安装、擦除、保存环境或文件系统写入命令。

## 1. 最终推荐方案

```text
macOS → 硬件 DFU
→ Legacy-iOS-Kit 的 ipwnder -p（limera1n）
→ 重新读取同一 ECID，确认 PWND: limera1n
→ RAM 加载离线补丁 iBSS 4.1 / 8B117
→ 上传公开 OpeniBoot 0.3 的 NAND 初始化禁用副本
→ go → 小入口包装 → iBSS 原生 jump_to
→ OpeniBoot USB 0525:1280 → ACM help 往返成功
```

本轮依用户后续要求改用其提供的公开 binary。不是新编译的 OpeniBoot。原文件 `<HOME>/Downloads/openiboot_ipodtouch4g_0.3.bin` 保持原样，276384 字节，SHA256：

```text
61adbd378093bbd94f935fa16721c7d738e188ceb1c9090dd22c9d79a942ba8c
```

**测试副本有明确的一处保护修改**：`.init_modules` 中偏移 `0x3f9e0` 的 `h2fmi_init` 回调，从 `0x18255` 替换成已有的 Thumb 空函数 `0x2269d`。四字节指针内实际改变三个字节，跳过自动 NAND/FTL 初始化，其余初始化回调继续执行。没有把回调改成 NULL，因为 NULL 会终止整个初始化表遍历。该修改不会删除手动闪存写命令；测试客户端只发送 `help`，不能拿它证明任意交互命令都安全。

## 2. 准备命令

**当前这台电脑已准备好，不必重复安装依赖。**

```bash
cd .
python3 phase1/run.py --check
```

在另一台使用 Homebrew 的 Mac 上，主机依赖可以这样安装（这些是准备命令，不是本次实测机器使用的包管理器）：

```bash
brew install python scons pkgconf libusb libirecovery
```

本次实际使用 Python 3.9、SCons 4.11.1、libirecovery 1.3.1，以及已有的 Darwin x86_64 ARM GCC 4.8。ARM GCC 仅用于编译 28 字节的入口包装，不重新编译这份公开 OpeniBoot。当前 GCC 路径为 `toolchain/arm-eabi-4.8/bin/arm-eabi-gcc`。

Intel Mac 已实测。现有 Legacy-iOS-Kit 的 `ipwnder` 同时包含 x86_64 和 arm64；Apple Silicon 尚未实测，旧 x86_64 GCC 需要能运行 x86_64 程序的环境。主机加载器、控制台应按本机架构重新编译，不能把 Intel 实测当作 Apple Silicon 实测。

工具比较：

| 工具 | 本轮结论 |
|---|---|
| Legacy-iOS-Kit / ipwnder | 本机选择；多次实测取得 limera1n 标记并启动补丁 iBSS。只调用独立 `ipwnder -p`，不运行恢复流程。 |
| primepwn | 当前源码已在本机编译通过；8930 默认 SHAtter，另有 `--use-limera1n`。本轮没有对实机重复测试它。其带镜像参数的分支不能直接当成 A4 OpeniBoot 加载器。 |
| axi0mX/ipwndfu | A4 使用 SHAtter；原版仍有 Python 2 语法和旧依赖，不是这台现代 Mac 的最短路径。 |
| irecovery | 用 `-q` 检查设备、PWND；上传和跳转由小加载器固定协议并检查阶段。 |

若 macOS exploit 持续失败，可用原生 Linux 的 primepwn 完成 pwned DFU；这是备用候选，未在本次硬件上验证，不提供“已可靠”的承诺。

## 3. 编译 OpeniBoot / 准备测试镜像

本轮成功对象是用户提供的公开 binary，**不用重新编译 OpeniBoot**：

```bash
cd .
python3 phase1/prepare_published.py <HOME>/Downloads/openiboot_ipodtouch4g_0.3.bin
```

输出：

| 文件 | 用途 |
|---|---|
| `build/phase1-published/openiboot-original.bin` | 原文件逐字节副本 |
| `build/phase1-published/openiboot.bin` | 仅跳过自动 NAND 初始化的副本 |
| `build/phase1-published/openiboot-native.bin` | 实际上传文件，前 4 KiB 是入口包装 |
| `build/phase1-published/manifest.json` | 各文件校验值和修改记录 |

自编基线也已准备，构建命令为 `python3 phase1/build.py`，内部从校验后的上游快照执行 `scons -Q iPodTouch4G`；输出 `build/phase1/openiBoot-master/ipt_4g_openiboot`（ELF）和同名 `.bin`。该自编版本及其跳过显示初始化的对照版本本轮均未出现 OpeniBoot USB，不能推荐为已验证成功的镜像。

构建修复仅涉及 Python 3/SCons 兼容、Cortex-A8 选项、旧链接器参数、缺失 malloc 头，以及用保留 ELF 段和 BSS 大小的 Python 导出器替代旧宿主 mk8900image/xpwn 依赖。A4 目标没有 IMG3 模板，原始输出是裸 ARM binary；没有把旧设备的 IMG3 模板套上来。FreeiBoot 所查快照的 A4 target、入口和关键构建脚本与旧上游相同，未提供已完成的 N81 新启动链。

## 4. T4 进入 DFU 后的测试命令

重新进入硬件 DFU 后，一次执行完整链和成功检查：

```bash
cd .
python3 phase1/run.py --check
python3 phase1/run.py --boot --published
```

脚本先校验文件 SHA256、CPID、BDID、BootROM 和本机保存的 ECID；必要时调用 `ipwnder -p`；再次通过 `irecovery -q` 独立核对 PWND，未确认则不上传。然后运行 `build/phase1-published/load` 和只发送 `help` 的 `console`。完整原始回包保存到 `logs/phase1-published-*.log`。

**实际加载参数：**

- iBSS：4.1 / 8B117 的 N81AP IMG3 `.dfu`，离线修改 go 处理指针后保持原加密模板。无需 iBEC。
- RAM 上传地址：`0x41000000`；入口包装在此。
- 包装调用：`jump_to(0, 0x41001000, 0)`；本版本 iBSS 的 Thumb 地址为 `0x8401496d`。
- OpeniBoot 裸 binary 位于包装后 `0x41001000`，首条 ARM 指令执行自身的 relocation。
- 链接和搬迁目标：`0x00000000`。这是 A4 源码的 `OpenIBootLoad`，不是 USB 上传地址。
- go 请求：`bmRequestType=0x40, bRequest=0, wValue=0, wIndex=0, data="go\0"`。
- iBSS 的原生 jump_to 做关中断和缓存/MMU收尾；原先直接 BX 镜像的流程省略了这些操作。

**不能使用 `pwn DFU; irecovery -f openiboot.bin` 来替代这条链。** 普通 pwned DFU 没有通用的“把任意裸 binary 放到合适地址并执行”语义。SHAtter 有 IMG3 解析和特定 exec 协议，其接收区上限 `0x2c000` 也小于这份 276384 字节 binary；并且 DFU 没有 iBSS 的 go 命令处理器。这里通过小型 iBSS 先完成可控 RAM 上传，再触发其跳转。

`client/oibc` 来自更早的代码树，不应未经核对就当成当前 0.3 `acm/` 的客户端。本次客户端直接使用 0.3 的 bulk OUT `0x02`、bulk IN `0x81`，以 `ACM: Done: help.` 为成功条件。

## 5. 每一步预期输出与本次结果

```text
CPID: 0x8930
BDID: 0x08
SRTG: iBoot-574.4
MODE: DFU
PWND: limera1n
iBSS Recovery verified. Uploading RAM image at 0x41000000.
go transfer returned -1; execution must be checked independently.
OpeniBoot USB 0525:1280 opened.
version: openiboot 0.3 commit c5cee8c for iPod Touch 4G
ACM: Ready.
ACM: Starting help
...
ACM: Done: help.
OPENIBOOT_CONSOLE_CONFIRMED
```

以上来自本轮实机，不是期望输出拼接。`go` 返回 -1 不能单独判失败：本次随后确实枚举 OpeniBoot 并完成控制台往返。相反，上传成功或仅有旧 Recovery 设备记录都不能判成功。成功退出码仅在客户端收齐 help 完成标记后给出。

成功日志：`logs/phase1-published-20261018-102912.log`。前面的两个自编对照失败日志分别为 `logs/phase1-native-20261018-102305.log`、`logs/phase1-headless-20261018-102442.log`。

## 6. 如果黑屏，快速判断树

```text
DFU 的 PWND 缺失 → exploit 未确认，停止上传
仍是 BootROM DFU → iBSS 未运行
只有旧 Recovery 记录 → 不能证明设备仍响应
跳转后完全无 USB → 尚未建立早期入口/平台初始化证据
新出现 0525:1280 → OpeniBoot 已执行到 USB 初始化
ACM help 完整回包 → OpeniBoot 主体与控制台正常（本次已达到）
屏幕出现文本 → 另行确认 framebuffer 实际输出
```

只判断本轮是否出现新的 USB 身份，不以屏幕白/黑单独判断。退出临时状态可长按 Home + 顶部电源键重启；本流程没有持久安装步骤。

## 7. 尚未确认的问题

1. 自编版本为何失败，而公开 c5cee8c 版本成功；尚未定位到编译器差异或具体源码变化。
2. Apple Silicon 上相同流程的实机可靠性。
3. 本轮屏幕上的实际显示内容尚未由用户回报；USB 控制台成功已独立成立。

第一阶段停止：已得到公开 binary 的 RAM boot 和 ACM 控制台实机结果。不继续研究 Android、安装或双启动。

### 核对用的一手来源

- [OpeniBoot A4 入口与 relocation](https://github.com/iDroid-Project/openiBoot/blob/master/arch-arm/entry.sx)
- [A4 地址定义](https://github.com/iDroid-Project/openiBoot/blob/master/plat-a4/includes/hardware/a4.h)
- [原 syringe loadibec](https://github.com/iDroid-Project/syringe/blob/master/utilities/loadibec.c)
- [OpeniBoot 0.3 ACM 协议](https://github.com/iDroid-Project/openiBoot/blob/master/acm/acm.c)
- [公开 binary](https://github.com/albyvar/oibreleases/tree/master/oib/iPod4%2C1)
- [c5cee8c 的 NAND 自动初始化](https://github.com/iDroid-Project/openiBoot/blob/c5cee8c/plat-a4/h2fmi.c)
- [primepwn](https://github.com/LukeZGD/primepwn)、[Legacy-iOS-Kit 当前选择逻辑](https://github.com/LukeZGD/Legacy-iOS-Kit/blob/main/restore.sh)、[SHAtter 加载协议](https://github.com/axi0mX/ipwndfu/blob/master/src/SHAtter-shellcode.S)
- [irecovery 命令行源码](https://github.com/libimobiledevice/libirecovery/blob/master/tools/irecovery.c)、[FreeiBoot](https://github.com/FreeiBoot/FreeiBoot)
