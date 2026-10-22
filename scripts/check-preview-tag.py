#!/usr/bin/env python3
"""Refuse frozen/old tags and inconsistent package revisions before publication."""
import re
import sys

match = re.fullmatch(r'v0\.1\.0-preview\.([0-9]+)', sys.argv[1] if len(sys.argv) == 3 else '')
if not match or int(match[1]) < 10 or match[1] != sys.argv[2]:
    raise SystemExit('Use a new preview >=10 whose suffix equals the package revision; published tags stay immutable.')
