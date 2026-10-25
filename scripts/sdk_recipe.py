#!/usr/bin/env python3
"""Resolve the installed SDK dnsmasq recipe from generated package metadata."""
import argparse
import pathlib
import re

from release_schema import require


def dnsmasq_source_identity(recipe):
    """Source uses the upstream version; package versions may be normalized.

    Do not evaluate Make expressions or shell fragments. Accept only the
    literal upstream identity and the recipe's exact source archive mapping.
    """
    content = (recipe / 'Makefile').read_text(encoding='utf-8')
    def assignment(name, required=True):
        values = re.findall(r'^' + name + r'[ \t]*(?::=|=)[ \t]*([^\r\n]*?)[ \t]*$', content, re.MULTILINE)
        require(len(values) == 1 or (not required and not values), 'SDK recipe has missing or ambiguous ' + name)
        return values[0] if values else None
    upstream = assignment('PKG_UPSTREAM_VERSION', required=False)
    variable = 'PKG_UPSTREAM_VERSION' if upstream is not None else 'PKG_VERSION'
    version = upstream if upstream is not None else assignment('PKG_VERSION')
    require(re.fullmatch(r'[0-9][0-9.]+', version), 'SDK upstream source version is not a literal release')
    require(assignment('PKG_SOURCE') == '$(PKG_NAME)-$(' + variable + ').tar.xz', 'SDK recipe source archive mapping differs')
    digest = assignment('PKG_HASH')
    require(re.fullmatch(r'[0-9a-f]{64}', digest), 'SDK recipe upstream source hash is not literal SHA256')
    return version, digest


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
