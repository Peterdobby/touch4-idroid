# T4_LINUX_DIAG_10

DIAG09 的用户照片显示内核已进入 setup_per_cpu_areas，尚未证明 PID1。
原图见 <HOME>/Desktop/IMG_8178.png 和 IMG_8174.png；09 源码、manifest、日志和判读保存在 experiments/linux-ram-09-first-fault/。

## 首个异常与连锁异常

照片中的完整栈包含：pcpu_dump_alloc_info+0x20 -> __dabt_svc -> do_DataAbort -> __do_kernel_fault -> die -> __irq_svc -> asm_do_IRQ -> generic_handle_irq -> handle_bad_irq。
C0135CE0 的机器码 E58D2027 是 STR r2,[sp,#39]，来自 mm/percpu.c 的 char empty_str[] 初始化。
这是 GCC 4.8 发出的未对齐普通 RAM 字写入。照片中 SCTLR=10C5387F，A=1、U=1。
这高度指向最先发生对齐异常；最初 Oops 的完整标题未捕获，因此保留实机确认条件。
旧内核 alignment_init 在 fs_initcall 才清 A；此时 per-CPU 初始化还在它之前。
随后 die 的 spin_unlock_irq 无条件开启 IRQ，此时 early_irq_init 尚未给 irq_desc 分配 kstat_irqs，
handle_bad_irq+0x188 读取 NULL，引起后续异常。不能把反复的寄存器/内存转储当作正常启动日志。

## 本版的有限修改

- 在原板级映射回调最开始，调用原生 noalign_setup(NULL)，提前执行内核已有的 noalign 路径。
  同时更新 cr_alignment、cr_no_alignment 和实时 SCTLR；要求 U=1，检查唯一变化为清除 A(bit1)。
  不直接修改 MMIO，不重新配置 LCD/MIPI，也不更换 zImage/压缩内核或 initrd。
- 保留 09 的显示时钟 OFF 保护、映射、RAM 保留、全部 NAND 初始化与写入/擦除入口阻止措施。
- 增加 per-CPU 返回和 IRQ 初始化前后标记，调用顺序及原生返回地址逐条核对。
- die 改跳 RAM resident 的首次致命异常记录并停机，先屏蔽 IRQ/FIQ，显示 PC/LR/CPSR/DFSR/DFAR/SCTLR。
  不再让 die 开启中断或退出当前任务，避免第一条异常被连锁 Oops 覆盖。此项仅用于诊断。
- 未修改 VIC2/VIC3 分发偏移，也未改变正常 IRQ 屏蔽/启用时序；本次先验证明确捕获的对齐故障。

## 运行

重新进入硬件 DFU 后执行：

```bash
cd .
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_LINUX_DIAG_10 --boot
```

若当前已经在公开 OpeniBoot，可仅运行最后一行。

预期逐步出现：

```
T4_ALIGN noalign EARLY before=10c5387f after=10c5387d
T4_INIT PERCPU RETURNED
T4_INIT IRQ_DESC BEGIN
T4_INIT IRQ_DESC RETURNED
T4_INIT VIC INIT RETURNED
```

只有 RAM /init 自己打印 PID1_REACHED 才证明用户空间已执行。
如停在 T4_FIRST_FATAL，记录完整三行；如没有致命异常行，记录最后一个标记。
离线检查通过不等于硬件成功；尚未测试本版设备启动。

## 重建与验证

```bash
python3 linux-ramtest/diag10/build.py
python3 linux-ramtest/diag10/test_layout.py
cc -Wall -Wextra -Werror linux-ramtest/diag10/test_resident.c -o build/T4_LINUX_DIAG_10/test-resident
build/T4_LINUX_DIAG_10/test-resident
python3 linux-ramtest/run.py --build T4_LINUX_DIAG_10 --check
```

所有设备侧修改只在 RAM 中发生。旧产物保留，不访问设备存储。
