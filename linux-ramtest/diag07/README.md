# T4_LINUX_DIAG_07：持续内核日志及 RAM PID1 尝试

06 实机反馈 `22`：已进入内核早期 C，首次 printk 返回。06 原产物保留，反馈与源码
快照在 experiments/linux-ram-06-checkpoint22/。本版本不再在正常编号处主动停止。

```bash
cd .
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_LINUX_DIAG_07 --boot
```

22 继续进入 setup_arch；23 表示机器选择与早期参数解析已经返回，下一步启动原生
framebuffer console。原生控制台显示累积的真实 printk，再显示
`T4_DIAG_07: NATIVE_CONSOLE_READY`，随后继续内存、时钟、中断、定时器及 initcalls。
若成功执行原最小 initramfs 中的 /init，将周期性看到 `PID1_REACHED`。
原 initramfs 的 marker 仍含旧名称 T4_LINUX_RAM_01，未改动该已校验产物。
不要将 NATIVE_CONSOLE_READY 或任何编号认作用户空间/Android 成功。
如果失败，记录最后的真实日志；23 前则记录完整编号文字。

## 原生控制台交接

zImage/压缩内核/initramfs 与已验证 06 相同，仍先通过原 Image CRC 才应用 RAM 诊断补丁。
22 补执行原 add/BL，以 **原内核返回地址 c0008658** 调用 setup_arch，避免它在页表清理
后返回已撤销映射的 helper。新增 b5a0 钩子在 parse_early_param 返回后调用内核原有
t4_ramfb_console_init；保存/恢复全部寄存器与条件标志，再补执行原 LDR/BL。
24 只通过真实 printk 输出日志，不再直接覆盖 framebuffer。

19 增加 framebuffer 的内核直接映射（实测地址对应 c8104580 -> 08104580），
使用所选 proc_info 的 kernel RAM flags。prepare_page_table 清除低地址 helper 映射时，
该地址仍在首个 256MiB RAM bank 内，随后由 map_lowmem 接管。原控制台完全使用
内核自己的代码、字体、全局变量和 __va 像素地址，不依赖已撤销的 helper。
诊断映射发生冲突就停止，不覆盖已有项。

t4_map_io 原入口改成直接跳转原 s5l8930_map_io，避免同一个 console 被重复注册。
其余原有时钟/UART、IRQ、timer、machine init 继续执行。LCD/MIPI 初始化调用仍保持此前移除状态。

## NAND/NOR 限制

审查发现 CONFIG_MTD 虽关闭，但独立的 Apple block NAND 栈仍编入了原内核，
尤其 dev-h2fmi.c 的 register_vfl 是 late_initcall，不能仅凭板级未注册 H2FMI 就放开启动。
本版本在任何内核 initcall 前，对解压后的 RAM Image 同时应用并校验：

- h2fmi_mod_init、register_vfl、s5l8930_register_h2fmi 入口直接返回 0，跳过注册/探测。
- apple_nand_write_page、apple_nand_erase_block、h2fmi_nand_write、h2fmi_nand_erase
  入口返回 -ENODEV，阻止这组 NAND 写入/擦除 API。

core-patches.h/manifest.json 记录每处旧指令、新指令与地址；整段修改后的 Image 再比较 CRC。
没有修改原文件或设备存储。MTD/NOR、MMC、ATA、SCSI、USB storage 未启用。
板级 H2FMI 注册此前也已去除。仅使用内含 /init 和 RAM 字符设备节点的最小 initramfs；
不使用 Android ramdisk，不挂载任何持久分区，/init 只向内存中的 /dev/kmsg 写日志。

## 当前完成条件

本轮还需确认：持续原生 printk、RAM 用户空间 PID1。编号是故障定位标记，没有预定总数。
PID1 通过后再评估 Android initrd/rootfs；不能由 kernel C 或 PID1 成功推断 Android 可运行。

```bash
python3 linux-ramtest/diag07/build.py
python3 linux-ramtest/diag07/test_layout.py
python3 linux-ramtest/run.py --build T4_LINUX_DIAG_07 --check
```

离线机器码、跳转返回地址、NAND stub/initcall 入口、临时页表冲突回滚、ATAG、
模拟 USB 以及旧版本哈希检查日志存于 build/T4_LINUX_DIAG_07/。
所有硬件结果待用户测试。
