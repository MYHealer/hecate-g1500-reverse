# HECATE G1500 BAR LED Control Protocol - FINAL

## Protocol: Two-Step (init → SetFeature)

### Critical Notes
1. **Order: init FIRST, then SetFeature** (confirmed by Frida hook of HECATE.exe)
2. HECATE.exe 不需要关闭（不影响控制）

### API
- **Library**: hidapi.dll (from `C:\Program Files\HECATE\`)
- **Step 1**: `hid_write()` — init/apply
- **Step 2**: `hid_send_feature_report()` — set color

### Protocol Format

#### Step 1: Init
```
hid_write: [ED] [10] [00]x14  (16 bytes, 1 time)
```

#### Step 2: SetFeature (set color)
```
hid_send_feature_report: [ED] [06] [10] [mode] [00] [R] [G] [B] [00]x8  (16 bytes)
```

| Byte | Value | Description |
|------|-------|-------------|
| 0 | 0xED | Report ID |
| 1 | 0x06 | Command type |
| 2 | 0x10 | Sub-command (color set) |
| 3 | 0x01 | Fixed (always 0x01) |
| 4 | mode | **LED mode (0x00-0x04)** |
| 5 | R | **Red channel (0x00-0xFF)** |
| 6 | G | **Green channel (0x00-0xFF)** |
| 7 | B | **Blue channel (0x00-0xFF)** |
| 8-15 | 0x00 | Padding |

### LED Modes
| Mode | Value | Description |
|------|-------|-------------|
| Constant | 0x00 | Static color |
| Breathe | 0x01 | Breathing effect |
| Blink Slow | 0x02 | Slow blinking |
| Blink Fast | 0x03 | Fast blinking |
| Heartbeat | 0x04 | Heartbeat effect |

### Color Encoding
**Standard RGB** in bytes 5, 6, 7 (R, G, B). Byte 4 is always 0x00.

**All 5 preset colors confirmed:**
| Name | RGB | Bytes 5-7 | Status |
|------|-----|-----------|--------|
| ice_blue | (0x00, 0xFF, 0xFF) | 00 FF FF | CONFIRMED |
| red | (0xFF, 0x00, 0x00) | FF 00 00 | CONFIRMED |
| green | (0x00, 0xFF, 0x00) | 00 FF 00 | CONFIRMED |
| blue | (0x00, 0x50, 0xFF) | 00 50 FF | CONFIRMED |
| pink | (0xFF, 0x00, 0xFF) | FF 00 FF | CONFIRMED |

### Correct Usage Pattern
```python
import ctypes, time

# 1. Open device
handle = hidapi.hid_open_path(col02_path)

# 2. Init (1 time)
init = [0xED, 0x10, 0,0,0,0,0,0,0,0,0,0,0,0,0,0]
hidapi.hid_write(handle, init, 16)

# 3. SetFeature (set color)
report = [0xED, 0x06, 0x10, mode, 0x00, R, G, B, 0,0,0,0,0,0,0,0]
hidapi.hid_send_feature_report(handle, report, 16)

# 4. Close handle
hidapi.hid_close(handle)
```

### Key Discovery Path
1. Originally got protocol order wrong (SetFeature → init×3)
2. Tried byte4 as red channel — FAILED (byte4 is reserved, always 0)
3. Tried byte6/byte7 as G/B only — worked for green/blue/ice_blue but not red
4. Frida hook on HECATE.exe: captured HidD_SetFeature with bytes `00 FF 00 00` for red
5. Discovered: byte5=R, byte6=G, byte7=B (standard RGB, not just G+B)
6. Also discovered: correct order is init → SetFeature (not reversed)

### Status
- ALL 5 preset colors: CONFIRMED controllable
- Protocol: FULLY REVERSED
- Music-reactive mode: PENDING
