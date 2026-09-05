"""
hecate_led_v5.py - HECATE G1500 BAR LED Controller (FINAL)
Protocol reverse-engineered from HECATE.exe via Frida hook

Protocol: Two-step (init → SetFeature)
  Step 1: hid_write (init): [ED] [10] 00x14  (16 bytes, 1x)
  Step 2: hid_send_feature_report (color): [ED] [06] [10] [mode] [00] [R] [G] [B] 00x8  (16 bytes)

Color encoding: Standard RGB in bytes 5, 6, 7 (R, G, B). Byte 4 = 0x00.
Mode values: 0=Off, 1=Constant, 2=Breathe, 3=BlinkSlow, 4=BlinkFast, 5=Heartbeat
"""
import ctypes
import time
import sys

# Load hidapi
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


# LED Modes
MODE_CONSTANT = 0
MODE_BREATHE = 1
MODE_BLINK_SLOW = 2
MODE_BLINK_FAST = 3
MODE_HEARTBEAT = 4

# Preset colors: (R, G, B)
COLORS = {
    'ice_blue':  (0x00, 0xFF, 0xFF),
    'red':       (0xFF, 0x00, 0x00),
    'green':     (0x00, 0xFF, 0x00),
    'blue':      (0x00, 0x50, 0xFF),
    'pink':      (0xFF, 0x00, 0xFF),
    'off':       (0x00, 0x00, 0x00),
}


class HecateLED:
    def __init__(self):
        self.path = find_col02()
        self.handle = None

    def open(self):
        if not self.path:
            print("ERROR: Col02 device not found!")
            return False
        self.handle = hidapi.hid_open_path(self.path)
        if not self.handle:
            print("ERROR: hid_open_path failed!")
            return False
        return True

    def init_device(self):
        """Step 1: Init (send BEFORE SetFeature)"""
        report = (ctypes.c_ubyte * 16)(0xED, 0x10, *([0]*14))
        ret = hidapi.hid_write(self.handle, report, 16)
        return ret > 0

    def get_state(self):
        """Read current feature report state"""
        buf = (ctypes.c_ubyte * 16)(0xED, *([0]*15))
        ret = hidapi.hid_get_feature_report(self.handle, buf, 16)
        return bytes(buf) if ret > 0 else None

    def set_led(self, mode=MODE_CONSTANT, r=0, g=0, b=0):
        """
        Set LED color and mode.
        Protocol: init → SetFeature
        Format: [ED][06][10][01][mode][R][G][B] + padding

        mode: 0=Constant, 1=Breathe, 2=BlinkSlow, 3=BlinkFast, 4=Heartbeat
        r, g, b: 0-255 each
        """
        # Step 1: Init
        self.init_device()
        time.sleep(0.05)
        # Step 2: SetFeature (set color)
        report = (ctypes.c_ubyte * 16)(
            0xED, 0x06, 0x10, 0x01, mode, r, g, b,
            *([0]*8)
        )
        ret = hidapi.hid_send_feature_report(self.handle, report, 16)
        return ret

    def set_color(self, name, mode=MODE_CONSTANT):
        """Set LED by color name"""
        rgb = COLORS.get(name.lower())
        if rgb is None:
            print(f"Unknown color: {name}")
            return
        return self.set_led(mode, *rgb)

    def off(self):
        """Turn LED off"""
        self.set_led(MODE_CONSTANT, 0, 0, 0)

    def close(self):
        if self.handle:
            hidapi.hid_close(self.handle)


def hex_str(data):
    return ' '.join(f'{b:02x}' for b in data) if data else 'N/A'


def main():
    print("=== HECATE G1500 BAR LED Controller v5 (FINAL) ===\n")

    led = HecateLED()
    if not led.open():
        print("ERROR: Could not open Col02 device")
        return

    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()

        if cmd == 'off':
            led.off()
            print("LED OFF")

        elif cmd == 'state':
            state = led.get_state()
            print(f"State: {hex_str(state)}")

        elif cmd in COLORS:
            r, g, b = COLORS[cmd]
            led.set_led(MODE_CONSTANT, r, g, b)
            print(f"Constant {cmd} (R={r:02X} G={g:02X} B={b:02X})")

        elif cmd == 'breathing':
            cname = sys.argv[2].lower() if len(sys.argv) > 2 else 'ice_blue'
            rgb = COLORS.get(cname, (0, 0xFF, 0xFF))
            led.set_led(MODE_BREATHE, *rgb)
            print(f"Breathing {cname}")

        elif cmd == 'blink':
            cname = sys.argv[2].lower() if len(sys.argv) > 2 else 'ice_blue'
            speed = sys.argv[3].lower() if len(sys.argv) > 3 else 'slow'
            rgb = COLORS.get(cname, (0, 0xFF, 0xFF))
            mode = MODE_BLINK_SLOW if speed == 'slow' else MODE_BLINK_FAST
            led.set_led(mode, *rgb)
            print(f"Blink {speed} {cname}")

        elif cmd == 'heartbeat':
            cname = sys.argv[2].lower() if len(sys.argv) > 2 else 'ice_blue'
            rgb = COLORS.get(cname, (0, 0xFF, 0xFF))
            led.set_led(MODE_HEARTBEAT, *rgb)
            print(f"Heartbeat {cname}")

        elif cmd == 'rgb':
            # Direct RGB: python hecate_led_v5.py rgb R G B
            if len(sys.argv) >= 5:
                r, g, b = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
                led.set_led(MODE_CONSTANT, r, g, b)
                print(f"Constant RGB({r},{g},{b})")
            else:
                print("Usage: python hecate_led_v5.py rgb R G B (0-255 each)")

        elif cmd == 'color':
            # Direct hex color: python hecate_led_v5.py color RRGGBB
            if len(sys.argv) > 2:
                hex_val = sys.argv[2].lstrip('#')
                r = int(hex_val[0:2], 16)
                g = int(hex_val[2:4], 16)
                b = int(hex_val[4:6], 16)
                led.set_led(MODE_CONSTANT, r, g, b)
                print(f"Constant #{hex_val} (R={r:02X} G={g:02X} B={b:02X})")
            else:
                print("Usage: python hecate_led_v5.py color RRGGBB")

        elif cmd == 'test':
            print("Testing all colors (3s each)...\n")
            for name, (r, g, b) in COLORS.items():
                if name == 'off':
                    continue
                led.set_led(MODE_CONSTANT, r, g, b)
                print(f"  {name} ({r:02X},{g:02X},{b:02X})", flush=True)
                time.sleep(3)
            led.off()
            print("\nTest complete.")

        elif cmd == 'modes':
            print("Testing all modes with red (5s each)...\n")
            for mode_name, mode_val in [
                ("Constant", MODE_CONSTANT),
                ("Breathe", MODE_BREATHE),
                ("BlinkSlow", MODE_BLINK_SLOW),
                ("BlinkFast", MODE_BLINK_FAST),
                ("Heartbeat", MODE_HEARTBEAT),
            ]:
                led.set_led(mode_val, 0xFF, 0x00, 0x00)
                print(f"  {mode_name} (mode={mode_val})", flush=True)
                time.sleep(5)
            led.off()
            print("\nMode test complete.")

        else:
            print(f"Unknown: {cmd}")
            print("Colors: " + ", ".join(COLORS.keys()))
            print("Modes: breathing, blink, heartbeat")
            print("Direct: rgb R G B | color RRGGBB | off | state | test | modes")

    else:
        led.set_led(MODE_CONSTANT, 0x00, 0xFF, 0xFF)
        state = led.get_state()
        print(f"Ice blue constant")
        print(f"State: {hex_str(state)}")
        print(f"\nColors: {', '.join(COLORS.keys())}")
        print("Modes: breathing [color], blink [color] [slow|fast], heartbeat [color]")
        print("Direct: rgb R G B, color RRGGBB")

    led.close()


if __name__ == "__main__":
    main()
