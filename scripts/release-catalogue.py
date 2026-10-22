#!/usr/bin/env python3
"""Collect tuple manifests into catalogue.json; caller authenticates and signs."""
import argparse
import json
import pathlib
from release_schema import UPSTREAM, describe, load, require, validate

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('directory', type=pathlib.Path)
parser.add_argument('manifests', type=pathlib.Path, nargs='+')
args = parser.parse_args()
try:
    entries = []
    seen = set()
    for path in sorted(args.manifests):
        m = validate(load(path), path.parent)
        require(m['schema'] == 2 and m['profile_id'] not in seen, 'Catalogue requires unique schema2 profiles')
        require(path.name == m['profile_id'] + '-manifest.json', 'Manifest filename does not match profile')
        sig = path.with_suffix('.sig')
        require(sig.is_file() and 0 < sig.stat().st_size <= 1024, 'Detached tuple signature is required')
        seen.add(m['profile_id'])
        entries.append({**describe(path), 'profile_id': m['profile_id'], 'signature': describe(sig)})
    require(0 < len(entries) <= 128, 'Invalid catalogue profile count')
    (args.directory / 'catalogue.json').write_text(json.dumps({'schema': 2, 'upstream': UPSTREAM, 'profiles': entries}, indent=2) + '\n', encoding='utf-8')
except (ValueError, KeyError, OSError) as exc:
    raise SystemExit(str(exc))