import frida, time, json

device = frida.get_local_device()
session = device.attach(18120)

script_code = r'''
var hooks = [
    'CS_UsbMusicLed_SetColorModeData',
    'CS_UsbMusicLed_SetRCModeData',
    'CS_UsbMusicLed_SetRCModeConfig',
    'UsbMusicLed_SetColorModeData',
    'UsbMusicLed_SetRCModeData',
];

var hidDll = Process.findModuleByName('HID.DLL');
var hidSetReport = null;
if (hidDll) {
    var exps = hidDll.enumerateExports();
    for (var i = 0; i < exps.length; i++) {
        if (exps[i].name === 'HidD_SetOutputReport') {
            hidSetReport = exps[i].address;
            break;
        }
    }
}

var hidUsb = Process.findModuleByName('HIDUsb.dll');
if (!hidUsb) {
    send('ERROR: HIDUsb.dll not found');
} else {
    var allExps = hidUsb.enumerateExports();
    for (var i = 0; i < allExps.length; i++) {
        var name = allExps[i].name;
        if (hooks.indexOf(name) >= 0) {
            (function(fname, faddr) {
                Interceptor.attach(faddr, {
                    onEnter: function(args) {
                        var data = [];
                        // Read up to 64 bytes from first pointer arg
                        for (var a = 0; a < 4; a++) {
                            try {
                                var ptr = args[a];
                                if (ptr && !ptr.isNull()) {
                                    var b = Memory.readU8(ptr);
                                    if (b !== 0 || a === 0) {
                                        var buf = Memory.readByteArray(ptr, 32);
                                        data.push('arg' + a + ': ' + Array.from(new Uint8Array(buf)).map(function(x){return ('0'+x.toString(16)).slice(-2)}).join(' '));
                                    }
                                }
                            } catch(e) {}
                        }
                        send({func: fname, args: data});
                    }
                });
                send('Hooked: ' + fname);
            })(name, allExps[i].address);
        }
    }
}

// Also hook HidD_SetOutputReport
if (hidSetReport) {
    Interceptor.attach(hidSetReport, {
        onEnter: function(args) {
            try {
                var len = args[2].toInt32();
                if (len > 0 && len <= 128) {
                    var buf = Memory.readByteArray(args[1], len);
                    var hex = Array.from(new Uint8Array(buf)).map(function(x){return ('0'+x.toString(16)).slice(-2)}).join(' ');
                    send({func: 'HidD_SetOutputReport', len: len, data: hex});
                }
            } catch(e) {
                send({func: 'HidD_SetOutputReport', err: e.message});
            }
        }
    });
    send('Hooked: HidD_SetOutputReport');
}

send('READY - switch light modes now!');
'''

results = []
def on_message(msg, data):
    if msg['type'] == 'send':
        payload = msg['payload']
        if isinstance(payload, dict):
            print(json.dumps(payload))
            results.append(payload)
        else:
            print(payload)

script = session.create_script(script_code)
script.on('message', on_message)
script.load()

print('Capturing... switch light modes in HECATE app!')
print('Press Ctrl+C to stop.\n')

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print(f'\nCaptured {len(results)} events.')

    # Save
    out = r'E:\Downloads\Compressed\hecate-g1500-backup\hid_light_capture.json'
    with open(out, 'w') as f:
        json.dump(results, f, indent=2)
    print(f'Saved to {out}')

session.detach()
