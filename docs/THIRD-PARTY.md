# 上游与许可证

保留各文件中的原始版权。整合代码按根目录 GPL-3.0-or-later 发布；Linux 衍生内容和第三方源码按各自声明处理。

| 组件 | 来源 / 基线 | 许可证范围 |
| --- | --- | --- |
| OpeniBoot | [iDroid-Project/openiBoot](https://github.com/iDroid-Project/openiBoot)，`c5cee8c` | GPL-3.0-or-later |
| iDroid Linux | [iDroid-Project/iDroid-kernel](https://github.com/iDroid-Project/iDroid-kernel)，`idroid-3.0.0` | Linux GPL-2.0；内核衍生修改保留该版本 |
| Legacy iOS Kit | [LukeZGD/Legacy-iOS-Kit](https://github.com/LukeZGD/Legacy-iOS-Kit) | 外部依赖，不随源码快照打包其完整工具集合 |
| libirecovery 源文件 | `tools/libirecovery-1.3.1.c`，保留原始版权头 | LGPL-2.1，按原文件声明 |
| libusb、ARM 工具链 | 外部构建依赖 | 不附带编译后二进制，保留上游许可 |
| androidi4 / Android 用户空间 | 已有本地实验包 | 未随公开库分发，未对整个包作许可声明 |
| Apple 固件、iBoot、DeviceTree、票据、N1 固件 | 本机自备输入 | 不包含在公开库，根许可证不覆盖它们 |

`LICENSES/` 保存相关 GNU 许可证文本。`linux-ramtest/` 中的内核源码和生成的内核修改，以及 `patches/kernel-ramtest.patch`，保留 Linux GPL-2.0 范围。公开发布未重新许可专有固件，也未移除第三方文件版权。
