#!/usr/bin/env python3
"""Bind successful CI checks to exact source/packages; qualify preview scope only."""
import argparse
import json
import os
import pathlib
import re
import subprocess

from release_schema import describe, load, require, validate

ABI_CHECKS = {'static_elf', 'selected_cpu_startup', 'private_input_rejection', 'linux_tun_lifecycle', 'native_dns_tls',
              'private_dns_selected_cpu', 'private_dns_nftset_config'}
VM_CHECKS = {'clean_firmware_boot', 'native_package_transaction', 'offline_dependencies', 'signature_rejection',
             'repeat_install', 'settings_preserved', 'native_runtime_dns_firewall_luci'}


def source():
    value = subprocess.run(['git', 'rev-parse', 'HEAD'], check=True, capture_output=True, text=True).stdout.strip()
    require(re.fullmatch('[0-9a-f]{40}', value), 'Invalid source commit')
    require(not os.environ.get('GITHUB_SHA') or value == os.environ['GITHUB_SHA'], 'CI/source commit mismatch')
    return value


def package_binding(manifest):
    return [{k: p[k] for k in ('role', 'name', 'sha256', 'size', 'version')} for p in manifest['packages']]


def validate_vm_test_disk(disk):
    require(isinstance(disk, dict) and disk.get('physical_device') is False and
            disk.get('disk_expanded') is True and
            type(disk.get('original_root_bytes')) is int and
            0 < disk['original_root_bytes'] < 1073741824 and
            type(disk.get('test_root_bytes')) is int and disk['test_root_bytes'] == 1073741824,
            'VM must disclose its expanded disposable root; stock storage is not qualified')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('abi', 'qualify'))
    parser.add_argument('--directory', required=True, type=pathlib.Path)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--vm-evidence', type=pathlib.Path)
    parser.add_argument('--backend-manifest', type=pathlib.Path, help='Exact x86 candidate whose packages the clean firmware VM installed')
    parser.add_argument('--migration-evidence', type=pathlib.Path, help='Signed r9 native ARM package transaction proof for the original tuple')
    args = parser.parse_args()
    root = args.directory
    path = root / (args.profile + '-manifest.json')
    manifest = validate(load(path), root)
    require(manifest['schema'] == 2 and manifest['profile_id'] == args.profile, 'Evidence/profile mismatch')
    commit = source()
    abi_path = root / (args.profile + '-abi-evidence.json')
    if args.action == 'abi':
        # Called only after the SDK builder's selected-ABI smoke/TLS and native
        # package-payload/TUN and extracted private DNS commands have returned
        # success under set -e, using the matching SDK musl/target libraries.
        evidence = {'schema': 1, 'kind': 'selected_abi', 'source_commit': commit,
                    'profile_id': args.profile, 'physical_device': False,
                    'packages': package_binding(manifest), 'checks': sorted(ABI_CHECKS)}
        abi_path.write_text(json.dumps(evidence, indent=2) + '\n')
        return
    require(args.vm_evidence is not None and args.backend_manifest is not None, 'Native firmware VM evidence and backend package manifest are required')
    abi, vm = load(abi_path), load(args.vm_evidence)
    require(abi.get('kind') == 'selected_abi' and abi.get('source_commit') == commit and
            abi.get('profile_id') == args.profile and abi.get('packages') == package_binding(manifest) and
            set(abi.get('checks', [])) == ABI_CHECKS, 'Selected ABI evidence does not bind this build')
    require(vm.get('kind') == 'clean_openwrt_vm' and vm.get('source_commit') == commit and
            vm.get('openwrt') == manifest['platform']['openwrt'] and
            vm.get('package_manager') == manifest['platform']['package_manager'] and
            set(vm.get('checks', [])) == VM_CHECKS and vm.get('result') == 'pass', 'Clean native firmware acceptance missing or mismatched')
    require(vm.get('image', {}).get('sha256') and vm.get('physical_device') is False, 'VM scope/image proof missing')
    validate_vm_test_disk(vm['image'].get('test_disk'))
    backend = validate(load(args.backend_manifest), args.backend_manifest.parent)
    expected_vm = 'official-' + manifest['platform']['openwrt'] + '-x86-64-x86_64'
    require(backend['profile_id'] == expected_vm and vm.get('profile_id') == expected_vm and
            vm.get('packages') == package_binding(backend), 'Native firmware proof does not bind the exact backend packages')
    # The firmware/backend checks are shared source; ABI-specific execution and
    # native feed signatures/kernel ABI are independently checked for each tuple.
    # This is explicitly preview acceptance, never real-board or VK certification.
    require(manifest['requirements'].get('kernel_package') and manifest['dependency_bundle']['packages'], 'Authenticated dependency closure is missing')
    extra = []
    if args.profile == 'official-25.12.5-mediatek-filogic-aarch64_cortex-a53':
        require(args.migration_evidence is not None, 'Original r9 tuple requires native signed migration evidence')
        migration = load(args.migration_evidence)
        require(migration.get('kind') == 'native_r9_migration' and migration.get('result') == 'pass' and
                migration.get('profile_id') == args.profile and migration.get('source_commit') == commit and
                migration.get('packages') == package_binding(manifest) and migration.get('physical_device') is False and
                migration.get('package_scripts') is False and
                set(migration.get('checks', [])) == {'public_signed_r9', 'native_apk_upgrade', 'native_apk_rollback',
                    'settings_identity_budget_preserved', 'offline_upgrade_rollback', 'package_scripts_disabled'},
                'Native signed r9 migration proof is incomplete or mismatched')
        extra.append(args.migration_evidence)
    vm_copy = root / args.vm_evidence.name
    if vm_copy.resolve() != args.vm_evidence.resolve():
        vm_copy.write_bytes(args.vm_evidence.read_bytes())
    manifest['qualification'] = {
        'installation': True, 'activation': True, 'preview': True, 'physical_device': False,
        'reason': 'clean_official_firmware_vm_and_selected_abi_preview',
        'evidence': [abi_path.name, vm_copy.name, *(p.name for p in extra)],
        'scope': {'firmware_backend': 'clean_openwrt_vm', 'abi': 'selected_cpu_emulation_linux_tun_dns_tls',
                  'native_device_vk': 'unverified'},
        'proofs': [describe(abi_path), describe(vm_copy), *(describe(p) for p in extra)],
        'source_commit': commit,
    }
    validate(manifest, root)
    text = json.dumps(manifest, indent=2) + '\n'
    path.write_text(text)
    (root / 'manifest.json').write_text(text)
    # A stale prequalification signature must never be mistaken for the final one.
    path.with_suffix('.sig').unlink(missing_ok=True)
    (root / 'manifest.sig').unlink(missing_ok=True)
    print('Preview qualification bound to successful VM/source/ABI/package evidence; physical router/VK unverified.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit('release evidence: ' + str(error)) from None
