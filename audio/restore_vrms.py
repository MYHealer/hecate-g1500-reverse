"""
restore_vrms.py - Restore HECATE G1500 BAR to factory defaults
Run as Administrator.
"""
from comtypes import GUID
from comtypes.client import CreateObject
from pycaw.api.mmdeviceapi import IMMDeviceEnumerator
from pycaw.api.mmdeviceapi.depend.structures import PROPERTYKEY, PROPVARIANT
from pycaw.constants import STGM
from comtypes.automation import VT_UI4
import ctypes, sys, winreg, subprocess

VRMS_GUID = GUID("{9287D038-9DDE-4472-9509-D1EE9371C1D6}")

def main():
    if not ctypes.windll.shell32.IsUserAnAdmin():
        print("ERROR: Right-click -> Run as administrator!")
        sys.exit(1)

    print("=== HECATE G1500 BAR - Restore Factory Defaults ===\n")

    CLSID = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
    enum = CreateObject(CLSID, interface=IMMDeviceEnumerator, clsctx=1)

    # Find HECATE device
    coll = enum.EnumAudioEndpoints(0, 1)
    count = coll.GetCount()
    hecate = None
    for i in range(count):
        d = coll.Item(i)
        did = d.GetId()
        if 'edbcfb54' in did or '20cd8f61' in did or '468bf86e' in did:
            hecate = d
            break
        try:
            ps = d.OpenPropertyStore(STGM.STGM_READ.value)
            pk = PROPERTYKEY()
            pk.fmtid = GUID("{A45C254E-DF1C-4EFD-8020-67D146A850E0}")
            pk.pid = 14
            pv = ps.GetValue(pk)
            name = str(pv.GetValue() or "")
            pv.clear()
            if "HECATE" in name.upper():
                hecate = d
                break
        except:
            pass

    if not hecate:
        print("HECATE device not found!")
        sys.exit(1)

    did = hecate.GetId()
    print(f"Device: {did[:60]}")

    # Open RW
    try:
        props = hecate.OpenPropertyStore(2)
    except:
        print("Cannot open PropertyStore RW!")
        sys.exit(1)

    labels = ["Enable", "Level", "Attack", "Release", "PreGain"]

    # Factory defaults from original INF
    defaults = {0: 1, 1: 70, 2: 100, 3: 4000, 4: 0}

    print("\n--- Restoring VRMS Limiter to factory defaults ---")
    for pid, val in defaults.items():
        pk = PROPERTYKEY()
        pk.fmtid = VRMS_GUID
        pk.pid = pid
        pv = PROPVARIANT()
        pv.vt = VT_UI4
        pv.union.lVal = val
        hr = props.SetValue(pk, pv)
        status = "OK" if hr == 0 else f"FAIL 0x{hr & 0xFFFFFFFF:08X}"
        print(f"  {labels[pid]} = {val}: {status}")

    hr = props.Commit()
    print(f"\nCommit: {'SUCCESS' if hr == 0 else f'FAIL 0x{hr & 0xFFFFFFFF:08X}'}")

    # Verify
    print("\n--- Verify ---")
    for pid in range(5):
        pk = PROPERTYKEY()
        pk.fmtid = VRMS_GUID
        pk.pid = pid
        pv = props.GetValue(pk)
        val = pv.GetValue()
        pv.clear()
        print(f"  {labels[pid]} = {val}")

    # Clean up manually created registry FX keys
    print("\n--- Cleaning registry ---")
    fx_path = r'SYSTEM\CurrentControlSet\Control\Class\{4d36e96c-e325-11ce-bfc1-08002be10318}\0009\FX'
    try:
        r = subprocess.run(['reg', 'delete', r'HKLM\\' + fx_path, '/f'],
                          capture_output=True, text=True, timeout=10)
        print(f"  Registry FX key: deleted")
    except Exception as e:
        print(f"  Registry FX key: {e}")

    # Restore testsigning
    print("\n--- Restoring testsigning ---")
    r = subprocess.run(['bcdedit', '/set', 'testsigning', 'off'],
                      capture_output=True, text=True, timeout=10)
    print(f"  testsigning off: {'OK' if r.returncode == 0 else r.stderr.strip()}")

    print("\n=== Factory defaults restored ===")

if __name__ == "__main__":
    main()
