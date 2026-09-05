# 逆向方法论

本文档记录 HECATE G1500 BAR LED 控制协议的完整逆向过程，包括使用的工具、方法和踩过的坑。

## 工具链

| 工具 | 用途 |
|------|------|
| **hidapi.dll** | HID 设备枚举和通信 |
| **Ghidra** | 静态反汇编分析 |
| **Frida** | 动态 hook，捕获运行时 API 调用 |
| **Python + ctypes** | 脚本化 HID 通信 |

## 步骤一：HID 设备枚举

### 目的
确定 G1500 有哪些 HID 接口，找到 LED 控制用的接口。

### 方法
```python
import ctypes
hidapi = ctypes.CDLL(r'C:\Program Files\HECATE\hidapi.dll')
# 枚举 VID=0x35BB, PID=0xB001 的所有 HID 接口
devs = hidapi.hid_enumerate(0x35BB, 0xB001)
```

### 结果
G1500 是 USB Composite Device，有多个 HID 接口：
- **MI_00** — 音频控制
- **MI_03** — HID Consumer Control（Col02）← LED 用这个

关键：LED 控制通过 **Col02** 接口的 **Feature Report** 实现。

## 步骤二：Ghidra 静态分析

### 目的
理解 HECATE.exe 和 HIDUSB.DLL 的内部结构，找到 HID 通信函数。

### 方法
1. 用 Ghidra 的 `analyzeHeadless` 导入 HECATE.exe 和 HIDUSB.DLL
2. 导出函数列表、导入表、字符串表
3. 搜索 `hid_send_feature_report`、`WriteFile`、`HidD_SetFeature` 的交叉引用

### 关键发现

**HIDUSB.DLL 内部函数**（非导出）：
- `UsbMusicLed_SetColorModeData` (0x180007780) — 0xB0 协议
- `UsbMusicLed_SetRCModeData` (0x1800075c0) — 0xB6 协议
- `UsbMusicLed_GetMusicLedColor` (0x180007190) — 获取颜色

**HECATE.exe 导入**：
- 从 HIDUSB.DLL 导入17个函数，全是 UsbMouseC_*/UsbFinderC_*/UsbListenerC_*
- **没有** UsbMusicLed_* 导入
- **没有** hidapi、CreateFile、WriteFile 导入

**误导**：最初以为 HECATE 用 HIDUSB.DLL 的 0xB0 协议控制 LED，实际上不是。

## 步骤三：初始协议尝试（走了弯路）

### 假设
从 HID 描述符分析得出：颜色编码为 `Color = (Green << 8) | Blue`，存储在 bytes 6-7。

### 测试结果
| 颜色 | 编码 | 结果 |
|------|------|------|
| green | 0xFF00 | ✓ |
| blue | 0x50FF | ✓ |
| ice_blue | 0xFFFF | ✓ |
| red | 0x0000 | ✗ LED 不变 |
| pink | 0x00FF | ✗ LED 不变 |

### 分析
byte6=0x00 时固件跳过命令。red 和 pink 的 Green 分量为 0，所以 byte6=0x00，命令被忽略。

### 错误的协议顺序
最初文档记录为"先 SetFeature 后 init"，后来发现这是错的。正确顺序是 init → SetFeature。

## 步骤四：Frida 动态 hook（关键突破）

### 目的
捕获 HECATE.exe 设置 LED 颜色时实际发送的字节。

### Frida 17.x API 变化

Frida 17.x 移除了 `Module.findExportByName`，必须用：

```javascript
function findExport(modName, funcName) {
    var mod = Process.findModuleByName(modName);
    if (!mod) return null;
    var exports = mod.enumerateExports();
    for (var i = 0; i < exports.length; i++) {
        if (exports[i].name === funcName) return exports[i].address;
    }
    return null;
}
```

### Hook 策略

Hook 了 4 层 API，确保不遗漏：

1. **HidD_SetFeature** (hid.dll) — Windows 原生 HID API
2. **HidD_SetOutputReport** (hid.dll) — 另一个 HID API
3. **WriteFile** (kernel32.dll) — 底层文件写入
4. **hid_send_feature_report / hid_write** (hidapi.dll) — hidapi 封装

### 关键：attach 模式

```python
# 错误：spawn 模式不出 HID 流量
device.spawn(['HECATE.exe'])  # ✗

# 正确：attach 到已运行的进程
session = device.attach(hecate_pid)  # ✓
```

### 抓包结果

当用户在 HECATE app 中切换到红色时：

```
[HidD_SetFeature] ED 06 10 01 00 FF 00 00 00 00 00 00 00 00 00 00
[WriteFile]       ED 10 00 00 00 00 00 00 00 00 00 00 00 00 00 00
```

**解读**：
- SetFeature: `ED 06 10 01 00 FF 00 00` — byte5=0xFF = **红色通道！**
- WriteFile: `ED 10 00...` — init/apply 命令
- 顺序：先 init 后 SetFeature

### 之前的错误

1. 以为 byte5 是保留字段（0x00）→ 实际是 Red 通道
2. 以为颜色只有 G+B 两个通道 → 实际是 R+G+B 三个通道
3. 以为顺序是 SetFeature → init → 实际是 init → SetFeature

## 步骤五：协议确认

用完全相同的字节和顺序发送，红色成功！

```python
# Step 1: Init
init = [0xED, 0x10, 0,0,0,0,0,0,0,0,0,0,0,0,0,0]
hidapi.hid_write(handle, init, 16)

# Step 2: SetFeature (red)
report = [0xED, 0x06, 0x10, 0x01, 0x00, 0xFF, 0x00, 0x00, 0,0,0,0,0,0,0,0]
hidapi.hid_send_feature_report(handle, report, 16)
```

完整颜色编码确认：
- byte5 = R (Red)
- byte6 = G (Green)
- byte7 = B (Blue)
- 标准 RGB，任意颜色可调

## 经验总结

### 什么有效
1. **Frida attach 模式** — 捕获运行时 API 调用的最可靠方法
2. **多层 hook** — 同时 hook HidD_SetFeature + WriteFile + hidapi，确保不遗漏
3. **对比验证** — 用 HECATE 完全相同的字节和顺序发送，确认协议正确

### 什么无效
1. **Ghidra 单独分析** — 5000 函数的摘要不包含关键的颜色转换逻辑
2. **暴力测试字节** — 没有正确的假设，穷举效率极低
3. **0xB0 协议** — HIDUSB.DLL 内部的协议，HECATE 实际不用于 LED 控制
4. **GetFeature 回读** — 回读的状态不准确，不能用于推断颜色编码

### 关键教训
- **不要假设** — byte5 看起来像保留字段，实际上是 Red 通道
- **抓包优先** — 静态分析只能提供线索，动态抓包才能确认
- **注意 Frida 版本** — 17.x API 有 breaking changes
