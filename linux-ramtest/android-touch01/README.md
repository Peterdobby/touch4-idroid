# T4_ANDROID_TOUCH_01

基线为实机可进入桌面并有 root ADB 的 T4_ANDROID_ADB_01。保留其所有 USB、
显示、按键、Android init/Framework 文件及 RAM-only 存储限制。仅增加内核
CONFIG_INPUT_MISC / CONFIG_INPUT_UINPUT 和一个 N1 → Linux MT Type A 输入服务。
原版本及 OpeniBoot 文件均独立保留并校验 SHA256。

触摸初始化复用 CLOCK15：本机 iOS0098固件、本机1024字节 MtCl、SPI1、N1校准，
以及实际 AppleD1815PMU clock_enable参数3对应的 GPIO0高阻模式51。旧模式13
会导致 ROM/HBPP可用但固件运行接口不响应。只写 PMU GPIO0寄存器50，退出时恢复；
不修改电压、LDO、USB、IRQ或任何非易失存储。

真实硬件证据：CLOCK15 log20261022-222542中49个校验通过的手指帧，X范围-115..4528、
Y范围218..5426，44个有压力帧、5个抬起帧。用这49帧回放新输入边界，输出真实位置、
移动及抬起事件；ASan/UBSan检查通过。Linux3.0 ARM uinput结构和ioctl编码编译校验通过。
这些检查不替代此新内核的实机启动、evdev与桌面触摸验证。

坐标按已有 iDroid FingerData处理：X=rawX，Y=SensorHeight-rawY；传入 D9报告的
5000×7500传感器范围，不在驱动里硬缩放到屏幕像素。压力major/minor均非零才视为
有效接触；空/抬起帧发Type A释放。包校验和、类型、长度、finger stride和数量都验证。
没有 Android input/monkey注入，也没有模拟手指位置。Android可以按abs范围映射到屏幕；
四角方向及边缘准确度仍需实机确认。

构建：

```sh
python3 linux-ramtest/android-touch01/build.py
python3 linux-ramtest/run.py --build T4_ANDROID_TOUCH_01 --check
```

硬件DFU后，只执行RAM启动：

```sh
python3 phase1/run.py --boot --published
python3 linux-ramtest/run.py --build T4_ANDROID_TOUCH_01 --boot
python3 tools/t4-adb-check.py --wait 120
python3 tools/t4-touch-check.py
```

若旧日志在 initramfs 100% 后直接结束，还没有执行 Linux；不能手动补一个 boot。
4MiB分段版的实机日志231559仍在第5段超时，故不能视为已修复。
上传协议v2改为每1MiB确认一次精确接收结束地址，并要求version往返；
每16KiB暂停1ms，命令边界暂停2ms，避免连续全速请求。
末包只在USB传输上补到512字节，sendfile仍声明真实字节数，OpeniBoot丢弃多余尾字节，
RAM中的镜像不变。失败后最多两次重置USB连接、重新打开并确认c5cee8c version，
之后只重传未确认的区间。若重置或版本确认失败立即停止；不会盲发数据或boot。
现有整镜像CRC stage验证仍必需。这是电脑端传输修正，未修改OpeniBoot或Linux镜像。
旧上传失败后若version也不响应，需要重新进入硬件DFU并运行上面的两个boot命令。
本次仍需实机确认，不能把离线模拟当成USB恢复或触摸成功。
电脑端回归检查：`python3 linux-ramtest/android-touch01/test_upload.py`。

新的 init.rc自动启动 t4-touch。它把校验通过的控制器帧交给 /dev/uinput，注册
“T4 Multitouch”；Android沿用原EventHub/InputReader。使用打印出的getevent命令
观察真实触摸事件，并实测Launcher点击/滑动。仅注册成功不能宣称桌面触摸成功。

不要在运行输入服务时再运行 CLOCK15 等独立诊断，它们会因硬件正在使用而拒绝。
如需停止，使用 `adb shell stop t4-touch`，使服务经SIGTERM走完整清理，恢复
SPI/GPIO/PMU并销毁uinput设备。重启会清除所有本阶段修改。不要强杀触摸进程。
