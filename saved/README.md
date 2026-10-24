# saved/

这里保存本地生成物、下载、依赖、完整包、日志、设备专属输入和冻结成功快照。Git 只跟踪本说明和空目录标记。

- `build/`：构建、诊断和主机检查产物。
- `releases/`：完整工具包及只读成功快照。
- `packages/`：从自有包导入的运行材料。
- `state/`：新入口的安装日志、组件缓存和审计。
- `downloads/`、`sources/`、`research/`、`toolchain/`、`dependencies/`：上游输入和工具。
- `private/`：本机配置、票据与校准。
- `history/`、`experiments/`：历史和失败版本。

原工作区的 `build/`、`releases/` 等软链接用于兼容旧命令；实际内容已在这里。冻结成功版保持原样，新实验使用新版本目录。
