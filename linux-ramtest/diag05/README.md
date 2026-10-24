# T4_LINUX_DIAG_05

04 实机反馈：`12`。确认 Linux 压缩头的 SCTLR 写入、读回、指令同步屏障以及
其后的诊断绘图均执行。本版继续越过原主动停止点。
04 完整产物保留；反馈和源码快照在 `experiments/linux-ram-04-checkpoint12/`。

## 操作

重新进入硬件 DFU 后：

```bash
cd .
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_LINUX_DIAG_05 --boot
```

本版预计主动停在 15，不进入内核主体，不尝试 Android。
回报最后的编号和实际解压文字；若蓝屏，记录蓝屏前最后一项。
USB 断开仍不是 Linux 启动成功的证明。

|编号/文字|证据及下一边界|
|---|---|
|12 MMU WRITE RETURNED|与 04 相同边界，随后恢复原 mov pc,ip 返回|
|13 BEFORE DECOMPRESS C|原 head.S+0x160 调用之前，解压参数通过检查|
|13A DECOMPRESS C TEXT|真实解压器 C 代码调用了 putstr；文字继续画在屏幕中部|
|Uncompressing Linux...|真实 misc.c 的开始消息，不代表解压成功|
|done, booting the kernel.|真实 misc.c 中 do_decompress 成功返回后的消息；本版仍会主动停住|
|14 IMAGE CRC OK|decompress_kernel 返回，RAM 中的 1687840 字节 Image CRC32 为 F1B0975D|
|14 IMAGE CRC FAILED - STOP|解压结果与基线 Image 不符，主动停住；屏幕显示实际 CRC|
|15 BEFORE KERNEL CORE - STOP|原 cache_clean_flush 和 cache_off 已返回，检查 r0/r4/r7/r8 后主动停止，尚未执行内核主体|

## 改动与边界

继续使用公开 OpeniBoot、02 的内核压缩内容和最小 RAM initramfs。
原 NAND 禁用与继承显示的内核配置不变。没有 LCD/MIPI 重新初始化，也无持久化操作。

压缩头前 32 字节的原 NOP 区放四个绝对跳转；0x328、0x160、0x164 放 B 跳转，
分别对应 MMU 后、解压前、解压后。探针保存寄存器和条件标志，补执行原返回或 BL。
原 SCTLR 写入/读回/同步、cache_clean_flush/cache_off 的机器码均不变。
04 的 10/11 日志探针撤掉，恢复对应原指令，header 空间复用给解压探针。

原 putstr 的开头 8 字节替换成 RAM 模块入口，**只替换诊断文字绘制**：
真实字符串从 r0 读取，经已验证的高地址 framebuffer 路径绘制并清理缓存。
这样不依赖旧 putstr 的低地址像素缓存可见性，但不认定缓存就是先前蓝屏的原因。
inflate、malloc、error、decompress_kernel 及压缩数据本身没有改动。

0x170/0x174 替换成最终停止探针，因此尚未执行原 r1/r2 赋值和 mov pc,r4。
15 检查保存在 r7/r8 的机器号/ATAG、r4 的 Image 入口和 r0。
它证明到达交接前边界，不证明内核主体或用户空间执行。

压缩输入从 zImage+0x469b 到 0xd0a95。构建时用主机 gzip 解压校验完整性，
并与原构建目录的 arch/arm/boot/Image 逐字节比较，生成 Image.expected。
设备上 14 的 CRC 与这个独立结果比较。产物与地址、SHA256 在 manifest.json。

```bash
python3 linux-ramtest/diag05/build.py
python3 linux-ramtest/diag05/test_layout.py
python3 linux-ramtest/run.py --build T4_LINUX_DIAG_05 --check
```
