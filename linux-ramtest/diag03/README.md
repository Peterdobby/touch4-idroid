# T4_LINUX_DIAG_03：给关停和内核入口建立可区分的屏幕边界

依据实机日志 `logs/linux-ram-20261018-183922.log`：RAM 内容、原版代码 CRC、
framebuffer 布局、修正后的完整 cmdline 均已通过；最后收到的是
`init: Shutting down modules.`。用户反馈蓝屏。尚无内核执行证据。

已静态核对原版 exit table：起点 `0x3f9f0`，第一个 callback 即 NULL，
没有退出回调。但日志打印位于 `exit_modules` 的开头，不能由此认定函数已返回。
本版本不重复 DFU/设备支持研究，也不重新初始化 LCD/MIPI。

## 运行

重新进入硬件 DFU，先执行：

```bash
cd .
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_LINUX_DIAG_03 --stage
```

这一步没有进入 Linux。应看到 `DIAG 03 STAGED - NOT LINUX`。
若这行没有显示，保留日志并报告，不继续以屏幕判定后续步骤。

确认上述文字可见后，再执行：

```bash
python3 linux-ramtest/run.py --build T4_LINUX_DIAG_03 --boot
```

回报最后可见的完整编号文字，最好保留屏幕照片。主机日志仍自动保存到
`logs/linux-ram-*.log`。关中断后的步骤用屏幕观测，不能从 USB 消失推断进度。

## 编号的边界

| 最后可见的文字 | 在屏幕保持可读的前提下，已取得的证据 / 下一未确认边界 |
|---|---|
| `1 BEFORE CRITICAL` | 即将调用原版 EnterCriticalSection，尚未观察其返回 |
| `2 CRITICAL RETURNED` | 原版 EnterCriticalSection 返回；接着调用 exit_modules |
| `3 MODULES RETURNED` | 原版 exit_modules 返回 |
| `4 BEFORE CACHE OFF` | 即将调用原版 arm_disable_caches，尚未观察其返回 |
| `5 CACHE OFF RETURNED` | arm_disable_caches 返回；接着调用原版 mmu_disable |
| `6 MMU OFF RETURNED` | mmu_disable 返回；下一步核对低地址 kernel CRC 并准备 initrd/ATAG |
| `7 LOW KERNEL CRC FAILED` | 低物理地址别名读回的 kernel 内容不符；不会跳转 |
| `7 ATAG BUILD FAILED` | 参数块生成失败；不会跳转 |
| `7 TAGS INITRD READY` | initrd RAM 复制与 ATAG 生成完成 |
| `8 BEFORE ZIMAGE BRANCH` | 即将以 r0=0、r1=3564、r2=0x100 跳转 zImage；尚未观察到入口探针 |
| `9 ENTRY REGISTERS BAD` | zImage 头探针被调用，但寄存器/ATAG CORE 校验失败；停住 |
| `9 ZIMAGE HEADER PROBE` | zImage 修改后的前三条指令已调用诊断探针，入口寄存器与 CORE tag 通过 |

**9 仍只证明入口探针执行，不证明 Linux 主体运行。** 后续真实
`Uncompressing Linux...`、`Linux version...`、`PID1_REACHED` 分别才对应
解压器、内核主体、RAM 用户空间。画面若整体丢失，只记录丢失前最后一行，
不把“没有下一编号”当作某一具体指令必然故障的证明。

## 改动的准确范围

- 原公开版文件、原缓存/MMU/中断硬件函数都没改。新适配代码在 RAM 里按最小
  `boot_linux` 的流程生成标准 ATAG，然后依次调用原版函数，并在每个边界直接绘图。
- 这是独立的诊断交接实现，**没有把原 boot_linux 本体打补丁后假称仍完全相同**。
  本实验不执行原函数的可选 multitouch calibration 标签查询，也避免在关停后再
  调用原版 bufferPrintf。若它能继续运行，仍需进一步比较原路径来确定根因。
- 阶段绘图调用与成功 RAM menu 相同的 `framebuffer_setdisplaytext(0)`，随后仅改
  framebuffer RAM 像素，避免原文本滚屏覆盖编号；不设置 CLCD/MIPI/背光寄存器。
- 既有 02 的 zImage 只有前 **12 字节（原为三条 ARM NOP）** 被替换：
  `ldr ip,[pc,#0]; bx ip; .word 0x44000000`。0x24 magic、头部其余字段、
  压缩内核内容、总长度均保持不变。
- 诊断模块在固定 `0x44000000` 放置 ARM 探针，保存/恢复 r0-r12、lr，检查寄存器，
  绘制 9 后回到未改动的 `0x0200000c`，继续其余 NOP 和原 zImage 启动代码。
  探针本身只写 RAM。原始 zImage 副本为 `build/T4_LINUX_DIAG_03/zImage.original`。
- INITRD、N81 内核配置和 vmlinux 继续复用 02；`vmlinux` 对应未修改压缩头前的
  内核主体，压缩头探针在 `entry.S` 中单独提供。
- 原版调用地址经公开版校验固定：EnterCriticalSection `0x4c1`、exit_modules
  `0x391`、arm_disable_caches `0x829`、mmu_disable `0x12da1`（均为 Thumb）。
- 不写 NAND/NOR，不访问设备文件系统，不分区、安装或擦除；不用 Android ramdisk。

## 重建和离线检查

```bash
python3 linux-ramtest/diag03/build.py
python3 linux-ramtest/run.py --build T4_LINUX_DIAG_03 --check
```

已执行：命令行完整字符串测试、共享 ATAG 构造器的格式/容量测试、5 条模拟 USB
流程（正常 stage/boot 请求，版本错误、内容错误、参数错误拒绝）、ARM 探针的
寄存器保存/恢复及恢复地址检查、zImage 仅前 12 字节变化的比较。没有实机结果。
源码、构建信息、SHA256、反汇编在 `linux-ramtest/diag03/` 与
`build/T4_LINUX_DIAG_03/manifest.json`、`handoff.disasm`。

02 的完整产物保持原样，其源码和失败日志另有快照：
`experiments/linux-ram-02-blue-20261018-183922/`。
