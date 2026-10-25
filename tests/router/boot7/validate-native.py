"""Compile embedded recovery ucode without executing it or changing policy."""
from pathlib import Path
import re
import subprocess

source = Path(__file__).resolve().parent
output = source.parents[2] / '.work' / 'boot7'
output.mkdir(parents=True, exist_ok=True)
expressions = re.findall(r"ucode -e '([^']+)'", (source / 'recovery.sh').read_text(encoding='utf-8'))
assert len(expressions) >= 6
passed = 0
for index, code in enumerate(expressions):
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                             '-o', 'ConnectTimeout=8', 'openwrt-router', 'ucode -c -o /dev/null -'],
                            input=code.encode(), capture_output=True, timeout=8)
    if result.returncode:
        (output / f'recovery-expression-{index}.private.log').write_bytes(result.stderr)
        print('embedded_ucode_compile=false')
        raise SystemExit(1)
    passed += 1
record = f'embedded_ucode_compile=true\ncompiled_expressions={passed}\n'
(output / 'recovery-compile.public.log').write_text(record, encoding='utf-8')
print(record, end='')
