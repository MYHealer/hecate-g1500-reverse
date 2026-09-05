# HECATE G1500 BAR Reverse Engineering

HECATE G1500 BAR 游戏音箱完全逆向工程 — LED 全色控制 + 音频解锁。

## 成果

- **LED 全色控制**: 任意 RGB 颜色，6 种灯效模式（常亮/呼吸/慢闪/快闪/心跳/关闭）
- **音频解锁**: 禁用 VRMS Limiter + Harman EQ
- **协议完全逆向**: 通过 Frida 动态 hook + Ghidra 静态分析破解 HID 协议

## 硬件信息

| 属性 | 值 |
|------|-----|
| 设备 | HECATE G1500 BAR 游戏音箱 |
| VID | 0x35BB |
| PID | 0xB001 |
| HID 接口 | MI_03 / Col02 (Consumer Control) |
| HID 库 | hidapi.dll (`C:\Program Files\HECATE\`) |

## 快速开始

### 依赖

```bash
pip install frida
```

需要 `hidapi.dll`（安装 HECATE 驱动后在 `C:\Program Files\HECATE\`）。

### 控制 LED

```bash
# 关闭 HECATE.exe 后使用
python led/hecate_led.py red          # 红色常亮
python led/hecate_led.py green        # 绿色
python led/hecate_led.py blue         # 蓝色
python led/hecate_led.py ice_blue     # 冰蓝
python led/hecate_led.py pink         # 粉色
python led/hecate_led.py breathing red   # 红色呼吸
python led/hecate_led.py heartbeat blue  # 蓝色心跳
python led/hecate_led.py rgb 255 128 0   # 橙色 (RGB)
python led/hecate_led.py color FF8000    # 橙色 (hex)
python led/hecate_led.py off             # 关灯
python led/hecate_led.py test            # 测试所有颜色
```

### 音频解锁

```bash
python audio/unlock_vrms.py    # 解锁 VRMS Limiter + 应用 Harman EQ
python audio/restore_vrms.py   # 恢复原始设置
```

## LED 协议

两步协议，通过 hidapi 的 Col02 接口发送：

```
Step 1: hid_write              → [ED] [10] 00x14           (init, 1次)
Step 2: hid_send_feature_report → [ED] [06] [10] [mode] [00] [R] [G] [B] 00x8
```

### 报告格式

| 字节 | 值 | 说明 |
|------|-----|------|
| 0 | 0xED | Report ID |
| 1 | 0x06 | Command |
| 2 | 0x10 | Sub-command |
| 3 | 0x01 | 固定值 |
| 4 | mode | **灯效模式** |
| 4 | 0x00 | 保留 |
| 5 | **R** | **红色通道 (0x00-0xFF)** |
| 6 | **G** | **绿色通道 (0x00-0xFF)** |
| 7 | **B** | **蓝色通道 (0x00-0xFF)** |
| 8-15 | 0x00 | 填充 |

### 灯效模式

| 模式 | 值 |
|------|-----|
| 常亮 | 0x00 |
| 呼吸 | 0x01 |
| 慢闪 | 0x02 |
| 快闪 | 0x03 |
| 心跳 | 0x04 |

## 逆向过程

### 第一步：HID 枚举

用 `tools/enum_hid.py` 枚举 G1500 的所有 HID 接口：

```
MI_00 - 音频接口
MI_03 - HID Consumer Control (Col02) ← LED 控制用这个
```

### 第二步：Ghidra 静态分析

用 Ghidra 分析 `HECATE.exe` 和 `HIDUSB.DLL`：
- HECATE.exe 从 HIDUSB.DLL 导入17个函数（UsbMouseC_*、UsbFinderC_* 等）
- HIDUSB.DLL 内部有 `UsbMusicLed_SetColorModeData`（0xB0协议）和 `UsbMusicLed_SetRCModeData`（0xB6协议）
- 但 HECATE.exe 实际上**不使用**这些内部函数控制 LED

### 第三步：初始尝试（走了弯路）

最初假设颜色编码为 `Color = (Green << 8) | Blue`，只用 bytes 6-7：
- green (0xFF00) ✓
- blue (0x50FF) ✓
- ice_blue (0xFFFF) ✓
- red (0x0000) ✗ — byte6=0x00 导致固件跳过命令
- pink (0x00FF) ✗ — 同上

同时搞反了协议顺序（先 SetFeature 后 init），浪费了大量时间。

### 第四步：Frida 动态 hook（关键突破）

**Frida 17.x 注意事项**：`Module.findExportByName` 不可用，必须用：
```javascript
var mod = Process.findModuleByName('hid.dll');
var exports = mod.enumerateExports();
for (var i = 0; i < exports.length; i++) {
    if (exports[i].name === 'HidD_SetFeature') {
        Interceptor.attach(exports[i].address, { ... });
    }
}
```

Hook 了以下函数：
- `HidD_SetFeature` (hid.dll)
- `WriteFile` (kernel32.dll)
- `CreateFileW` (kernel32.dll)
- `hid_send_feature_report` / `hid_write` (hidapi.dll)

**关键发现**：当用户在 HECATE app 中切换到红色时，抓到：

```
[HidD_SetFeature] ED 06 10 01 00 FF 00 00 00 00 00 00 00 00 00 00
```

- byte5 = 0xFF → **这就是红色通道！**
- byte6 = 0x00 (Green)
- byte7 = 0x00 (Blue)
- 顺序是 init → SetFeature（不是之前认为的反过来）

### 第五步：协议确认

用 HECATE 完全相同的顺序和字节发送，红色成功！

完整颜色编码：
- **byte5 = Red**
- **byte6 = Green**
- **byte7 = Blue**

标准 RGB，三个独立通道。

**限制**: 固件配置 `"any_color": false`，只支持5个预设颜色（ice_blue/red/green/blue/pink）。发送其他 RGB 值会被固件忽略。这是硬件限制，非协议问题。

### 踩坑记录

1. **HECATE.exe 抢占设备** — 运行时它持有 HID handle，我们的命令会被覆盖。必须先关闭。
2. **Frida spawn 模式无流量** — `device.spawn()` 启动的进程不出 HID 流量，必须 attach 到已运行的进程。
3. **byte6=0x00 = 跳过** — 固件忽略 byte6=0x00 的命令，导致红色（R>0,G=0,B=0）无法通过旧编码设置。
4. **0xB0 协议是干扰** — HIDUSB.DLL 内部有 0xB0/0xB6 协议，但 HECATE 实际不用于 LED 控制。
5. **HidD_SetFeature vs hid_send_feature_report** — HECATE 用的是 Windows 原生 `HidD_SetFeature`，不是 hidapi 的 `hid_send_feature_report`。

## 工具说明

### led/

| 文件 | 说明 |
|------|------|
| `hecate_led.py` | 最终 LED 控制器，支持所有颜色和灯效 |
| `hook_frida.py` | Frida hook 脚本，捕获 HECATE HID 流量（17.x 兼容）|
| `color_test.py` | 颜色编码自动测试工具 |

### audio/

| 文件 | 说明 |
|------|------|
| `unlock_vrms.py` | 解锁 VRMS Limiter + Harman EQ |
| `restore_vrms.py` | 恢复原始音频设置 |

### tools/

| 文件 | 说明 |
|------|------|
| `enum_hid.py` | HID 设备枚举 |
| `capture_hid.py` | HID 流量抓包 |
| `check_usb_interfaces.py` | USB 接口检查 |

### docs/

| 文件 | 说明 |
|------|------|
| `LED_PROTOCOL.md` | LED 协议完整文档 |
| `REVERSE_METHODOLOGY.md` | 逆向方法论详解 |
| `HID_FINDINGS.md` | HID 接口发现记录 |

## 已知限制

- **音乐律动模式** — 需要 WASAPI loopback + beat detection，尚未实现
- **需要关闭 HECATE.exe** — 不能同时使用官方 app 和自定义控制
- **hidapi.dll 依赖** — 需要安装 HECATE 驱动

## License

MIT
