# 构建与私有输入

这是已验证工作区的源码发布。完整二进制保存在本地 `saved/releases/`。克隆后可运行离线检查；完整固件重建仍需要原有输入、工具链和受保护基线。

## 依赖

- Python 3.9+、Bash、Clang，现有 Legacy iOS Kit。
- GNU ARM EABI 工具链，用于 ARM 段。
- Mach-O 助手构建使用 macOS Clang、`ld-classic` 和本地链接桩。
- 完整菜单依赖 OpeniBoot `c5cee8c`、已捕获的受控 iBoot 环境、Android TOUCH03 和校验清单。
- 本机 Apple 输入、签名票据、N1 固件和校准由使用者自行提供，不提交到公开库。

## 布局

公开源码的构建、上游输入、工具链和日志统一放入 `saved/`。历史脚本仍有原工作区的依赖约定，要结合输入清单准备；没有声称仅靠一次克隆就能从零重建完整固件。

原本机工作区通过兼容软链接保留旧 `build/`、`releases/` 等入口，实际内容已收纳到 `saved/`。成功快照按原清单保留，没有批量改写。

## 主要代码

| 目录 | 用途 |
| --- | --- |
| `installer/t4-android02/` | 02.4 安装器、组件下载、完整镜像组与测试 |
| `chainload/menu04/` | 目标 iBoot 菜单和 RAM 文件加载 |
| `chainload/menu03/` | 已验证的原 iOS 7.1.2 / Android 菜单基线 |
| `chainload/untethered-oib02/` | Apple 更新 API 顺序、预检查与完整组测试 |
| `linux-ramtest/android-touch03/` | 当前无顶部调试叠字的 Android RAM 构建 |
| `linux-ramtest/android-touch02/` | 真实 N1 触摸、低有效就绪与 Home 后触摸修复 |
| `phase1/` | 依赖外部 Kit 的现有 RAM 引导流程 |
| `tools/native_image.py` | 保持 raw payload 不变的 native 包装 |

## 离线检查

```bash
python3 installer/t4-android02/tests.py
python3 installer/t4-android02/test_profiles.py
python3 tools/test_native_image.py
bash -n start.sh installer/t4-android02/start.sh
```

这些检查不操作设备。native 包装校验和 raw 拒绝测试可独立运行；重建二进制的两项集成检查需要 GNU ARM 工具链和本机参考镜像，缺少时明确跳过。可用 `CROSS` 指定工具链前缀、`T4_REFERENCE_BUILD_DIR` 指定参考镜像目录。对已存在的受保护输出，构建器通常会拒绝覆盖；新实验使用新输出目录。

## 原生包装

具备对应基线和工具链时：

```bash
python3 tools/make-openiboot-native.py \
  saved/build/openiboot.bin \
  saved/build/openiboot-native-generated.bin
```

payload 位于 offset 0x1000，逐字节保持不变。该 wrapper 对应既有 4.1 iBSS 契约，不能视为任意 iBoot 的通用入口。

公开副本移除原机器绝对路径、ECID 和密码默认值。设备配置使用本地环境或私有输入；这种整理不等于对其他设备或其他 iOS 的实机确认。
