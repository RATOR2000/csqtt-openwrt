#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
OUT=$(mktemp -d)
trap 'rm -rf "$OUT"' EXIT
node tests/policy/render.mjs "$OUT"
"$ROOT/.work/ucode/build/ucode" -L "$ROOT/.work/ucode/build/*.so" tests/policy/native.uc "$OUT"
cmp "$OUT/policy.nft" "$OUT/native-policy.nft"
cmp "$OUT/hold.nft" "$OUT/native-hold.nft"
cmp "$OUT/release.nft" "$OUT/native-release.nft"
for conf in "$OUT"/dns-*.conf; do
    cmp "$conf" "$OUT/native-$(basename "$conf")"
    "$ROOT/.work/dnsmasq-2.93/src/dnsmasq" --test --conf-file="$conf"
done
python3 - "$OUT" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
assert json.loads((root / 'model.json').read_text()) == json.loads((root / 'native-model.json').read_text())
PY
sudo python3 tests/policy/network-smoke.py "$OUT"
