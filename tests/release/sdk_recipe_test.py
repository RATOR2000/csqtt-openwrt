#!/usr/bin/env python3
"""SDK recipe targets and GPL source archive follow actual package metadata."""
import hashlib
import pathlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from sdk_recipe import dnsmasq_recipe, dnsmasq_source_identity


class SdkRecipeTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        self.sdk = self.root / 'sdk'
        (self.sdk / 'tmp').mkdir(parents=True)

    def recipe(self, relative):
        path = self.sdk / relative / 'Makefile'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('PKG_NAME:=dnsmasq\nPKG_VERSION:=2.93\nPKG_SOURCE:=$(PKG_NAME)-$(PKG_VERSION).tar.xz\n', encoding='utf-8')
        (self.sdk / 'tmp/.packageinfo').write_text('Source-Makefile: ' + relative + '/Makefile\nPackage: dnsmasq\nPackage: dnsmasq-full\n', encoding='utf-8')
        return path

    def test_installed_feed_recipe_provides_the_actual_make_target(self):
        recipe = self.recipe('package/feeds/base/dnsmasq')
        target, actual = dnsmasq_recipe(self.sdk)
        self.assertEqual(target, 'package/feeds/base/dnsmasq/compile')
        self.assertEqual(actual, recipe.parent.resolve())

    def test_classic_recipe_is_supported_only_when_metadata_selects_it(self):
        self.recipe('package/network/services/dnsmasq')
        self.assertEqual(dnsmasq_recipe(self.sdk)[0], 'package/network/services/dnsmasq/compile')
        (self.sdk / 'tmp/.packageinfo').write_text('Package: dnsmasq-full\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            dnsmasq_recipe(self.sdk)

    def test_missing_ambiguous_and_traversing_metadata_refuse(self):
        self.recipe('package/feeds/base/dnsmasq')
        info = self.sdk / 'tmp/.packageinfo'
        for data in ('Source-Makefile: package/feeds/base/other/Makefile\nPackage: dnsmasq\n',
                     info.read_text() + 'Source-Makefile: package/other/dnsmasq/Makefile\nPackage: dnsmasq-full\n',
                     'Source-Makefile: package/../../outside/Makefile\nPackage: dnsmasq-full\n'):
            info.write_text(data, encoding='utf-8')
            with self.assertRaises(ValueError):
                dnsmasq_recipe(self.sdk)

    def test_unrelated_recipe_cannot_satisfy_dnsmasq_metadata(self):
        path = self.recipe('package/feeds/base/dnsmasq')
        path.write_text('PKG_NAME:=other\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            dnsmasq_recipe(self.sdk)

    def test_modern_upstream_source_version_is_distinct_from_normalized_package_version(self):
        recipe = self.recipe('package/feeds/base/dnsmasq')
        modern = ('PKG_NAME:=dnsmasq\nPKG_UPSTREAM_VERSION:=2.93\n'
                  'PKG_VERSION:=$(subst test,~~test,$(subst rc,~rc,$(PKG_UPSTREAM_VERSION)))\n'
                  'PKG_SOURCE:=$(PKG_NAME)-$(PKG_UPSTREAM_VERSION).tar.xz\nPKG_HASH:=' + 'a' * 64 + '\n')
        recipe.write_text(modern, encoding='utf-8')
        self.assertEqual(dnsmasq_source_identity(recipe.parent), ('2.93', 'a' * 64))
        for bad in (modern.replace('PKG_UPSTREAM_VERSION:=2.93', 'PKG_UPSTREAM_VERSION:=$(shell unexpected)'),
                    modern + 'PKG_UPSTREAM_VERSION:=2.92\n',
                    modern.replace('PKG_SOURCE:=$(PKG_NAME)-$(PKG_UPSTREAM_VERSION).tar.xz', 'PKG_SOURCE:=different.tar.xz'),
                    modern.replace('PKG_HASH:=' + 'a' * 64, 'PKG_HASH:=$(shell unexpected)')):
            recipe.write_text(bad, encoding='utf-8')
            with self.assertRaises(ValueError):
                dnsmasq_source_identity(recipe.parent)

    def test_build_retains_source_with_unset_config_and_empty_make_override(self):
        build = (ROOT / 'scripts/build-sdk.sh').read_text(encoding='utf-8')
        self.assertIn("sed -i '/^CONFIG_AUTOREMOVE=/d; /^# CONFIG_AUTOREMOVE is not set$/d' .config", build)
        self.assertIn('# CONFIG_AUTOREMOVE is not set\nCONFIG_PACKAGE_csqtt=m', build)
        self.assertIn('run_logged private-dns make "$DNS_COMPILE_TARGET" -j2 V=s CONFIG_AUTOREMOVE=', build)
        self.assertIn('run_logged packages make package/csqtt-local/luci-app-csqtt/compile -j2 V=s \\\n    CONFIG_AUTOREMOVE= \\', build)
        self.assertNotIn('CONFIG_AUTOREMOVE=n', build)

    @unittest.skipUnless(shutil.which('make'), 'GNU Make fixture runs in Linux CI; no local make executable')
    def test_gnu_make_empty_disables_cleanup_but_literal_n_enables_it(self):
        fixture = ROOT / 'tests/release/fixtures/sdk-autoremove.mk'
        for flag, expected in (('', 'source-preserved'), ('n', 'cleanup-enabled'), ('y', 'cleanup-enabled')):
            result = subprocess.run(['make', '--no-print-directory', '-f', str(fixture),
                                     'CONFIG_AUTOREMOVE=' + flag, 'check'], check=True, capture_output=True, text=True)
            self.assertEqual(result.stdout.strip(), expected)

    def test_corresponding_source_includes_exact_recipe_license_and_source(self):
        recipe = self.recipe('package/feeds/base/dnsmasq')
        upstream = self.sdk / 'dl/dnsmasq-2.93.tar.xz'
        upstream.parent.mkdir()
        upstream.write_bytes(b'public upstream source archive fixture')
        with recipe.open('a', encoding='utf-8') as stream:
            stream.write('PKG_HASH:=' + hashlib.sha256(upstream.read_bytes()).hexdigest() + '\n')
        source = self.sdk / 'build_dir/target/dnsmasq-full/dnsmasq-2.93'
        source.mkdir(parents=True)
        (source / 'COPYING').write_text('public license fixture\n', encoding='utf-8')
        (source / 'source.c').write_text('public patched source fixture\n', encoding='utf-8')
        (self.sdk / '.config').write_text('CONFIG_PACKAGE_dnsmasq_full_nftset=y\n', encoding='utf-8')
        output = self.root / 'output'
        output.mkdir()
        args = [sys.executable, str(ROOT / 'scripts/package-dnsmasq-source.py'), '--profile',
                'official-25.12.5-x86-64-x86_64', '--source', str(source), '--sdk', str(self.sdk), '--output', str(output)]
        subprocess.run(args, check=True, capture_output=True)
        with tarfile.open(next(output.glob('*.tar.gz')), 'r:gz') as archive:
            names = archive.getnames()
            self.assertIn('openwrt-package-recipe/Makefile', names)
            self.assertIn('patched-source/COPYING', names)
            self.assertIn('patched-source/source.c', names)
            self.assertIn('upstream/dnsmasq-2.93.tar.xz', names)
        legacy = recipe.read_text(encoding='utf-8')
        modern = legacy.replace('PKG_VERSION:=2.93', 'PKG_UPSTREAM_VERSION:=2.93\nPKG_VERSION:=$(subst test,~~test,$(subst rc,~rc,$(PKG_UPSTREAM_VERSION)))')
        modern = modern.replace('$(PKG_NAME)-$(PKG_VERSION).tar.xz', '$(PKG_NAME)-$(PKG_UPSTREAM_VERSION).tar.xz')
        recipe.write_text(modern, encoding='utf-8')
        subprocess.run(args, check=True, capture_output=True)
        recipe.write_text(modern.replace('PKG_UPSTREAM_VERSION:=2.93', 'PKG_UPSTREAM_VERSION:=2.92'), encoding='utf-8')
        self.assertNotEqual(subprocess.run(args, capture_output=True).returncode, 0)
        recipe.write_text(modern, encoding='utf-8')
        upstream.write_bytes(b'changed source')
        self.assertNotEqual(subprocess.run(args, capture_output=True).returncode, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
