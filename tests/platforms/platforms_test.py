#!/usr/bin/env python3
"""Fail-closed SDK selection, ELF ABI and archive boundary regressions."""
import copy
import importlib.util
import io
import json
import pathlib
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from binary_abi import validate_elf
from platforms import load_registry, select_profile, shell_environment, validate_profile, verify_sdk

spec = importlib.util.spec_from_file_location('native_ipk', ROOT / 'scripts/test-native-ipk.py')
native_ipk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native_ipk)
smoke_spec = importlib.util.spec_from_file_location('platform_smoke', ROOT / 'scripts/test-platform.py')
platform_smoke = importlib.util.module_from_spec(smoke_spec)
smoke_spec.loader.exec_module(platform_smoke)
runtime_spec = importlib.util.spec_from_file_location('private_runtime', ROOT / 'scripts/private-runtime.py')
private_runtime = importlib.util.module_from_spec(runtime_spec)
runtime_spec.loader.exec_module(private_runtime)


def tar_bytes(members):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for name, body in members:
            info = tarfile.TarInfo(name)
            info.size = len(body)
            archive.addfile(info, io.BytesIO(body))
    return stream.getvalue()


def elf(machine=183, interp=False, needed=False):
    header = bytearray(64)
    header[:7] = b'\x7fELF\x02\x01\x01'
    struct.pack_into('<HHI', header, 16, 2, machine, 1)
    struct.pack_into('<Q', header, 32, 64)
    struct.pack_into('<HHH', header, 52, 64, 56, 2)
    first = struct.pack('<IIQQQQQQ', 1, 5, 0, 0, 0, 208, 208, 4096)
    second = struct.pack('<IIQQQQQQ', 3 if interp else 2, 4, 176, 0, 0, 32, 32, 8)
    return bytes(header) + first + second + struct.pack('<qQqQ', 1 if needed else 0, 1, 0, 0)


class PlatformsTest(unittest.TestCase):
    def setUp(self):
        self.registry = load_registry()
        self.profile = select_profile(self.registry)
        self.directory = tempfile.TemporaryDirectory(prefix='csqtt-platform-tests-')
        self.addCleanup(self.directory.cleanup)
        self.root = pathlib.Path(self.directory.name)

    def test_default_keeps_preview_sdk_and_new_profiles_are_unqualified(self):
        self.assertEqual(self.profile['openwrt'], '25.12.5')
        self.assertEqual(self.profile['sdk']['sha256'], 'ff4a38a397caa2cfe1c39e18f84ddede14878221b3593c3f2c4cfe24e3ec4c25')
        self.assertEqual(len(self.registry['profiles']), 8)
        for profile in self.registry['profiles']:
            self.assertFalse(profile['qualification']['installation'])
            self.assertFalse(profile['qualification']['activation'])
            self.assertIn('SDK_SHA=', shell_environment(profile))

    def test_unknown_vendor_armv7_and_mips_cannot_fall_back_by_cpu(self):
        for profile_id in ('unknown', 'glinet-stable-4.11-gl-mt6000', 'armv7', 'mips', 'mipsel'):
            with self.assertRaises(ValueError):
                select_profile(self.registry, profile_id)
        for values in ({'architecture': 'mips_24kc'}, {'architecture': 'arm_cortex-a7_neon-vfpv4'}, {'family': 'glinet'}):
            profile = dict(self.profile, **values)
            with self.assertRaises(ValueError):
                validate_profile(profile)

    def test_wrong_manager_sdk_origin_and_toolchain_are_rejected(self):
        changes = [lambda p: p.update(package_manager='opkg'), lambda p: p.update(goarch='amd64'),
                   lambda p: p['sdk'].update(url='https://example.com/sdk.tar.zst'),
                   lambda p: p['sdk'].update(toolchain_prefix='x86_64-openwrt-linux-musl'),
                   lambda p: p['qualification'].update(installation=True)]
        for change in changes:
            profile = copy.deepcopy(self.profile)
            change(profile)
            with self.assertRaises(ValueError):
                validate_profile(profile)

    def sdk_fixture(self):
        (self.root / '.config').write_text('CONFIG_TARGET_BOARD="mediatek"\nCONFIG_TARGET_SUBTARGET="filogic"\nCONFIG_TARGET_ARCH_PACKAGES="aarch64_cortex-a53"\n')
        (self.root / 'staging_dir/toolchain-aarch64_gcc-14.3.0').mkdir(parents=True)

    def test_sdk_headers_are_bound_to_target_and_package_abi(self):
        self.sdk_fixture()
        self.assertEqual(verify_sdk(self.profile, self.root, check_compiler=False).name, 'toolchain-aarch64_gcc-14.3.0')
        for old, changed in [('mediatek', 'x86'), ('filogic', '64'), ('aarch64_cortex-a53', 'aarch64_generic')]:
            original = (self.root / '.config').read_text()
            (self.root / '.config').write_text(original.replace(old, changed))
            with self.assertRaises(ValueError):
                verify_sdk(self.profile, self.root, check_compiler=False)
            (self.root / '.config').write_text(original)
        (self.root / 'staging_dir/toolchain-aarch64_second').mkdir()
        with self.assertRaises(ValueError):
            verify_sdk(self.profile, self.root, check_compiler=False)

    def test_elf_rejects_wrong_architecture_dynamic_loader_and_truncation(self):
        binary = self.root / 'client'
        binary.write_bytes(elf())
        validate_elf(binary, self.profile)
        for body in (elf(machine=62), elf(interp=True), elf(needed=True), elf()[:100], b'not ELF'):
            binary.write_bytes(body)
            with self.assertRaises(ValueError):
                validate_elf(binary, self.profile)
        x86 = next(p for p in self.registry['profiles'] if p['architecture'] == 'x86_64')
        binary.write_bytes(elf(machine=62))
        validate_elf(binary, x86)
        binary.write_bytes(elf(interp=True, needed=True))
        validate_elf(binary, self.profile, require_static=False)

    def dns_fixture(self):
        self.sdk_fixture()
        target = self.root / 'staging_dir/target-aarch64_cortex-a53_musl'
        target.mkdir()
        loader = self.root / 'staging_dir/toolchain-aarch64_gcc-14.3.0/lib/libc.so'
        loader.parent.mkdir()
        loader.write_bytes(elf())
        binary = self.root / 'extracted/usr/libexec/csqtt/dnsmasq'
        binary.parent.mkdir(parents=True)
        binary.write_bytes(elf(interp=True, needed=True))
        return binary.resolve(), loader.resolve(), target.resolve()

    def test_private_dns_command_uses_selected_cpu_sdk_loader_and_extracted_payload(self):
        binary, loader, target = self.dns_fixture()
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            self.assertEqual(command[:4], ['qemu-aarch64', '-cpu', 'cortex-a53', str(loader)])
            self.assertEqual(command[4:7], ['--library-path',
                             ':'.join(map(str, (target / 'usr/lib', target / 'lib', loader.parent))), str(binary)])
            self.assertEqual(kwargs['timeout'], 15)
            self.assertNotIn('LD_PRELOAD', kwargs['env'])
            self.assertNotIn('QEMU_LD_PREFIX', kwargs['env'])
            if command[-1] == '--version':
                return subprocess.CompletedProcess(command, 0, 'Dnsmasq version fixture\nCompile time options: nftset\n', '')
            self.assertEqual(command[-2], '--test')
            config = pathlib.Path(command[-1].removeprefix('--conf-file='))
            self.assertIn('nftset=/csqtt-test.invalid/4#inet#csqtt#d_test\n', config.read_text())
            self.assertIn('server=192.0.2.53@198.18.0.1\n', config.read_text())
            return subprocess.CompletedProcess(command, 0, '', 'dnsmasq: syntax check OK.\n')

        with mock.patch.object(platform_smoke.subprocess, 'run', side_effect=run), \
                mock.patch.dict(platform_smoke.os.environ, {'LD_PRELOAD': 'host.so', 'QEMU_LD_PREFIX': '/host'}):
            platform_smoke.private_dns_smoke(self.profile, binary, self.root)
        self.assertEqual(len(calls), 2)

    def test_private_dns_wrong_payload_loader_or_ambiguous_sdk_never_executes(self):
        binary, loader, target = self.dns_fixture()
        original_binary, original_loader = binary.read_bytes(), loader.read_bytes()
        with mock.patch.object(platform_smoke.subprocess, 'run') as run:
            for path in (binary, loader):
                path.write_bytes(elf(machine=62))
                with self.assertRaisesRegex(ValueError, 'selected platform'):
                    platform_smoke.private_dns_smoke(self.profile, binary, self.root)
                binary.write_bytes(original_binary)
                loader.write_bytes(original_loader)
            (target.parent / 'target-second').mkdir()
            with self.assertRaisesRegex(ValueError, 'exactly one'):
                platform_smoke.private_dns_smoke(self.profile, binary, self.root)
            run.assert_not_called()

    def test_private_dns_negative_capability_startup_and_configuration_fail(self):
        binary, _, _ = self.dns_fixture()
        for status, options in ((0, 'no-nftset'), (1, 'nftset')):
            with mock.patch.object(platform_smoke.subprocess, 'run', return_value=
                                   subprocess.CompletedProcess([], status, options, '')) as run:
                with self.assertRaisesRegex(ValueError, 'startup or nftset'):
                    platform_smoke.private_dns_smoke(self.profile, binary, self.root)
                self.assertEqual(run.call_count, 1)
        with mock.patch.object(platform_smoke.subprocess, 'run', side_effect=[
                subprocess.CompletedProcess([], 0, 'nftset', ''),
                subprocess.CompletedProcess([], 1, '', 'configuration refused')]):
            with self.assertRaisesRegex(ValueError, 'managed nftset configuration'):
                platform_smoke.private_dns_smoke(self.profile, binary, self.root)

    def test_ipk_private_dns_command_binds_the_extracted_package_bytes(self):
        profile = next(p for p in self.registry['profiles'] if p['package_format'] == 'ipk')
        payloads = {'csqtt': {'usr/bin/csqtt-client': (b'core fixture', 0o755),
                              'usr/libexec/csqtt/dnsmasq': (b'actual packaged DNS fixture', 0o755)},
                    'csqtt-captcha': {'usr/bin/csqtt-captcha': (b'broker fixture', 0o755)}}
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            if 'test-platform.py' in pathlib.Path(command[1]).name:
                binary = pathlib.Path(command[command.index('--dnsmasq') + 1])
                self.assertEqual(binary.read_bytes(), b'actual packaged DNS fixture')
                self.assertEqual(command[command.index('--sdk') + 1], str(self.root))
            return subprocess.CompletedProcess(command, 0)

        with mock.patch.object(native_ipk, 'inspect', return_value=payloads), \
                mock.patch.object(native_ipk.subprocess, 'run', side_effect=run), \
                mock.patch.object(sys, 'argv', ['test-native-ipk.py', '--profile', profile['id'],
                                              '--sdk', str(self.root), str(self.root)]):
            native_ipk.main()
        self.assertEqual(len(calls), 2)

    def test_armv7_elf32_requires_soft_float_eabi5_and_bounded_segments(self):
        profile = next(p for p in self.registry['profiles'] if p['target'] == 'armsr/armv7')
        header = bytearray(52)
        header[:7] = b'\x7fELF\x01\x01\x01'
        struct.pack_into('<HHI', header, 16, 2, 40, 1)
        struct.pack_into('<I', header, 28, 52)
        struct.pack_into('<I', header, 36, 0x05000200)
        struct.pack_into('<HHH', header, 40, 52, 32, 1)
        program = struct.pack('<IIIIIIII', 1, 0, 0, 0, 84, 84, 5, 4096)
        binary = self.root / 'arm32'
        binary.write_bytes(bytes(header) + program)
        validate_elf(binary, profile)
        for flags in (0x05000400, 0x04000200, 0):
            changed = bytearray(header)
            struct.pack_into('<I', changed, 36, flags)
            binary.write_bytes(bytes(changed) + program)
            with self.assertRaises(ValueError):
                validate_elf(binary, profile)

    def test_private_runtime_resolves_only_its_sdk_libraries_and_preserves_pins(self):
        work = self.root / 'work'
        build = work / 'ucode-build'
        sdk = work / 'sdk'
        target = sdk / 'staging_dir/target-aarch64'
        toolchain = sdk / 'staging_dir/toolchain-aarch64'
        out = self.root / 'out'
        revision = json.loads((ROOT / 'platforms/private-runtime-experiment.json').read_text())['ucode']['revision']
        for path in [build / name for name in ('ucode', 'fs.so', 'uci.so', 'ubus.so', 'libucode.so.0')] + [toolchain / 'lib/libc.so']:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(elf())
        for directory in [work / ('ucode-' + revision), sdk / 'build_dir/musl-1.1.24',
                          *(sdk / ('build_dir/' + name + '-fixture') for name in ('libubox', 'ubus', 'uci', 'json-c'))]:
            directory.mkdir(parents=True, exist_ok=True)
            (directory / 'LICENSE').write_text('synthetic license fixture')
        def dependencies(binary, _):
            return ['libucode.so.0', 'libc.so'] if binary.name == 'ucode' else []
        with mock.patch.object(private_runtime, 'needed', side_effect=dependencies):
            private_runtime.assemble(build, target, toolchain, out)
        manifest = json.loads((out / 'bundle.json').read_text())
        self.assertFalse(manifest['qualification']['installation'])
        self.assertIn('sdk_sources', manifest)
        paths = {entry['path'] for entry in manifest['files']}
        self.assertIn('usr/libexec/csqtt/ucode-runtime/lib/libc.so', paths)
        self.assertIn('usr/libexec/csqtt/ucode-runtime/modules/ubus.so', paths)
        self.assertFalse(any(path.startswith('lib/') for path in paths))
        with mock.patch.object(private_runtime, 'needed', return_value=['host-only.so']):
            with self.assertRaisesRegex(ValueError, 'unresolved'):
                private_runtime.assemble(build, target, toolchain, out)
        self.assertFalse((out / 'bundle.json').exists())

    def test_ipk_tar_boundary_rejects_traversal_duplicate_and_symlink(self):
        for members in ([('../outside', b'bad')], [('same', b'a'), ('same', b'b')], [('/absolute', b'bad')]):
            with self.assertRaises(ValueError):
                native_ipk.tar_members(tar_bytes(members))
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w:gz') as archive:
            info = tarfile.TarInfo('symlink')
            info.type = tarfile.SYMTYPE
            info.linkname = '/etc/passwd'
            archive.addfile(info)
        with self.assertRaises(ValueError):
            native_ipk.tar_members(stream.getvalue())

    def test_ipk_both_outer_formats_and_missing_metadata(self):
        control = tar_bytes([('./control', b'Package: csqtt\nVersion: 0.1.0-r1\nArchitecture: aarch64_cortex-a53\n')])
        data = tar_bytes([('./usr/bin/csqtt-client', b'fixture')])
        members = [('debian-binary', b'2.0\n'), ('control.tar.gz', control), ('data.tar.gz', data)]
        ar = bytearray(b'!<arch>\n')
        for name, body in members:
            ar.extend(f'{name + "/":<16}{0:<12}{0:<6}{0:<6}{"100644":<8}{len(body):<10}`\n'.encode('ascii'))
            ar.extend(body)
            if len(body) % 2:
                ar.extend(b'\n')
        for body in (tar_bytes(members), bytes(ar)):
            path = self.root / 'fixture.ipk'
            path.write_bytes(body)
            metadata, payload = native_ipk.read_ipk(path)
            self.assertEqual(metadata['Package'], 'csqtt')
            self.assertEqual(payload['usr/bin/csqtt-client'][0], b'fixture')
        path.write_bytes(tar_bytes(members[:2]))
        with self.assertRaises(ValueError):
            native_ipk.read_ipk(path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
