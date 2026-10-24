"""Stage a CHECK-ONLY private context. Never arm, edit UCI, or restart services."""
from pathlib import Path
import io
import json
import secrets
import subprocess
import tarfile

source = Path(__file__).resolve().parent
root = source.parents[2]
output = root / '.work' / 'boot7'
output.mkdir(parents=True, exist_ok=True)
binary = output / 'probe-linux-arm64'
assert binary.is_file(), 'Build the bounded ARM64 probe first'
assert binary.read_bytes()[:4] == b'\x7fELF'
files = {p.name: p.read_bytes() for p in [source / 'prepare.uc', source / 'recovery.sh']}
files[binary.name] = binary.read_bytes()
files['synthetic-macs'] = ('\n'.join('02:' + ':'.join(f'{b:02x}' for b in secrets.token_bytes(5))
                                  for _ in range(2)) + '\n').encode()
archive = io.BytesIO()
with tarfile.open(fileobj=archive, mode='w') as pack:
    for name, data in files.items():
        entry = tarfile.TarInfo(name)
        entry.mode = 0o700 if name == binary.name else 0o600
        entry.size = len(data)
        pack.addfile(entry, io.BytesIO(data))
script = '''set -eu
umask 077
for p in csqtt dhcp firewall network; do
    test -z "$(uci -q changes "$p")"
done
test ! -e /var/lock/csqtt-policy
test -L /etc/rc.d/S95csqtt
test "$(readlink /etc/rc.d/S95csqtt)" = ../init.d/csqtt
test -L /etc/rc.d/K10csqtt
test "$(readlink /etc/rc.d/K10csqtt)" = ../init.d/csqtt
state=/etc/csqtt/backups/boot7-$(date +%Y%m%d-%H%M%S)-$$
test ! -e "$state"
mkdir -m 700 "$state" "$state/baseline"
for p in csqtt dhcp firewall network; do
    cp "/etc/config/$p" "$state/baseline/$p"
    chmod 600 "$state/baseline/$p"
done
tar -xf - -C "$state"
sh -n "$state/recovery.sh"
ucode -c -o "$state/prepare.bytecode" "$state/prepare.uc" > "$state/compile.private.log" 2>&1
if ! ucode "$state/prepare.uc" "$state" > "$state/prepare.public.log" 2> "$state/prepare.private.log"; then
    cat "$state/prepare.public.log"
    printf 'context_path=%s\n' "$state"
    exit 1
fi
sha256sum /etc/config/csqtt /etc/config/dhcp /etc/config/firewall /etc/config/network \
    "$state/recovery.sh" "$state/prepare.uc" "$state/probe-linux-arm64" \
    "$state/synthetic-macs" "$state/fixture.env" "$state/closed.nft" "$state/fault-set" \
    "$state/identity" "$state/init-was-enabled" "$state"/baseline/* > "$state/armed.sha256"
set +e
sh "$state/recovery.sh" check "$state" > "$state/check.public.log" 2> "$state/check.private.log"
rc=$?
set -e
printf '%s\n' "$rc" > "$state/check.exit"
cat "$state/prepare.public.log" "$state/check.public.log"
for p in csqtt dhcp firewall network; do cmp -s "$state/baseline/$p" "/etc/config/$p"; done
echo owner_configs_unchanged=true
echo armed=false
printf 'context_path=%s\n' "$state"
exit "$rc"
'''
result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                         '-o', 'ConnectTimeout=8', 'openwrt-router', script],
                        input=archive.getvalue(), capture_output=True, timeout=35)
(output / 'context.public.log').write_bytes(result.stdout)
(output / 'context.exit').write_text(str(result.returncode) + '\n', encoding='utf-8')
if result.stderr:
    (output / 'context.stderr.private.log').write_bytes(result.stderr)
    print('SSH diagnostics saved privately')
print(result.stdout.decode(errors='replace').strip())
print('CONTEXT_STAGE_EXIT=' + str(result.returncode))
if result.returncode == 0:
    lines = result.stdout.decode().splitlines()
    state = next(line.removeprefix('context_path=') for line in lines if line.startswith('context_path='))
    (output / 'context.json').write_text(json.dumps({'state': state, 'armed': False}) + '\n', encoding='utf-8')
raise SystemExit(result.returncode)
