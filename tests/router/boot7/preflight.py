from pathlib import Path
import ipaddress
import json
import re
import subprocess
source_folder = Path(__file__).resolve().parent
folder = source_folder.parents[2] / '.work' / 'boot7'
folder.mkdir(parents=True, exist_ok=True)
ps = '''$items = foreach ($nic in Get-NetAdapter | Where-Object { $_.Status -eq 'Up' -and $_.HardwareInterface }) {
    foreach ($ip in Get-NetIPAddress -InterfaceIndex $nic.ifIndex -AddressFamily IPv4) {
        @{ ip=$ip.IPAddress; mac=$nic.MacAddress.Replace('-',':').ToLower(); physical=$true }
    }
}; ConvertTo-Json -InputObject @($items) -Compress'''
nics = json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',ps], text=True))
assert isinstance(nics, list) and len(nics) <= 10
for nic in nics:
    assert ipaddress.ip_address(nic['ip']).version == 4
    assert re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', nic['mac'])
    assert nic['physical'] is True
source = (source_folder / 'preflight.uc').read_text(encoding='utf-8')
assert source.count('let windows_adapters = [];') == 1
source = source.replace('let windows_adapters = [];', 'let windows_adapters = ' + json.dumps(nics) + ';')
result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                         '-o', 'ConnectTimeout=8', 'openwrt-router', 'ucode -'],
                        input=source.encode(), capture_output=True, timeout=25)
(folder / 'preflight.public.json').write_bytes(result.stdout)
(folder / 'preflight.exit').write_text(str(result.returncode)+'\n', encoding='utf-8')
if result.stderr:
    (folder / 'preflight.stderr.private.log').write_bytes(result.stderr)
    print('Native preflight stderr saved privately')
print(result.stdout.decode('utf-8', errors='replace').strip())
print('NATIVE_PREFLIGHT_EXIT=' + str(result.returncode))
raise SystemExit(result.returncode)
