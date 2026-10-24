# T4 Android 安装工具 02.4：自动获取启动组件

这是持久安装测试版。用途：在同一台已验证的 iPod4,1 / N81AP（ECID `YOUR_DEVICE_ECID`）上，使用现有 Kit DRA6 安装 iOS 后，从 SSH ramdisk 一次完成 iOS / Android / Console 菜单安装。原成功的 MENU03 和工具01保留。

02.4 修正基础启动组件混用。5.1.1 首轮冷启动进入 DFU，原配置把持久 dtre 换成了目标 9B206，而其他基础组件和 APTicket 保持 10B500。现保留已验证的六个 10B500 基础镜像，仅更换自有菜单 ibob；目标 iBoot/DeviceTree 原文件另保留。旧电脑配置完整备份到缓存下 `.history/`，再更新镜像组，不覆盖失败样本。恢复基础 dtre 后，实际重启的 OpeniBoot USB/version 已通过，用户随后确认 iOS 5.1.1 能启动，以及拔线重启菜单、Android、触摸和按键正常。

02.3 处理旧版本成功提交后留下的 RAM 锁：再次选择安装时，核对已完成记录、设备/版本/内核、启动文件、NVRAM，以及仍留在本次 ramdisk 随机工作目录中的原提交包和助手；一致则直接提示已完成，不重新提交固件。单有电脑历史记录不足以跳过安装，换过 ramdisk 或恢复系统后必须重新检查。无法确认的锁和未完成提交仍保留并停止，不盲目删除锁。遗留 RAM 锁在重启后自动消失。

02.2 修复 Kit ramdisk 缺少 `/bin/rmdir` 导致的收尾报错。成功提交并确认 NVRAM 不变后，将本次 RAM 安装锁移入本次 RAM 工作目录，不依赖 rmdir；即使清理失败，也单独记录提示并保留已完成状态。用户 2026-10-24 的 5.1.1/9B206 安装记录已为 `COMPLETE`，七镜像更新接口返回成功，随后才发生原 rmdir 报错。这次安装无需重复提交，拔线启动效果仍待实机确认。

02.1 修复了身份探针的 IOKit 动态库路径：使用 ramdisk 实际提供的 `IOKit.framework/Versions/A/IOKit`。此前“读取 ECID 失败”实际为 dyld 找不到库，并非 ECID 不匹配；现在保留探针退出码、标准输出和错误日志。已有电脑端组件缓存中的旧探针会在完整校验后更新，不修改原来的硬链接备份。

2026-10-24 已在本机 SSH ramdisk 实测菜单1完整通过：iPod4,1、ECID、iOS 5.1.1/9B206、现有内核、DRA6/NVRAM、LLB只读预检查和剩余空间均通过。该检查没有执行持久写入；5.1.1 新启动入口仍需安装后实机验证。

## 使用

需要 macOS、Python 3.9+、现有 Legacy-iOS-Kit，以及已经运行的 Kit SSH ramdisk。工具不负责恢复或刷写 iOS；请先用 Kit 安装要测试的主系统，并保持 SSH 转发（默认6414）。

```sh
bash start.sh
```

- 菜单1：读取主 iOS，自动获取匹配组件并检查。不写持久存储，辅助程序只在已确认的 ramdisk RAM 根目录执行。
- 菜单2：同样自动识别与准备，然后显示实际设备和版本；确认一次即可持久安装，不要求先做 RAM 启动试验。
- 菜单3：可在刷机前离线准备，例如输入 `5.1.1`。无需连接设备、无需完整自制 IPSW。
- 菜单4：设置 SSH 端口和 Kit 路径。

也可以直接运行：

```sh
bash start.sh prepare --version 5.1.1 --kit "/你的/Legacy-iOS-Kit路径"
bash start.sh install --port 6414 --kit "/你的/Legacy-iOS-Kit路径"
```

安装时不接受人为覆盖版本号，会读取 `/mnt1/System/Library/CoreServices/SystemVersion.plist`。已准备的组件会校验后复用。

本次随包提供已经实际下载并生成的 **5.1.1 / 9B206** 配套配置，首次展开也无需重新下载；它复用包内 Android 和公共辅助文件，不额外重复一份 Android。其他版本走相同的在线准备流程。

## 自动准备的实际流程

1. 按 iPod4,1 和实际 iOS/build 查询固件位置，再从 Apple HTTPS 固件用 Kit 的 `pzb` 分段提取 `BuildManifest.plist`、iBoot 和 DeviceTree。
2. 验证清单中的版本、build、N81AP 身份和组件名称。只处理该设备存在的正式 iOS 4/5/6 版本；没有声称支持 beta 或所有版本已经实测。
3. 获取 Kit 自身固定提交的密钥数据，调用原有 `xpwntool` 解密和原有 `iBoot32Patcher` 处理。不修改、增强或重新编写这些工具及漏洞代码。
4. iOS入口经原有受控 iBoot6 的文件读取和 CPU 交接函数，进入匹配系统的目标 iBoot。基础固件的 dtre 保持已验证的10B500文件；目标版本 DeviceTree 保留在电脑配置中，不替换基础固件。本机5.1.1/9B206已实际进入iOS，其他版本仍需分别验证该交接。
5. Android 仍使用原 TOUCH03 kernel/initramfs/handoff；Linux、触摸、按键和 ADB 文件不重新编译。

固件 URL 来自版本目录，组件实际取自 Apple。Kit 密钥清单固定提交：
`https://github.com/LukeZGD/Legacy-iOS-Kit-Keys/tree/033cbc09511de587e1ea4255e26662be543cbb51`

## 持久修改范围

新增 `/boot/t4/android.img3`、`/boot/t4/ios-iboot.img3`；同名相同内容复用，不同内容保留并停止。通过成功版使用的 Apple 更新接口完整提交七个启动镜像：LLB先提交，再提交其余六个；六个基础镜像与原成功版逐字节一致，仅 ibob 为本次菜单。

不替换原 iOS kernelcache，不擦除、不分区、不写 NVRAM，也不修改原 DRA 分区。安装成功只表示完整API提交成功；首次拔线启动仍需你的实机测试。工具不自动重启、不自动重试未完成的固件提交。

默认日志、原kernelcache、DRA分区副本、NVRAM、组件哈希、Kit工具哈希和安装审计存放于：
`~/Library/Application Support/T4-Android-Installer-02/`

这些备份不是完整 NAND/NOR 转储。Android 的系统和用户运行环境仍在 RAM，重启不保留 Android 中的数据。

## 测试状态

原 MENU03 的7.1.2、Android和拔线菜单成功版保持原样。02.4在本机iOS 5.1.1/9B206上已通过：重启后0525:1280与c5cee8c版本回应、iOS启动，以及用户确认的拔线菜单、Android桌面、触摸和按键。32项安装状态测试和22项组件/完整镜像组测试通过。iOS 4、6及其他尚未测试版本沿用自动准备流程，尚未声称实机通过；出现差异会保留组件和日志。

包内 `provenance/` 保存主机测试结果和编译ARM入口模型测试结果。模型测试不会连接设备，也不能替代真实启动结果。
