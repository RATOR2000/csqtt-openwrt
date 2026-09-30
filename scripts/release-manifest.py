#!/usr/bin/env python3
"""Describe artifacts; release signatures are applied by the release workflow."""
import hashlib
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
packages = sorted(root.glob("*.apk"))
if len(packages) != 3:
    raise SystemExit(f"Expected 3 OpenWrt packages, got {len(packages)}")
manifest = {"schema": 1, "openwrt": "25.12.5", "target": "mediatek/filogic", "architecture": "aarch64_cortex-a53", "upstream": "amurcanov/csqtt@v2.1.9", "packages": []}
for path in packages:
    manifest["packages"].append({"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "size": path.stat().st_size})
(root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
(root / "SHA256SUMS").write_text("".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in [*packages, root / "manifest.json"]), encoding="ascii")
