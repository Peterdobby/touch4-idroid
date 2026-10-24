# c5cee8c 的实际菜单调用链

以下以本地真实 `c5cee8c` checkout 为基线；新增诊断不会改变显示初始化顺序。

```text
arch-arm/entry.sx: ArmReset → OpenIBootStart
openiboot.c: OpenIBootStart
  → plat-a4/a4.c: platform_init
      → arm_setup → mmu_setup → tasks_setup
      → 原有时钟、中断、GPIO、timer、I2C、DMA、SPI、AES 初始化
      → plat-a4/clcd.c: displaypipe_init
          → LCDInfoTable[DISPLAYID]；N81 的 DISPLAYID=2
          → createWindow / createFramebuffer
          → configureLCDClock
          → pinot_init
              → plat-a4/mipi_dsim.c: mipi_dsim_init
              → MIPI panel-ID 读取、panel 开启
          → Gamma / window buffer 设置
          → CurFramebuffer = currentWindow->framebuffer.buffer
      → 仅 displaypipe_init 返回 0 才调用 framebuffer.c: framebuffer_setup
      → framebuffer_setdisplaytext(TRUE) / backlight
  → init.c: init_setup
  → OpenIBootMain = OpenIBootConsole
  → init_boot_modules
      → actions.c: setup_init；空 BootEntry 链表，current/default=root sentinel
      → 只有链接 menu 模块时：menu.c: menu_init_boot
          → OpenIBootMain = menu_main
  → OpenIBootMain()
      → 原版 T4：OpenIBootConsole → init_modules → acm_start → tasks_run
      → 若链接菜单：menu_main
          → task_init / init_modules
          → scripting.c: script_run_file("(0)/boot/menu.lst")
              → script_load_file → script_load_hfs_file → bdevfs_open
              → 失败：打印 NOT FOUND，OpenIBootConsole，return
              → 成功：script_run_commands → command_run
                  → title 命令 → actions.c: setup_title → malloc BootEntry → 链入链表
          → temp-os 分支可能 nvram_save / setup_boot（测试版完全跳过）
          → setup_entry(setup_default())
          → framebuffer_setdisplaytext(FALSE)
          → menu_draw：每个 BootEntry 的 title + 固定 Console 行
          → task_start(menu_run)
              → buttons_is_pushed → gpio_pin_state
              → setup_entry(next/prev) → menu_draw
              → Home 原版可 setup_boot；测试版禁用
```

关键源码位置：

| 文件 | 函数 / 决定 |
|---|---|
| `plat-a4/iPodTouch4G.SConscript` 与 `plat-a4/SConscript` | 原版未 AddModules(menu)，不能因根 SConstruct 读取了 menu/SConscript 就认为 menu 被链接。 |
| `openiboot.c:OpenIBootStart` | 默认入口明确为 Console；boot modules 可以覆盖它。 |
| `menu/menu.c:menu_main` | 配置加载失败直接 console；成功后才执行 menu_draw。 |
| `actions.c:setup_init/setup_title` | 空 root sentinel 与动态创建系统条目的区别。 |
| `menu/menu.c:menu_draw` | Console 是额外固定行，不是第三个新建 BootEntry。 |
| `plat-a4/includes/hardware/clcd.h` | CONFIG_IPOD_TOUCH_4G → DISPLAYID 2；framebuffer 地址定义。 |
| `plat-a4/clcd.c:LCDInfoTable/pinot_init` | 真正的 n81 显示参数及面板初始化；没有独立名为 n81_init 的函数。 |

**USB ACM 可用不能单独证明 framebuffer_setup 成功。** `a4.c` 在 displaypipe_init 返回非零时跳过 framebuffer，却继续走到 USB 模块。相反，若确认是该源码路径运行，ACM 出现说明 platform_init 已返回，不代表显示返回值为零。新诊断明确记录这个区别。

本 commit 的 `menu_draw()` 是 framebuffer 文本列表，当前项反色；PNG 三图标的 include/构建项已注释。此次沿用该 renderer，不重新制作图标菜单。
