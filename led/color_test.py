"""
hecate_color_test2.py - Auto-advance color test with delays
Test byte4 as Red channel hypothesis.
"""
import ctypes
import time
import sys

hidapi = ctypes.CDLL(r'C:\Program Files\HECATE\hidapi.dll')

class hid_device_info(ctypes.Structure): pass
hid_device_info._fields_ = [
    ('path', ctypes.c_char_p), ('vendor_id', ctypes.c_ushort),
    ('product_id', ctypes.c_ushort), ('serial_number', ctypes.c_wchar_p),
    ('release_number', ctypes.c_ushort), ('manufacturer_string', ctypes.c_wchar_p),
    ('product_string', ctypes.c_wchar_p), ('usage_page', ctypes.c_ushort),
    ('usage', ctypes.c_ushort), ('interface_number', ctypes.c_int),
    ('next', ctypes.POINTER(hid_device_info)),
]

hidapi.hid_enumerate.argtypes = [ctypes.c_ushort, ctypes.c_ushort]
hidapi.hid_enumerate.restype = ctypes.POINTER(hid_device_info)
hidapi.hid_open_path.argtypes = [ctypes.c_char_p]
hidapi.hid_open_path.restype = ctypes.c_void_p
hidapi.hid_write.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int]
hidapi.hid_write.restype = ctypes.c_int
hidapi.hid_send_feature_report.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int]
hidapi.hid_send_feature_report.restype = ctypes.c_int
hidapi.hid_get_feature_report.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int]
hidapi.hid_get_feature_report.restype = ctypes.c_int
hidapi.hid_close.argtypes = [ctypes.c_void_p]


def find_col02():
    devs = hidapi.hid_enumerate(0x35BB, 0xB001)
    d = devs
    result = None
    while d and d[0].path:
        if b'Col02' in d[0].path:
            result = d[0].path
            break
        d = d[0].next
    hidapi.hid_free_enumeration(devs)
    return result


def full_init(handle):
    for _ in range(3):
        report = (ctypes.c_ubyte * 16)(0xED, 0x10, *([0]*14))
        hidapi.hid_write(handle, report, 16)
        time.sleep(0.1)


def set_color(handle, byte4, byte5, color_hi, color_lo, mode=0x01):
    report = (ctypes.c_ubyte * 16)(
        0xED, 0x06, 0x10, mode,
        byte4, byte5, color_hi, color_lo,
        *([0]*8)
    )
    return hidapi.hid_send_feature_report(handle, report, 16)


def main():
    path = find_col02()
    if not path:
        print("ERROR: Col02 not found!")
        return

    handle = hidapi.hid_open_path(path)
    if not handle:
        print("ERROR: Could not open Col02!")
        return

    DELAY = 8  # seconds between tests

    # Single test from command line, or run all
    if len(sys.argv) >= 2:
        cmd = sys.argv[1].lower()

        if cmd == 'red':
            print("Testing RED: byte4=FF, G=00, B=00")
            full_init(handle)
            set_color(handle, 0xFF, 0x00, 0x00, 0x00)
            print("Sent. Watch LED for color.")

        elif cmd == 'green':
            print("Testing GREEN: byte4=00, G=FF, B=00")
            full_init(handle)
            set_color(handle, 0x00, 0x00, 0xFF, 0x00)

        elif cmd == 'blue':
            print("Testing BLUE: byte4=00, G=00, B=FF")
            full_init(handle)
            set_color(handle, 0x00, 0x00, 0x00, 0xFF)

        elif cmd == 'ice':
            print("Testing ice_blue: byte4=00, G=FF, B=FF")
            full_init(handle)
            set_color(handle, 0x00, 0x00, 0xFF, 0xFF)

        elif cmd == 'white':
            print("Testing WHITE: R=FF, G=FF, B=FF")
            full_init(handle)
            set_color(handle, 0xFF, 0x00, 0xFF, 0xFF)

        elif cmd == 'pink':
            print("Testing PINK: R=FF, G=00, B=FF")
            full_init(handle)
            set_color(handle, 0xFF, 0x00, 0x00, 0xFF)

        elif cmd == 'yellow':
            print("Testing YELLOW: R=FF, G=FF, B=00")
            full_init(handle)
            set_color(handle, 0xFF, 0x00, 0xFF, 0x00)

        elif cmd == 'test2':
            # Test: what if bytes 4-5 together form a 16-bit red channel?
            # Like (byte4 << 8) | byte5 = red value
            # For red=0xFF0000: byte4=0xFF, byte5=0x00
            # For ice_blue=0x00FFFF: byte4=0x00, byte5=0x00
            print("Testing bytes 4-5 as 16-bit value...")
            tests = [
                ("b4=FF,b5=00 (0xFF00)", 0xFF, 0x00, 0x00, 0x00),
                ("b4=00,b5=FF (0x00FF)", 0x00, 0xFF, 0x00, 0x00),
                ("b4=FF,b5=FF (0xFFFF)", 0xFF, 0xFF, 0x00, 0x00),
                ("b4=80,b5=00 (0x8000)", 0x80, 0x00, 0x00, 0x00),
            ]
            for name, b4, b5, b6, b7 in tests:
                print(f"\n  {name}")
                full_init(handle)
                set_color(handle, b4, b5, b6, b7)
                print(f"  Sent. Waiting {DELAY}s...")
                time.sleep(DELAY)

            # Reset
            full_init(handle)
            set_color(handle, 0x00, 0x00, 0xFF, 0xFF)
            print("\nDone. Restored ice_blue.")

        elif cmd == 'test3':
            # Test: what if ALL of bytes 4-7 form a 32-bit RGBA?
            # Or bytes 4-7 = R1 R2 G B?
            print("Testing 4-byte color (bytes 4-7)...")
            tests = [
                ("Only b4=FF",    0xFF, 0x00, 0x00, 0x00),
                ("Only b5=FF",    0x00, 0xFF, 0x00, 0x00),
                ("Only b6=FF",    0x00, 0x00, 0xFF, 0x00),
                ("Only b7=FF",    0x00, 0x00, 0x00, 0xFF),
                ("b4+b5=FF",      0xFF, 0xFF, 0x00, 0x00),
                ("b4+b6=FF",      0xFF, 0x00, 0xFF, 0x00),
                ("b4+b7=FF",      0xFF, 0x00, 0x00, 0xFF),
                ("b5+b6=FF",      0x00, 0xFF, 0xFF, 0x00),
                ("b5+b7=FF",      0x00, 0xFF, 0x00, 0xFF),
                ("b6+b7=FF",      0x00, 0x00, 0xFF, 0xFF),
            ]
            for name, b4, b5, b6, b7 in tests:
                print(f"\n  {name}")
                full_init(handle)
                set_color(handle, b4, b5, b6, b7)
                print(f"  Sent. Waiting {DELAY}s...")
                time.sleep(DELAY)

            full_init(handle)
            set_color(handle, 0x00, 0x00, 0xFF, 0xFF)
            print("\nDone. Restored ice_blue.")

        elif cmd == 'noinit':
            # Test without full_init - just raw set_color
            # This tests if the issue is init overwriting the color
            print("Testing WITHOUT re-init between colors...")
            full_init(handle)

            print("\n  Setting RED (b4=FF)")
            set_color(handle, 0xFF, 0x00, 0x00, 0x00)
            time.sleep(DELAY)

            print("  Setting GREEN (b6=FF)")
            set_color(handle, 0x00, 0x00, 0xFF, 0x00)
            time.sleep(DELAY)

            print("  Setting BLUE (b7=FF)")
            set_color(handle, 0x00, 0x00, 0x00, 0xFF)
            time.sleep(DELAY)

            full_init(handle)
            set_color(handle, 0x00, 0x00, 0xFF, 0xFF)
            print("\nDone.")

        else:
            print(f"Unknown: {cmd}")
            print("Commands: red, green, blue, ice, white, pink, yellow, test2, test3, noinit")

    else:
        print("Usage: python hecate_color_test2.py <command>")
        print("  red/green/blue/ice/white/pink/yellow - single color test")
        print("  test2 - bytes 4-5 as 16-bit value")
        print("  test3 - single byte at a time in bytes 4-7")
        print("  noinit - test without re-init between colors")

    hidapi.hid_close(handle)


if __name__ == "__main__":
    main()
