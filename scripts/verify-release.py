#!/usr/bin/env python3
"""Check already authenticated schema1/schema2 metadata and all exact bytes."""
import argparse
import pathlib
from release_schema import load, validate

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('directory', type=pathlib.Path)
parser.add_argument('--manifest', default='manifest.json')
args = parser.parse_args()
try:
    validate(load(args.directory / args.manifest), args.directory)
except (ValueError, KeyError, OSError) as exc:
    raise SystemExit(str(exc))
print('Release package hashes and exact platform verified; signatures/acceptance are separate gates')