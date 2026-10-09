#!/usr/bin/env python3
"""Export only committed changes for GitHub connector tree APIs (no credentials)."""
import argparse
import base64
import json
import pathlib
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument("base", nargs="?", default="origin/codex/csqtt-openwrt")
args = parser.parse_args()
git = lambda *argv: subprocess.check_output(["git", *argv])
root = pathlib.Path.cwd()
out = root / ".work" / "publish-delta"
out.mkdir(parents=True, exist_ok=True)
head = git("rev-parse", "HEAD").decode().strip()
parent = git("rev-parse", args.base).decode().strip()
base_tree = git("rev-parse", f"{args.base}^{{tree}}").decode().strip()
paths = git("diff", "--name-only", "-z", args.base, "HEAD").split(b"\0")
records, deleted = [], []
for name in filter(None, paths):
    path = name.decode("utf-8")
    line = git("ls-tree", "HEAD", "--", path).strip()
    if not line:
        deleted.append(path)
        continue
    mode, kind, sha = line.split(b"\t", 1)[0].decode().split()
    if kind != "blob":
        raise SystemExit(f"Unsupported tree entry: {path}")
    data = git("cat-file", "blob", sha)
    try:
        content, encoding = data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        content, encoding = base64.b64encode(data).decode(), "base64"
    for offset in range(0, max(1, len(content)), 24000):
        records.append(dict(path=path, mode=mode, encoding=encoding, part=offset // 24000, content=content[offset:offset + 24000]))
for i, record in enumerate(records):
    (out / f"{i}.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
manifest = dict(head=head, parent=parent, base_tree=base_tree, pages=len(records), deleted=deleted)
(out / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
print(json.dumps(manifest))
