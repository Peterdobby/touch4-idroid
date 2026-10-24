# T4 Android 安装工具 01

在已使用 Kit DRA6/DRV6 安装系统的 iPod touch 4G 上，通过已有 SSH ramdisk 安装成功版 MENU03：iOS / Android / Console。界面是 Bash 菜单，设备通信和安装校验由 Python 完成。无需电脑端编译器或原工程。

## 本测试包的适用范围

- macOS，Python 3.9 或更新版本、系统 SSH，以及现有 Legacy-iOS-Kit 的 `sshpass`。
- 本包的 Apple 签名材料只对应原已验证设备：iPod4,1 / N81AP，ECID `YOUR_DEVICE_ECID`。
- 自动读取主系统的 SystemVersion.plist 和 kernelcache；首版仅开放已实机验证的 Kit iOS **7.1.2 / 11D257**，内核 SHA-256 必须匹配成功版。
- 其他 iOS 会显示识别出的版本并停止。当前没有声称支持所有 DRA6 系统，也没有重新开发或修改漏洞代码。

## 开始测试

先用 Kit 自行进入 SSH ramdisk，并保持转发端口。可以已经挂载 `/mnt1`、`/mnt2`；若系统卷未挂载，工具只会先将它只读挂载到 `/mnt1`。不需要重新刷写当前已经正常的系统来测试检查功能。

```sh
cd T4-Android-Installer-01
bash start.sh
```

菜单 1 是检查：只读取持久分区；小型探针仅上传到 ramdisk 的 RAM 文件系统。会检查设备 ECID、主 iOS、内核、现有 DRA 分区、NVRAM、系统卷空间和 Apple 签名镜像接受情况。菜单 4 仅检查电脑端文件，完全不连接设备。

也可以直接运行：

```sh
bash start.sh verify
bash start.sh check --port 6414 --kit "/你的/Legacy-iOS-Kit路径"
bash start.sh install --port 6414 --kit "/你的/Legacy-iOS-Kit路径"
```

SSH 密码通过隐藏输入读取；回车使用 ramdisk 默认密码。日志不保存密码。

## 安装行为

选择菜单 2 后，工具先完成本次连接的全部检查，再显示设备与 iOS 并请求一次确认。确认后：

1. 新增 `/boot/t4/android.img3` 和 `/boot/t4/devicetree-ios7.img3`，逐字节回读。同名相同文件复用，同名不同文件停止。
2. 保留原 iOS 内核、原分区和 NVRAM。系统卷如果只读，会在安装时重新挂为可写；不操作 `/mnt2`。
3. 调用成功版的完整启动镜像组更新工具：LLB 先提交，再提交其余六个镜像。它会写入持久启动固件。
4. 保存返回结果，复查 NVRAM，不自动重启。用户重启后验证菜单和两个系统。

Android 仍是原 TOUCH03 的 RAM 运行版，触摸、按键、ADB 不变；Android 安装应用和设置不会因本工具而获得重启保存能力。

## 日志与备份

电脑端保存在 `~/Library/Application Support/T4-Android-Installer-01/`。每次有独立日志，保存系统版本、原 kernelcache、现有 DRA 分区、NVRAM 和安装返回记录；这些记录不是完整 NAND/NOR 备份。原工程的成功版归档继续保留。

发生未完成的固件提交时，工具会保留审计并阻止再次提交，不自动重试、不自动重启。检查模式仍可使用。安装完成提示表示 API 已接受，拔线启动结果需要实机确认。

本包是本机测试包，未公开上传至托管平台。`tests.py` 使用假的 SSH/设备模型验证错误拒绝、文件回读及完整提交顺序；它不会连接真实设备。原 MENU03 的实际拔线启动和触摸确认记录位于 `provenance/`。
