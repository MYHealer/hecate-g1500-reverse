# HID 接口发现记录

## 设备信息

- **VID**: 0x35BB
- **PID**: 0xB001
- **设备类型**: USB Composite Device

## HID 接口枚举

通过 `hid_enumerate(0x35BB, 0xB001)` 枚举到的接口：

| 接口 | 路径标识 | Usage Page | Usage | 用途 |
|------|----------|------------|-------|------|
| MI_00 | Col00 | - | - | 音频控制 |
| MI_03 | Col02 | 0x0C (Consumer) | 0x01 (Consumer Control) | **LED 控制** |

## Col02 接口详情

- **Report ID**: 0xED
- **Feature Report 大小**: 16 bytes
- **Output Report 大小**: 16 bytes
- **HID 描述符**: 标准 Consumer Control，支持 Feature Report 和 Output Report

## Feature Report 格式 (0xED)

```
[ED] [06] [10] [mode] [00] [R] [G] [B] [00]x8
```

- Byte 0: Report ID (0xED)
- Byte 1: Command (0x06 = LED color set)
- Byte 2: Sub-command (0x10)
- Byte 3: Mode (0x00-0x05)
- Byte 4: Reserved (0x00)
- Byte 5: Red channel (0x00-0xFF)
- Byte 6: Green channel (0x00-0xFF)
- Byte 7: Blue channel (0x00-0xFF)
- Byte 8-15: Padding (0x00)

## Output Report 格式 (0xED)

```
[ED] [10] [00]x14
```

- Byte 0: Report ID (0xED)
- Byte 1: Command (0x10 = init/apply)
- Byte 2-15: Zeros

## HIDUSB.DLL 内部协议（未使用）

HIDUSB.DLL 内部还有两个 LED 协议，但 HECATE.exe 实际不使用：

### 0xB0 协议 (UsbMusicLed_SetColorModeData)
```
[08] [B0] [mode] [submode] [color 8 bytes] [checksum]  (17 bytes, via WriteFile)
```

### 0xB6 协议 (UsbMusicLed_SetRCModeData)
```
[08] [B6] [14 data bytes] [checksum]  (17 bytes, via WriteFile)
```

## 通信流程

```
HECATE App
  ↓ (Qt signal)
HECATE.exe
  ↓ (HidD_SetFeature)
hid.dll (Windows HID API)
  ↓ (IRP)
HidUsb.sys (HID miniport driver)
  ↓ (USB)
G1500 Hardware
```

HECATE.exe 使用 Windows 原生 `HidD_SetFeature` API，不通过 hidapi.dll。
