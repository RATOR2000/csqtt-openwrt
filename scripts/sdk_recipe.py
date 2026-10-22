#!/usr/bin/env python3
"""Resolve the installed SDK dnsmasq recipe from generated package metadata."""
import argparse
import pathlib
import re

from release_schema import require


def dnsmasq_recipe(sdk):
    sdk = sdk.resolve()
    info = sdk / 'tmp/.packageinfo'
    require(info.is_file() and info.stat().st_size <= 33554432, 'SDK package metadata is missing or too large')
    current, candidates = None, set()
    for line in info.read_text(encoding='utf-8').splitlines():
        if line.startswith('Source-Makefile: '):
            current = line.removeprefix('Source-Makefile: ').strip()
        elif line == 'Package: dnsmasq-full':
            require(current is not None, 'dnsmasq-full has no source recipe metadata')
            candidates.add(current)
    require(len(candidates) == 1, 'SDK dnsmasq-full source recipe is missing or ambiguous')
    name = candidates.pop()
    require(re.fullmatch(r'package/[A-Za-z0-9_./+-]+/Makefile', name) and '..' not in pathlib.PurePosixPath(name).parts,
            'SDK source recipe path is unsafe')
    logical = pathlib.PurePosixPath(name).parent
    recipe = (sdk / name).resolve()
    require(recipe.is_relative_to(sdk) and recipe.is_file(), 'SDK source recipe escapes the SDK or is absent')
    content = recipe.read_text(encoding='utf-8')
    require(re.search(r'^PKG_NAME\s*:?=\s*dnsmasq\s*$', content, re.MULTILINE), 'SDK metadata points to a different package recipe')
    return logical.as_posix() + '/compile', recipe.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', required=True, type=pathlib.Path)
    parser.add_argument('--field', required=True, choices=('target', 'directory'))
    args = parser.parse_args()
    target, directory = dnsmasq_recipe(args.sdk)
    print(target if args.field == 'target' else directory)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as error:
        raise SystemExit('SDK dnsmasq recipe: ' + str(error)) from None
