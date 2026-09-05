import frida, time, json, sys

device = frida.get_local_device()
session = device.attach(18120)

script_code = r'''
var mods = Process.enumerateModules();
var result = [];
for (var i = 0; i < mods.length; i++) {
    var m = mods[i].name.toLowerCase();
    if (m.indexOf('conf') >= 0 || m.indexOf('hid') >= 0 || m.indexOf('hecate') >= 0) {
        result.push('MODULE: ' + mods[i].name + ' @ ' + mods[i].base);
        try {
            var exps = mods[i].enumerateExports();
            for (var j = 0; j < exps.length; j++) {
                var n = exps[j].name;
                if (n.indexOf('Report') >= 0 || n.indexOf('Output') >= 0 ||
                    n.indexOf('Write') >= 0 || n.indexOf('Light') >= 0 ||
                    n.indexOf('Send') >= 0 || n.indexOf('Set') >= 0) {
                    result.push('  ' + n + ' @ ' + exps[j].address);
                }
            }
        } catch(e) {}
    }
}
send(result.join('\n'));
'''

def on_message(msg, data):
    if msg['type'] == 'send':
        print(msg['payload'])
    else:
        print(f'ERR: {msg}')

script = session.create_script(script_code)
script.on('message', on_message)
script.load()
time.sleep(2)
session.detach()
