#!/usr/bin/env python3
"""Preserve GPL corresponding source/recipe for the SDK's private DNS payload."""
import argparse
import hashlib
import json
import pathlib
import re
import tarfile

from platforms import load_registry, select_profile
from release_schema import describe, require
from sdk_recipe import dnsmasq_recipe, dnsmasq_source_identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--source', type=pathlib.Path, required=True)
    parser.add_argument('--sdk', type=pathlib.Path, required=True)
    parser.add_argument('--output', type=pathlib.Path, required=True)
    args = parser.parse_args()
    profile = select_profile(load_registry(), args.profile)
    match = re.fullmatch(r'dnsmasq-([0-9][0-9.]+)', args.source.name)
    require(match is not None and (args.source / 'COPYING').is_file() and (args.source / 'COPYING').stat().st_size > 0,
            'Actual patched dnsmasq source/license unavailable')
    require(args.source.resolve().is_relative_to((args.sdk / 'build_dir').resolve()), 'Patched dnsmasq source is outside this SDK build directory')
    version = match[1]
    upstream = args.sdk / 'dl' / f'dnsmasq-{version}.tar.xz'
    require(upstream.is_file(), 'Exact upstream source archive unavailable')
    sha = hashlib.sha256(upstream.read_bytes()).hexdigest()
    compile_target, recipe = dnsmasq_recipe(args.sdk)
    recipe_version, recipe_hash = dnsmasq_source_identity(recipe)
    require(recipe_version == version, 'Patched source does not match the selected SDK recipe upstream version')
    require(recipe_hash == sha, 'Upstream source archive does not match the selected SDK recipe hash')
    name = profile['id'] + '--dnsmasq-corresponding-source.tar.gz'
    archive = args.output / name
    with tarfile.open(archive, 'w:gz') as output:
        def add_tree(directory, prefix):
            total = 0
            for path in sorted(directory.rglob('*')):
                relative = path.relative_to(directory)
                if (not path.is_file() or path.is_symlink() or path.suffix in ('.o', '.a', '.so')
                        or path.name == 'dnsmasq' or any(part.startswith(('.built', '.prepared', '.configured', '.pkgdir', '.git')) for part in relative.parts)):
                    continue
                total += path.stat().st_size
                require(total <= 33554432, 'Corresponding source exceeds bound')
                output.add(path, arcname=prefix + '/' + relative.as_posix(), recursive=False)
        add_tree(args.source, 'patched-source')
        add_tree(recipe, 'openwrt-package-recipe')
        output.add(upstream, arcname='upstream/' + upstream.name, recursive=False)
        output.add(args.sdk / '.config', arcname='build/openwrt-sdk.config', recursive=False)
        output.add(pathlib.Path(__file__).resolve().with_name('build-sdk.sh'), arcname='build/build-sdk.sh', recursive=False)
    notice = (f'dnsmasq {version}: GPL-2.0 (see dnsmasq-COPYING).\n'
              f'Upstream source: https://thekelleys.org.uk/dnsmasq/{upstream.name}\n'
              f'Upstream archive SHA256: {sha}\nSDK: {profile["sdk"]["url"]}\n'
              f'SDK archive SHA256: {profile["sdk"]["sha256"]}\n'
              f'SDK metadata compile target: {compile_target}\n'
              f'Corresponding patched source, upstream archive, OpenWrt recipe/patches and build configuration: {name}\n'
              'Build using the pinned SDK and build/build-sdk.sh with CSQTT_PROFILE set to this profile.\n')
    (args.output / 'dnsmasq-NOTICE').write_text(notice, encoding='utf-8')
    metadata = describe(archive, component='dnsmasq', version=version, license='GPL-2.0',
                        upstream_url='https://thekelleys.org.uk/dnsmasq/' + upstream.name, upstream_sha256=sha)
    (args.output / 'dnsmasq-source.json').write_text(json.dumps([metadata], indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError) as error:
        raise SystemExit('DNS source packaging: ' + str(error)) from None
