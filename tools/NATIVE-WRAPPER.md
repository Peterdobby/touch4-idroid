# N81 native RAM wrapper：已复现，主体是否可启动仍需独立实测

入口：`tools/make-openiboot-native.py`，共用实现 `tools/native_image.py`。
包装直接复用原有 `phase1/native_jump.S` 和原有 GCC/objcopy 参数，不改 payload。
`phase1/build.py`、`phase1/prepare_published.py`、`t4-menu/build.py`、
`t4-menu/public-overlay/build.py` 均改为调用该实现；没有修改设备端主体代码。

## 地址和实际控制流

```text
phase1/load.c
  → 上传固定 SHA256 的 N81 4.1 / 8B117 patched iBSS
  → Recovery bulk 上传 native image（本链使用 0x41000000）
  → control transfer: 0x40 / 0 / "go\0"
  → patched go 回调 0x41000000
  → launcher 设置 r0=0, r1=0x41001000, r2=0
  → BX 0x8401496d（切 Thumb）
  → iBSS jump_to 的实际指令地址 0x8401496c
  → 原生收尾流程
  → BLX r6，r6=0x41001000（切 ARM）
  → raw OpeniBoot 入口，自身 relocation
```

`0x8401496c` 是 RAM 中此版本 **iBSS** 的函数，不是 BootROM 通用地址。
`0x8401496d` 的 bit 0 表示 Thumb。它仅适用于项目锁定的 iBSS。
`0x41001000` 是上传起点加 launcher 预留的 4 KiB，并非主体的链接地址；
主体仍由自身入口重定位到其链接地址。

离线反汇编保存于 `build/native-wrapper-evidence/`：

- `jump-to.txt`：保存 r0/r2/r1 到 r4/r5/r6，调用多个收尾函数，最后
  `r0=r5, r1=r2=r3=0; blx r6`；若 payload 返回，留在自循环。
- `irq-disable.txt`：`0x84000584` 用 CPSR bit 7 屏蔽 IRQ，
  经 jump_to 的 `0x84014dfc` 调用链进入。
- `cache-clean.txt`：`0x84015d80` 按 set/way 清理数据缓存并执行同步。
- `cpu-shutdown.txt`：`0x8401614c` 调用上述缓存清理，再修改 SCTLR，
  掩码清除 M/C/Z/I 等位（MMU、D cache、branch prediction、I cache）。

launcher 自己只有五条指令和两个 literal，没有额外 copy/cache/MMU 代码；
相关工作由调用的 iBSS 函数承担。把 raw 直接交给 patched go 会绕过这些
收尾步骤，入口地址也从约定的 `0x41001000` 变成 `0x41000000`。
这解释了为什么本启动链要求 wrapper，但不能仅凭白屏断定某次失败的具体指令。

固件证据：`build/ibss-go-patch.json`，解密 raw 偏移 `0x20894` 的 go
函数指针由 `0x84000b99` 改为 `0x41000000`。`phase1/run.py` 强制校验实际
上传 iBSS 的 SHA256 为
`e8b10d73a72fbca026161bd4d4f169992092d8c0eed022540c8072bb5f5ddfcc`。

## padding 的准确规则

`.balign 4096` 保证 raw 从 offset `0x1000` 开始，并把 `.text` section 的
对齐提高到 4096；GNU ARM assembler 把 section 结尾补齐到同一边界。
不是固定总长 `0x42000`，也不是简单全零 padding。实际填充为短段 ARM NOP
再加零；原汇编器生成的模式原样保留，才能逐字节重现。

```text
native_size = align_up(0x1000 + raw_size, 0x1000)
tail_size   = native_size - 0x1000 - raw_size
```

| 本地版本 | raw | native | tail |
|---|---:|---:|---:|
| T4_DIAG_01 | 0x40e30 | 0x42000 | 0x1d0 |
| T4_MENU_01 | 0x41354 | 0x43000 | 0xcac |
| 成功公开版测试副本 | 0x437a0 | 0x45000 | 0x860 |

`tools/libirecovery-1.3.1.c` 的 `irecv_send_buffer` 对 Recovery **上传**采用
`0x8000` 分块，明确支持不足一块的最后一包；`0x2000` 出现在
`irecv_recv_buffer` 的 Recovery **读回**分块中，不能据此要求镜像对齐。
成功公开版 `0x45000` 本身也不满足 `0x2000` 整除。

## 构建、包装、校验、RAM boot

从项目根目录执行：

```bash
python3 t4-menu/build.py T4_MENU_01
python3 tools/make-openiboot-native.py \
  build/T4_MENU_01/openiboot.bin \
  build/T4_MENU_01/openiboot-native-generated.bin \
  --reference build/T4_MENU_01/openiboot-native.bin
cmp build/T4_MENU_01/openiboot-native.bin build/T4_MENU_01/openiboot-native-generated.bin
xxd -l 32 build/T4_MENU_01/openiboot-native-generated.bin
shasum -a 256 build/T4_MENU_01/openiboot-native{,-generated}.bin
python3 phase1/run.py --boot --file build/T4_MENU_01/openiboot-native-generated.bin
```

输出 `PAYLOAD_UNCHANGED` 及 `NATIVE_REPRODUCTION_EXACT`。
sidecar `<output>.json` 记录 raw/extracted SHA256、native SHA256、地址、大小。
`--file` 校验 launcher 和长度；有 sidecar 时还校验 payload 和整镜像 SHA256。
raw 在任何 USB 操作之前被拒绝。`phase1/load.c` 源码也加入相同入口检查，
重新构建加载器后生效；旧归档内的可执行文件没有被追改。

包装仅操作电脑上的输入/输出文件。启动过程不发送安装、擦除或存储写命令。
打包工具不审计任意输入主体的行为，也不能将不兼容的 payload 变成可启动代码。

## 本次验收结果（2026-10-18）

三个版本的 wrapper 均逐字节重现；包括之前实机失败的 DIAG，说明它当时已经
经过正确包装。原有实测成功的是公开版底座加 RAM UI 模块。

本次新编译 T4_MENU_01，通过新 `--file` 路径实际 RAM 上传后，仍未出现
OpeniBoot USB `0525:1280`，启动未确认：
`logs/native-file-20261018-113654.log`。不宣称达到自编完整版启动成功。
结果与校验值另存 `build/native-wrapper-evidence/RESULT.json`。
按本轮范围停止于包装/加载链，没有继续修改或调试主体、显示、菜单或 USB。
