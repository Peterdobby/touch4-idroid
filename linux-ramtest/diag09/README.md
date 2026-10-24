# T4_LINUX_DIAG_09：保留继承显示时钟，定位时钟握手

08 实机录像反馈：s5l8930_cpu_map_io done、T4_BOARD CPU_MAP RETURNED，
疑似 CLOCK BEGIN xtal=24000000（有遮挡），随后纯蓝屏。
**I/O 映射回调已经返回；最后的具体时钟门和 CPU 是否继续执行尚未确认。**
08 原产物保留，源码/manifest/主机日志/反馈在 experiments/linux-ram-08-clock-boundary/。

## 测试命令

重新进入硬件 DFU 后：

```bash
cd .
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_LINUX_DIAG_09 --boot
```

重点记录：

```
T4_CLK KEEP_DISPLAY gate=0b request=OFF
T4_CLK gate=.. enable=.. BEGIN
T4_CLK gate=.. RETURNED reg=........
T4_CLK gate=.. TIMEOUT requested=........ last=........ - STOP
T4_BOARD CLOCK RETURNED
```

画面保留并出现 CLOCK RETURNED 才证明这次时钟初始化返回；若是 TIMEOUT，
提供完整门号和寄存器值。若只看到 BEGIN 后卡住/丢画面，该次寄存器访问或随后的
诊断输出尚未确认，不能把它宣布为唯一故障指令。
后续继续尝试 UART、IRQ/timer 和 RAM /init；仍需 PID1_REACHED 才证明用户空间。

## 针对性修改

08 的 resident RAM 日志模块增加一个入口，内核 s5l_clock_gate_toggle_idx
首 8 字节在 RAM 中改跳至 resident_gate。原函数及补丁机器码、CRC 均逐项验证。
本版保持以下 OFF 请求不执行任何 MMIO：

|门号|源码依据|
|---|---|
|0x0b|c5cee8c plat-a4/clcd.c 开启 HPERF2；Linux s5l_power_zones[3].gate 同为 0x0b|
|0x0f、0x12|同一 OpeniBoot displaypipe_init 中的 CLCD/display pipe；Linux clk_clcd.ctrlbit=0x0f12|
|0x11|OpeniBoot MIPI_DSIM_CLOCKGATE；Linux clk_mipi_dsi.ctrlbit=0x0311|

原 s5l8930_cpu_init_clocks 起始循环会关闭 HPERF0/1/2，继承显示没有在 kernel clk
引用计数里预先登记。这给出了明确的显示中断风险，但仍不是对 08 蓝屏根因的实机证明。
另外 OpeniBoot 把 display pipe underrun colour 设置成蓝色，纯蓝也可能只是像素数据通路中断。

保护仅拒绝 OFF，**不强制开启门，不重设 LCD/MIPI/PLL，不更换频率**。
软件引用计数仍按原代码变化；这属于保留 bootloader 显示的临时诊断策略，不能代替正式显示驱动的时钟交接。

其余门的规则与原实现相同：同一寄存器 FC501010+4*index，开启 OR 0xf、关闭 AND ~0xf，
检查低四位和右移四位后的低四位是否相等。读写带 DSB 屏障；每次操作增加前后日志。
原无限循环改为最多 1000000 次读取；超限打印请求值/最后读值并停止，不继续使用未稳定时钟。
这不是固定毫秒数。无效门号也停止，避免访问越界寄存器。

08 的 resident RAM 保留、原生 framebuffer console、I/O 日志和板级调用顺序均保留。
所有 NAND 注册、写入/擦除入口阻止措施不变；不写 NAND/NOR，不安装或挂载持久存储。
原 zImage/压缩输入和 initramfs 不变。修改仍只存在于新构建文件与设备 RAM，重启恢复。

## 验证与重建

```bash
python3 linux-ramtest/diag09/build.py
python3 linux-ramtest/diag09/test_layout.py
python3 linux-ramtest/run.py --build T4_LINUX_DIAG_09 --check
```

test_resident.c 执行同一份 C 逻辑的模拟：64 个门分别开启/关闭，保护的 OFF 路径
零寄存器读写，其余位掩码保持原样；成功握手、超时停止、非法门号、17 个映射项和
板级调用参数均检查。真实 ARM 向量、gate hook、原 Image 数据中的门号、CRC、
页表映射、旧版本哈希、ATAG 和模拟 USB 路径另有离线检查。
离线通过不代表芯片已通过时钟初始化，等待用户实测。
