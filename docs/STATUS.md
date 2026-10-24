# 验证范围

最后整理：2026-10-24（Asia/Shanghai）。

| 项目 | 实际使用 |
| --- | --- |
| 设备 | iPod touch 4G，iPod4,1 / N81AP，Apple A4 |
| OpeniBoot | 0.3，commit `c5cee8c` |
| 基础引导 | 已有 Kit DRA6 / DRV6 环境，10B500 基础组件 |
| Linux / Android | 3.0.8 / 2.3.7，RAM 用户空间 |
| 主机 | Intel macOS；其他环境没有完整覆盖 |

## 已实测

1. **iOS 5.1.1 / 9B206，Installer 02.4 / MENU04**：重启后 OpeniBoot `0525:1280` 枚举，`version` 返回 `openiboot 0.3 commit c5cee8c for iPod Touch 4G`。用户确认进入 iOS，随后确认拔线有菜单、Android、触摸和按键正常。
2. **iOS 7.1.2 / 11D257，先前的 Kit 移植版 / MENU03**：用户此前确认 iOS、拔线菜单、Android、触摸和按键正常。这是特定移植版，不是官方支持 iPod touch 4G 的普通 iOS 7 安装。
3. Android RAM 构建的 root ADB shell 与 OpeniBoot ACM 命令回包均有实机记录。

只有这些具体组合建立了实机记录。iOS 4/6、其他小版本与其他设备仍待验证；下载组件成功不能证明可启动。

## 02.4 的修正

首轮 5.1.1 安装的更新接口全部返回成功，但重启进入 DFU。生成器把持久 `dtre` 换成目标 9B206 文件，其他基础镜像和 APTicket 仍来自 10B500。

02.4 恢复原成功版的六个基础镜像，只保留自有菜单 `ibob` 的变化。目标 iBoot 仍从本机文件加载。此后实际重启 USB/version、iOS 和拔线 Android 反馈均通过；没有修改原 iOS 内核、DRA 分区、分区表或 NVRAM。

更新回执、主机模拟检查、软件重启 USB、用户屏幕确认和拔线启动分别记录。公开仓库提供移除设备标识的摘要，原始日志和冻结快照留在本地 `saved/`。

## 限制

- Android 用户空间和用户数据在 RAM，重启丢失修改。
- 没有持久 Android userdata/cache，也没有证明 Android 已具有一般 NAND 读写能力。
- 真实触摸依赖正确的 N1 固件与本机校准，不能直接复用其他设备的校准。
- ADB 的主机、平台工具版本兼容范围尚未全面测试。
- Wi-Fi、音频、相机、蓝牙、完整电源管理与长期稳定性未列为已验证可用。
- 成功包与本机身份绑定；公开仓库不是通用预签名安装包。

02.4 通过 32 项安装状态测试、22 项组件和镜像组测试。它们验证更新顺序、包损坏拒绝、缓存保留、失败审计和 RAM 锁等情形，不替代实机验证。
