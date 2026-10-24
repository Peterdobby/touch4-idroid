# T4_LINUX_DIAG_08：N81 I/O 映射与时钟边界

07 录像实测已有真实 ARMv7、Machine: Apple iPod Touch 4G、console [t4fb0] enabled、
NATIVE_CONSOLE_READY、Memory Policy、CPU S5L8930 日志。用户最后观察到
s5l8930_cpu_map_io，随后纯蓝屏，没看到 done。
**原生内核控制台已确认；不能再把纯色背景本身当作 Linux 未运行。**
07 原产物不变，录像转述与主机日志在 experiments/linux-ram-07-native-console-cpu-map-io/。
目前只确认该入口日志，尚未确认最后成功的 create_mapping，也不排除后续代码在视频两帧间执行后切断显示。

## 测试

重新进入硬件 DFU 后：

```bash
cd .
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_LINUX_DIAG_08 --boot
```

用录像记录蓝屏前最后几行，优先找：

```
T4_IO 1/17 BEGIN va=fc000000 pa=bf200000 len=00010000 type=0
T4_IO 1/17 RETURNED
...
T4_IO 17/17 RETURNED
s5l8930_cpu_map_io done
T4_BOARD CPU_MAP RETURNED
T4_BOARD CLOCK BEGIN xtal=24000000
T4_BOARD CLOCK RETURNED
T4_BOARD UART BEGIN
T4_BOARD UART RETURNED
```

实际 type 取自原 map_desc，日志示例不作为硬编码预期。io-table.json 从原 Image 的 17 个描述符解码，
对应顺序为 VIC0–3、UART0–2、PMGR0–6、GPIO、USB PHY、TIMER。
每项 BEGIN 及 CLOCK BEGIN 后有短暂、有界的软件等待，便于录像捕捉；不使用内核定时器，
也不改时钟寄存器。实际时长依 CPU 频率而变，整个启动会比 07 慢。

- 某项 BEGIN 后没有 RETURNED：尚未确认的范围是原 create_mapping 及之后的日志输出。
- 所有项 RETURNED 且 CLOCK BEGIN 可见：I/O 映射已返回，问题转向时钟初始化或显示被关闭。
- CLOCK RETURNED 可见：时钟初始化已返回，下一边界是 UART 或后续 IRQ/timer 初始化。

没有正常编号处的主动停机；仍以真实日志/PID1_REACHED 为证据。

## 改动

保留 07 的 zImage、原解压 Image 校验、原生 console 交接与所有 NAND 注册/写入/擦除 stub。
08 只新增持续生效的内核上下文日志：

- 原 iotable_init 入口转到日志包装器，逐项调用 **原 create_mapping**，原参数/描述符保持不变。
- t4_map_io 转到日志包装器，按原顺序调用 s3c_init_cpu(0x8930, cpu_id, 1)、
  s3c24xx_init_clocks(24000000)、s3c24xx_init_uarts(原 cfg, 4)，只添加前后 printk。
- 原 framebuffer reserve 入口转到包装器，先经 ARM trampoline 调用原完整 reserve body，
  再为日志模块保留物理 0x03e00000 起的 1MiB；失败就停止。保留原 framebuffer/INFO reservation。

模块编译在虚拟 c3e00000，15 时从 helper 内嵌副本复制到 RAM 43e00000，低地址 03e00000
再读回 CRC。19 加入正常内核 RAM 映射。它位于 kernel direct map，能跨越 prepare_page_table，
与已撤销的低地址 OpeniBoot/helper 映射无关；模块区在分配页表之前被 memblock 保留。

没有更改原 I/O 描述符、create_mapping、时钟/电源门控、UART、LCD/MIPI 代码。
新增 printk 会改变时序，因此日志成功不能单独证明原问题已修复。
全部更改仍只在本地新文件及设备 RAM，不写 NAND/NOR，不挂载持久文件系统。

## 已发现、尚待实测的后续问题

clock.c:s5l8930_cpu_init_clocks 的初始循环会关闭 HPERF0/1/2；
s5l_clock_gate_toggle_display 使用 HPERF2。此行为可能影响继承的显示。
当前还没有证明 07 最后执行到了该循环，08 先记录 CLOCK BEGIN/RETURNED，不预先修改时钟行为。

## 重建

```bash
python3 linux-ramtest/diag08/build.py
python3 linux-ramtest/diag08/test_layout.py
python3 linux-ramtest/run.py --build T4_LINUX_DIAG_08 --check
```

resident.c 的同一份逻辑可用 test_resident.c 在主机上模拟，检查 17 个描述符、调用顺序、
BEGIN/RETURNED 配对、保留操作和原始板级参数。ARM 实际向量、reserve trampoline、
内嵌 blob、CRC、页表冲突和旧产物哈希另有离线检查。实机结果仍待测试。
