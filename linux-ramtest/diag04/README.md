# T4_LINUX_DIAG_04

实机 03 反馈：先看到 `9 ZIMAGE HEADER PROBE`，然后蓝屏。
日志 `logs/linux-ram-20261018-191036.log`。这证明交接探针运行且入口参数
校验通过，还没有证明解压器或内核主体执行。原 03 产物不变，反馈与源码快照在
`experiments/linux-ram-03-blue-20261018-191036/`。

04 只追踪原 zImage 压缩头的 cache_on 路径，**有意在 12 停住，不尝试解压**。
原版 OpeniBoot、LCD/MIPI、Linux MMU/缓存初始化指令都不改。
继承 03 的 RAM 交接与入口检查。initrd/内核压缩内容继续复用 02。

## 操作

设备重新进入硬件 DFU 后：

```bash
cd .
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_LINUX_DIAG_04 --boot
```

报告最后出现的编号；若能看到十六进制寄存器行，拍照保留整个画面。
不以 USB 消失认定 Linux 成功。

|编号|源码/真实指令边界|
|---|---|
|9|入口参数检查通过；跳回原 header 分支 0x20|
|10|`arch/arm/boot/compressed/head.S` 原 `bl cache_on`，zImage+0x64，即将调用|
|11|`__armv7_mmu_cache_on` 中 zImage+0x314：TTBR0 已按原逻辑写入，即将写 DACR/SCTLR|
|12|zImage+0x328：原 SCTLR 写入、读回、指令同步屏障均已执行，诊断绘图可运行；主动停止|

屏幕另显示 INITIAL/NEXT/ACTUAL SCTLR、TABLE BASE、CODE/FB PTE、TTBCR。
这些是实际读值；没有预先认定某个控制位就是故障原因。
如果 11 后蓝屏，未确认范围是 DACR/SCTLR 切换、取指同步及 12 绘图路径，
不能只凭画面消失把某一条指令宣布为唯一根因。
若稳定显示 12，下一步才继续到解压器；本版不会显示 PID1 或 Android。

## 变更范围及重建

八个 header ARM NOP 替换成四个 `ldr pc` 绝对跳转，不破坏寄存器。
0x64、0x314、0x328 用不带链接的 B 转到对应 header veneer。
探针保存/恢复 r0-r12、lr、CPSR 条件标志，栈保持八字节对齐；
0x64 补回原 BL 的 lr，0x314 补执行原条件 DACR 写入。
0x328 原返回指令被主动停止代替。
0x318..0x327 的 SCTLR 写入、读回及屏障连续原样保留。
原内核 zImage 副本为本构建目录的 zImage.original，vmlinux 对应未改压缩头的内核。
所有更改仅在本地新产物及设备 RAM；没有存储操作。

```bash
python3 linux-ramtest/diag04/build.py
python3 linux-ramtest/diag04/test_layout.py
python3 linux-ramtest/run.py --build T4_LINUX_DIAG_04 --check
```

SHA256 和条目地址见 `build/T4_LINUX_DIAG_04/manifest.json`；
最终 ARM 机器码见同目录 `handoff.disasm`。
