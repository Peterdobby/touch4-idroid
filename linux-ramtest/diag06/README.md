# T4_LINUX_DIAG_06

05 实机反馈：`15`。已通过原 Image 解压校验与压缩头 cache clean/off 返回边界。
05 产物保留；反馈与源码快照在 `experiments/linux-ram-05-checkpoint15/`。

## 运行

设备重新进入硬件 DFU 后执行：

```bash
cd .
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_LINUX_DIAG_06 --boot
```

预计最后主动停在 `22 FIRST PRINTK RETURNED - STOP`，下方显示真实内核的版本字符串。
回报最后完整编号文字；若变蓝屏，记录变色前最后编号。22 仍不是用户空间或 Android 成功。

|编号|真实执行边界|
|---|---|
|15|原 Image CRC 通过后，在 RAM 应用六处内核入口探针，再校验修改后 CRC 并同步取指缓存；继续跳入内核|
|16|物理 0x8000 的 stext 已转入入口探针，检查 r0/r1/r2|
|17|__lookup_processor_type 返回，检查 proc_info 地址并显示真实 CPU ID；继续原 MOVS|
|18|原 __vet_atags 返回，检查 r2 仍为 0x100|
|19|原 __create_page_tables 返回；检查 MMU/D-cache 仍关闭，然后补入诊断模块与 framebuffer 的临时映射|
|20|内核页表已启用，PC 已到虚拟 __mmap_switched 入口探针；继续原 data/BSS 处理|
|21|start_kernel 的 C 函数序言与 smp_setup_processor_id 调用已执行；继续 debug_objects_early_init 等原代码|
|22|真实 printk(linux_banner) 已返回；在 setup_arch 调用前主动停止|

若出现 BAD/REFUSED/UNSUPPORTED，记录完整文字。单凭某一编号后蓝屏，不能认定某条
具体指令必然失败；下一边界尚未确认，诊断绘图本身也属于这段范围。

## 具体修改与限制

上传的 **zImage 与 05 逐字节相同**。保留其解压算法、压缩输入、诊断文字输出和
原 Image CRC 校验。改动通过 helper 在 **解压后的 RAM Image** 上应用；没有更改磁盘中的
原 zImage/Image/vmlinux。Image.instrumented 是用于离线对照的副本，不直接上传。

六处各 8 字节的绝对跳转：0x8000、0x800c、0x8024、0x8180、0x85fc、0x8650。
原指令、目标向量与 ELF 符号均在构建时校验，写入前再次校验；修改后的整段 Image 再核对 CRC。
core-patches.h 与 manifest.json 记录完整列表。最后一处主动停止，不调用 setup_arch。
原指令的返回、PC 相对地址和 BL 语义由 entry.S 对应 stub 补回；错误 CPU 结果主动停止。

内核初始页表默认不覆盖 helper 的 0x44000000、共享 INFO 的 0x43f00000 和继承
framebuffer 的高地址别名，因此 19 只在空页表项中补入这些诊断映射。
helper/INFO 采用所选 proc_info 的原 kernel MMU flags，framebuffer 采用原 IO flags；
任何冲突、地址越界或不可执行 helper 属性都拒绝继续。没有替换原页表生成或 CPU/MMU 设置函数。
这属于额外的诊断映射，不能把结果当作完全未经干预的内核启动。

__mmap_switched 入口的 r13 是虚拟跳转目标，不是栈。20 使用独立 RAM 栈
0x44010000，返回前恢复 r13，再补执行原 ADR/LDM。helper 限定低于 0x44008000，
为诊断栈保留至少 32 KiB。21/22 使用内核已设置的栈。所有普通探针保存 r0-r12、lr 和条件标志。

未执行板级 init、Android initrd 或持久化存储操作；未改 LCD/MIPI，不写 NAND/NOR。
22 后主动停住，临时映射只服务本次 RAM 实验，重启消失。

## 重建及检查

```bash
python3 linux-ramtest/diag06/build.py
python3 linux-ramtest/diag06/test_layout.py
python3 linux-ramtest/run.py --build T4_LINUX_DIAG_06 --check
```

handoff.ld 固定 ARM 向量先于编译器可能生成的 cold text，构建后检查所有向量地址；
这是本轮离线检查发现并修正的布局问题。另一处首次链接错误是 banner 换行除法依赖
__aeabi_uidiv，已改为行列计数；最终 helper 无未解析符号。
最终反汇编、SHA256、机器码/页表映射/ATAG/模拟 USB 检查日志在 build/T4_LINUX_DIAG_06/。
