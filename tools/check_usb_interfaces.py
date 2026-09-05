"""Check all USB interfaces for HECATE G1500"""
import winreg

# Find all USB interfaces for this device
base = r'SYSTEM\CurrentControlSet\Enum\USB\VID_35BB&PID_B001'
key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base)
i = 0
while True:
    try:
        sub = winreg.EnumKey(key, i)
        full = base + '\\' + sub
        sk = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, full)

        # Read key properties
        props = {}
        for name in ['Service', 'DeviceDesc', 'LocationInformation', 'CompatibleIDs', 'HardwareID']:
            try:
                val, _ = winreg.QueryValueEx(sk, name)
                props[name] = val
            except FileNotFoundError:
                pass

        print(f'\n{sub}')
        for k, v in props.items():
            if isinstance(v, list):
                print(f'  {k}: {v[0]}')
            else:
                print(f'  {k}: {v}')

        # Check for Device Parameters subkey
        try:
            dp = winreg.OpenKey(sk, 'Device Parameters')
            for name in ['RawReportDescriptor', 'LowerFilters', 'UpperFilters']:
                try:
                    val, vtype = winreg.QueryValueEx(dp, name)
                    if isinstance(val, bytes):
                        print(f'  Device Parameters\\{name}: {val.hex(" ")[:100]}')
                    elif isinstance(val, list):
                        print(f'  Device Parameters\\{name}: {val}')
                    else:
                        print(f'  Device Parameters\\{name}: {val}')
                except FileNotFoundError:
                    pass
            winreg.CloseKey(dp)
        except FileNotFoundError:
            pass

        winreg.CloseKey(sk)
        i += 1
    except OSError:
        break
winreg.CloseKey(key)
print(f'\nTotal: {i} entries')

# Also check HID entries
print('\n=== HID entries ===')
base2 = r'SYSTEM\CurrentControlSet\Enum\HID'
try:
    key2 = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base2)
    j = 0
    while True:
        try:
            sub2 = winreg.EnumKey(key2, j)
            if 'VID_35BB' in sub2.upper():
                full2 = base2 + '\\' + sub2
                sk2 = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, full2)
                k = 0
                while True:
                    try:
                        sub3 = winreg.EnumKey(sk2, k)
                        full3 = full2 + '\\' + sub3
                        sk3 = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, full3)
                        svc = '?'
                        try:
                            svc, _ = winreg.QueryValueEx(sk3, 'Service')
                        except: pass
                        desc = '?'
                        try:
                            desc, _ = winreg.QueryValueEx(sk3, 'DeviceDesc')
                        except: pass
                        print(f'  {sub3}: service={svc} desc={desc}')

                        # Check Device Parameters
                        try:
                            dp2 = winreg.OpenKey(sk3, 'Device Parameters')
                            for name in ['RawReportDescriptor']:
                                try:
                                    val, _ = winreg.QueryValueEx(dp2, name)
                                    if isinstance(val, bytes) and len(val) > 2:
                                        print(f'    {name} ({len(val)} bytes): {val.hex(" ")[:200]}')
                                except: pass
                            winreg.CloseKey(dp2)
                        except: pass

                        winreg.CloseKey(sk3)
                        k += 1
                    except OSError:
                        break
                winreg.CloseKey(sk2)
            j += 1
        except OSError:
            break
    winreg.CloseKey(key2)
except Exception as e:
    print(f'Error: {e}')
