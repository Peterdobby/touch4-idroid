# T4_ANDROID_INIT_01

沿用已实机到达 PID1 的 DIAG12，zImage、实际 RAM 中 patched Image、resident.bin 均逐字节相同。
改动仅为新 RAM initramfs、校验常量和测试版本标签。DIAG12 原产物保留。

从用户 androidi4.zip/ramdisk.img 读取原始 /init，SHA256：
d67ec53adf54cbdb9e38c6cce4d324f5f1c4908abd4630169c438134057c520f。
此 ELF 以 /android-init 放入 RAM，未改动一个字节；静态 ARM ELF、无解释器。
/bootstrap /init 打印 EXEC 请求后，execve(/android-init, argv[0]=/init) 保持 PID 1。
真正的原版 Android init 负责解析本次最小 init.rc 并启动 /sbin/t4-probe。
服务打印父 PID，再打印 ANDROID_INIT_SERVICE_REACHED。bootstrap 自身不会打印成功标记。

init.rc 只含三个阶段 write /dev/kmsg、loglevel 和 start RAM 测试服务。
不包含原 ramdisk 的存储脚本、import、ueventd、原始 system/userdata/cache 镜像、Android 系统服务。
只创建 RAM 目录、字符节点、静态 ELF 和最小配置，无块设备节点。
/dev/console 使用 kmsg 字符设备供早期测试输出；不是交互终端，不代表 Android 显示驱动已就绪。

目前内核未启用 NET/UNIX socket、tmpfs、ashmem/binder 等完整 Android 所需功能。
原 init 的内置挂载/property/socket 初始化可能报错甚至阻止本阶段完成。
本次专门确认原 ELF 的实际执行、RC 处理和服务启动，不声称能运行桌面。
不要把 EXEC 请求标记或 USB 断开当作 Android init 已经正常运行的证明。

实机命令（重新进入 DFU）：

```bash
cd .
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_ANDROID_INIT_01 --boot
```

成功证据：T4_ANDROID_INIT_BOOT_ACTION，随后 ANDROID_INIT_SERVICE_REACHED。
若失败，请记录 EXEC_FAILED 的返回值，或最后一屏 Android init/kernel 错误。
所有设备修改只在 RAM，NAND/NOR 初始化与写入阻止措施保持；没有重新编译或覆盖成功内核。

重建与离线验证：

```bash
python3 linux-ramtest/android-init01/build.py
python3 linux-ramtest/android-init01/test_layout.py
build/t4-arm-tests-venv/bin/python linux-ramtest/android-init01/test_probe_arm.py
python3 linux-ramtest/run.py --build T4_ANDROID_INIT_01 --check
```
