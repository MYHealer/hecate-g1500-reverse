"""
hook_hecate_hidusb.py - Frida hook for HECATE.exe
Hook HIDUSB.DLL's internal functions: HidD_SetFeature, WriteFile, CreateFileW
Goal: capture the exact bytes and device path when HECATE sets red.
"""
import frida
import sys
import time
import json

HOOK_SCRIPT = r"""
'use strict';

// Hook HidD_SetFeature in HID.DLL (called by HIDUSB.DLL)
var HidD_SetFeature = Module.findExportByName('hid.dll', 'HidD_SetFeature');
if (HidD_SetFeature) {
    Interceptor.attach(HidD_SetFeature, {
        onEnter: function(args) {
            this.handle = args[0];
            var buf = args[1];
            var len = args[2].toInt32();
            var data = [];
            for (var i = 0; i < Math.min(len, 64); i++) {
                data.push(buf.add(i).readU8());
            }
            send({
                type: 'HidD_SetFeature',
                handle: this.handle.toString(),
                length: len,
                data: data,
                hex: data.map(function(b) { return ('0' + b.toString(16)).slice(-2); }).join(' ')
            });
        }
    });
    send({type: 'info', msg: 'Hooked HidD_SetFeature at ' + HidD_SetFeature});
} else {
    send({type: 'info', msg: 'HidD_SetFeature not found'});
}

// Hook HidD_SetOutputReport in HID.DLL
var HidD_SetOutputReport = Module.findExportByName('hid.dll', 'HidD_SetOutputReport');
if (HidD_SetOutputReport) {
    Interceptor.attach(HidD_SetOutputReport, {
        onEnter: function(args) {
            var buf = args[1];
            var len = args[2].toInt32();
            var data = [];
            for (var i = 0; i < Math.min(len, 64); i++) {
                data.push(buf.add(i).readU8());
            }
            send({
                type: 'HidD_SetOutputReport',
                length: len,
                data: data,
                hex: data.map(function(b) { return ('0' + b.toString(16)).slice(-2); }).join(' ')
            });
        }
    });
    send({type: 'info', msg: 'Hooked HidD_SetOutputReport at ' + HidD_SetOutputReport});
}

// Hook WriteFile in kernel32.dll
var WriteFile = Module.findExportByName('kernel32.dll', 'WriteFile');
if (WriteFile) {
    Interceptor.attach(WriteFile, {
        onEnter: function(args) {
            this.handle = args[0];
            this.buf = args[1];
            this.len = args[2].toInt32();
        },
        onLeave: function(retval) {
            if (this.len > 0 && this.len <= 64) {
                var data = [];
                for (var i = 0; i < this.len; i++) {
                    data.push(this.buf.add(i).readU8());
                }
                // Only report if it looks like an HID report (starts with 0x08 or 0xED)
                if (data[0] === 0x08 || data[0] === 0xED) {
                    send({
                        type: 'WriteFile',
                        handle: this.handle.toString(),
                        length: this.len,
                        data: data,
                        hex: data.map(function(b) { return ('0' + b.toString(16)).slice(-2); }).join(' '),
                        success: retval.toInt32() !== 0
                    });
                }
            }
        }
    });
    send({type: 'info', msg: 'Hooked WriteFile at ' + WriteFile});
}

// Hook CreateFileW to capture device paths
var CreateFileW = Module.findExportByName('kernel32.dll', 'CreateFileW');
if (CreateFileW) {
    Interceptor.attach(CreateFileW, {
        onEnter: function(args) {
            this.path = args[0].readUtf16String();
        },
        onLeave: function(retval) {
            var handle = retval.toInt32();
            if (handle !== -1 && this.path && this.path.indexOf('vid_35bb') !== -1) {
                send({
                    type: 'CreateFileW',
                    path: this.path,
                    handle: '0x' + handle.toString(16)
                });
            }
        }
    });
    send({type: 'info', msg: 'Hooked CreateFileW at ' + CreateFileW});
}

// Also hook hid_send_feature_report from hidapi.dll (just in case)
var hidapi = Process.findModuleByName('hidapi.dll');
if (hidapi) {
    var exports = hidapi.enumerateExports();
    for (var i = 0; i < exports.length; i++) {
        if (exports[i].name === 'hid_send_feature_report') {
            Interceptor.attach(exports[i].address, {
                onEnter: function(args) {
                    var buf = args[1];
                    var len = args[2].toInt32();
                    var data = [];
                    for (var j = 0; j < Math.min(len, 64); j++) {
                        data.push(buf.add(j).readU8());
                    }
                    send({
                        type: 'hid_send_feature_report',
                        length: len,
                        data: data,
                        hex: data.map(function(b) { return ('0' + b.toString(16)).slice(-2); }).join(' ')
                    });
                }
            });
            send({type: 'info', msg: 'Hooked hid_send_feature_report at ' + exports[i].address});
            break;
        }
    }
} else {
    send({type: 'info', msg: 'hidapi.dll not loaded'});
}

// Hook hid_write from hidapi.dll
if (hidapi) {
    var exports2 = hidapi.enumerateExports();
    for (var i = 0; i < exports2.length; i++) {
        if (exports2[i].name === 'hid_write') {
            Interceptor.attach(exports2[i].address, {
                onEnter: function(args) {
                    var buf = args[1];
                    var len = args[2].toInt32();
                    var data = [];
                    for (var j = 0; j < Math.min(len, 64); j++) {
                        data.push(buf.add(j).readU8());
                    }
                    send({
                        type: 'hid_write',
                        length: len,
                        data: data,
                        hex: data.map(function(b) { return ('0' + b.toString(16)).slice(-2); }).join(' ')
                    });
                }
            });
            send({type: 'info', msg: 'Hooked hid_write at ' + exports2[i].address});
            break;
        }
    }
}

send({type: 'info', msg: 'All hooks installed. Now change colors in HECATE app!'});
"""


def on_message(message, data):
    if message['type'] == 'send':
        payload = message['payload']
        msg_type = payload.get('type', '')
        if msg_type == 'info':
            print(f"[INFO] {payload['msg']}")
        else:
            print(f"\n{'='*60}")
            print(f"[CAPTURED] {msg_type}")
            for k, v in payload.items():
                if k != 'type':
                    print(f"  {k}: {v}")
            print(f"{'='*60}")
    elif message['type'] == 'error':
        print(f"[ERROR] {message['description']}")


def main():
    print("=== HECATE HIDUSB Frida Hook ===\n")

    # Find HECATE.exe process
    device = frida.get_local_device()
    processes = device.enumerate_processes()

    hecate_pid = None
    for proc in processes:
        if 'hecate' in proc.name.lower():
            hecate_pid = proc.pid
            print(f"Found HECATE.exe: PID={proc.pid}")
            break

    if not hecate_pid:
        print("HECATE.exe not found! Start it first.")
        return

    # Attach
    session = device.attach(hecate_pid)
    print("Attached to HECATE.exe")

    script = session.create_script(HOOK_SCRIPT)
    script.on('message', on_message)
    script.load()
    print("\nHooks installed. Now change colors in HECATE app!")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nDetaching...")
        session.detach()


if __name__ == "__main__":
    main()
