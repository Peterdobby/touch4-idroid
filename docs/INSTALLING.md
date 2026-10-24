# 使用已有的本机安装包

公开库不附带 Apple 固件、签名票据、androidi4 用户空间包、N1 固件与校准。完整 02.4 包来自本地成功构建，具有设备身份和输入校验，不能直接作为任意设备的通用安装包。

## 导入

```bash
python3 tools/import-installer.py /path/to/T4-Android-Installer-02.4.zip
```

导入器检查 ZIP 路径、文件清单、大小和 SHA-256，保存到 `saved/packages/T4-Android-Installer-02`。它不连接设备。

## 运行

用现有 Kit 进入 SSH ramdisk，保持转发并挂载系统卷。当前使用端口 6414，实际端口与 Kit 路径可在菜单中设置；这里不负责重装 iOS。

```bash
bash start.sh
```

先选择检查查看设备和版本。需要安装时选择安装并确认实际版本。安装入口将本次状态保存在 `saved/state/installer02/`。

也可执行单个动作：

```bash
bash start.sh verify
bash start.sh check --port 6414 --kit "$HOME/Legacy-iOS-Kit"
bash start.sh install --port 6414 --kit "$HOME/Legacy-iOS-Kit"
```

## 分别确认结果

1. `COMPLETE_IMAGE_SET_API_ACCEPTED` 只代表更新接口接受镜像。
2. OpeniBoot `0525:1280` 与正确 `version` 回包代表实际运行。
3. 屏幕菜单和选择移动需要观察。
4. iOS、Android、触摸和按键分别确认。
5. 拔线重启后仍有菜单和系统，才确认独立启动。

保留固件提交中断、未知结果与冷启动失败的日志和 ramdisk。旧版本遗留 RAM 锁已区分处理，不应只删锁后盲目重复提交。原工具包的既有审计路径不自动迁移，复制旧记录时需要一并保留引用的备份。
