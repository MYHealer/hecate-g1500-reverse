"""
unlock_vrms.py - HECATE G1500 BAR VRMS Limiter Unlock
Writes directly to IPropertyStore (COM).
Run as Administrator.
"""
from comtypes import GUID
from comtypes.client import CreateObject
from pycaw.api.mmdeviceapi import IMMDeviceEnumerator
from pycaw.api.mmdeviceapi.depend import IPropertyStore
from pycaw.api.mmdeviceapi.depend.structures import PROPERTYKEY, PROPVARIANT
from pycaw.constants import STGM
from comtypes.automation import VT_UI4
import ctypes, sys

VRMS_GUID = GUID("{9287D038-9DDE-4472-9509-D1EE9371C1D6}")

def main():
    if not ctypes.windll.shell32.IsUserAnAdmin():
        print("ERROR: Right-click -> Run as administrator!")
        sys.exit(1)

    print("=== HECATE G1500 BAR VRMS Limiter Unlock ===\n")

    CLSID = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
    enum = CreateObject(CLSID, interface=IMMDeviceEnumerator, clsctx=1)

    # Find active HECATE device
    coll = enum.EnumAudioEndpoints(0, 1)  # eRender, Active
    count = coll.GetCount()
    hecate = None
    for i in range(count):
        d = coll.Item(i)
        did = d.GetId()
        if 'edbcfb54' in did or '20cd8f61' in did or '468bf86e' in did or '978ad9d7' in did:
            hecate = d
            print(f"Found: {did[:60]}")
            break
        name = ""
        try:
            ps = d.OpenPropertyStore(STGM.STGM_READ.value)
            pk = PROPERTYKEY()
            pk.fmtid = GUID("{A45C254E-DF1C-4EFD-8020-67D146A850E0}")
            pk.pid = 14
            pv = ps.GetValue(pk)
            name = str(pv.GetValue() or "")
            pv.clear()
        except:
            pass
        if "HECATE" in name.upper():
            hecate = d
            print(f"Found: {name} | {did[:40]}")
            break

    if not hecate:
        print("HECATE not found! Is it plugged in?")
        sys.exit(1)

    # Open property store RW
    try:
        props = hecate.OpenPropertyStore(2)  # STGM_READWRITE
        print("Property store: RW\n")
    except Exception as e:
        print(f"RW failed: {e}\nTrying RO...")
        props = hecate.OpenPropertyStore(STGM.STGM_READ.value)
        print("Property store: RO (cannot write!)\n")
        # Read-only mode
        labels = ["Enable", "Level", "Attack", "Release", "PreGain"]
        for pid in range(5):
            pk = PROPERTYKEY()
            pk.fmtid = VRMS_GUID
            pk.pid = pid
            try:
                pv = props.GetValue(pk)
                val = pv.GetValue()
                vt = pv.vt
                pv.clear()
                print(f"  {labels[pid]}: {val if vt else '(empty)'}")
            except:
                print(f"  {labels[pid]}: err")
        print("\nNeed admin for write access!")
        sys.exit(1)

    labels = ["Enable", "Level", "Attack", "Release", "PreGain"]

    # Read current
    print("--- Current ---")
    for pid in range(5):
        pk = PROPERTYKEY()
        pk.fmtid = VRMS_GUID
        pk.pid = pid
        try:
            pv = props.GetValue(pk)
            val = pv.GetValue()
            vt = pv.vt
            pv.clear()
            print(f"  {labels[pid]}: {val if vt else '(empty)'}")
        except:
            print(f"  {labels[pid]}: err")

    # Write
    print("\n--- Unlocking ---")
    for pid, val in [(0, 0), (1, 100), (2, 100), (3, 4000), (4, 100)]:
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
    print(f"\nCommit: {'SUCCESS!' if hr == 0 else f'FAIL 0x{hr & 0xFFFFFFFF:08X}'}")

    # Verify
    print("\n--- Verify ---")
    for pid in range(5):
        pk = PROPERTYKEY()
        pk.fmtid = VRMS_GUID
        pk.pid = pid
        try:
            pv = props.GetValue(pk)
            val = pv.GetValue()
            vt = pv.vt
            pv.clear()
            print(f"  {labels[pid]}: {val if vt else '(empty)'}")
        except:
            print(f"  {labels[pid]}: err")

    print("\nDone! VRMS Limiter disabled.")

if __name__ == "__main__":
    main()
