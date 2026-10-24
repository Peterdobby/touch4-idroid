# T4_ANDROID_TOUCH_03

实机在 TOUCH02 中热更新后，用户已确认触摸持续响应，且重复 Home 返回后仍可点击、
滑动。现场 evdev 抓到 1038 个事件、12 次按下和11次抬起；采集结束时一次接触尚未结束。
同时日志记录了 Settings 页面点击、Home 返回、再次进入 Settings 及子页面。
这不是 TOUCH03 整包从 DFU 启动的证据，整包冷启动仍需实测。

修复包含：

- N81 N1 就绪信号实测低有效。原先照搬 Z2 的高有效门控，导致真正待处理的触摸被跳过。
- N1 出错时保持 NOP，重新同步长度阶段；识别遗留完整数据包的已校验头，重新完整接收并
  校验数据后才送入 uinput，避免一直把数据前缀当作长度应答。
- SPI 在片选释放前关闭传输 FIFO，并保留片选高电平间隔。
- 保留本机 iOS 固件、MtCl、正常按键映射、ADB 和已有的 RAM 屏幕亮屏兼容层。

本版去掉 Android 顶部四行调试字。上传的 zImage、vmlinux、硬件初始化均来自原成功内核，
不重新编译内核。既有 RAM handoff 检查 t4_input_hud 的原始指令后，将该绘制函数入口改为
立即返回；更新整幅运行时 Image 校验和。仅抑制像素叠字，不改显示、按键或 USB 驱动。
启动过程的内核日志和 ADB 日志继续保留。

在项目根目录编译、检查：

```sh
python3 linux-ramtest/android-touch03/build.py
python3 linux-ramtest/run.py --build T4_ANDROID_TOUCH_03 --check
```

重新进入硬件 DFU 后：

```sh
python3 phase1/run.py --boot --published &&
python3 linux-ramtest/run.py --build T4_ANDROID_TOUCH_03 --boot &&
python3 tools/t4-adb-check.py --wait 120
```

不要同时运行 CLOCK15 或其他独立 SPI 采集程序。触摸服务独占 N1，真实手指帧经校验后
交给 Linux uinput；无模拟位置或 Android 输入注入。全部在 RAM 中进行，无 NAND/NOR、
分区、安装或擦除操作。旧 TOUCH01/TOUCH02、ADB01 和公开 OpeniBoot 保留并校验哈希。
