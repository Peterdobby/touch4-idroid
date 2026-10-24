# RAM 与存储边界

本项目包含持久菜单安装和 RAM Android 运行，两者的保存范围不同。

## 安装

在已有 Kit SSH ramdisk 中读取主系统、身份、内核、DRA、NVRAM 和空间，确认后新增启动文件，通过现有 Apple 接口完整提交启动镜像组：LLB 在先，其余六个镜像在后。

本机文件包括 `/boot/t4/android.img3`、5.1.1 路线的 `/boot/t4/ios-iboot.img3`。原 MENU03 的 7.1.2 路线另有匹配的本地 DeviceTree 文件。

菜单和文件可以持久保存在设备上。安装器不执行擦除、重新分区、替换原 iOS kernelcache 或设置 NVRAM。

## Android 运行

菜单通过已有 iBoot 文件接口读取 `android.img3`，校验并将内核、initramfs 和相关段放入 RAM，再交给 Linux 和 Android。启动过程中会读 NAND 上的文件；Android 运行环境仍在 RAM，没有已实现的持久 Android 数据分区。

| 使用场景 | 当前表现 |
| --- | --- |
| 桌面、真实触摸、Home 和音量键 | 已实测 |
| ADB shell | 已实测 |
| 修改设置、安装应用或创建数据 | 当前运行期间生效，占用 RAM，重启后不保留 |
| Android 中访问完整 iOS 用户存储 | 不属于已实现功能 |
| 拔线重启 | 菜单保留，Android 每次重新加载 RAM 环境 |

有限内存需要同时容纳内核、解压后的系统文件、应用和临时数据。没有长期使用、完整休眠恢复或掉电数据保护的验证记录。

## saved/ 约定

| 目录 | 用途 |
| --- | --- |
| `saved/build/` | 编译、镜像、诊断产物 |
| `saved/packages/` | 导入的本机完整安装包 |
| `saved/state/` | 安装日志、组件缓存、审计 |
| `saved/releases/` | 工具包和冻结成功快照 |
| `saved/downloads/` | 下载缓存 |
| `saved/private/` | 本机配置、票据、校准 |
| `saved/history/` | 历史材料 |

Git 只保留说明和空目录标记，实际生成物和私有数据不提交。现有只读备份不等于完整 NAND/NOR 转储。
