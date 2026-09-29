#!/usr/bin/env python3
"""Exercise the manifest producer and workflow verifier across real files."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]


class ReleaseTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='csqtt-manifest-')
        self.addCleanup(self.directory.cleanup)
        self.root = pathlib.Path(self.directory.name)
        for role in ['csqtt', 'csqtt-captcha', 'luci-app-csqtt']:
            (self.root / f'{role}-0.1.0-r1.apk').write_bytes(b'fixture package bytes')
        self.assertEqual(self.command('release-manifest.py').returncode, 0)

    def command(self, script):
        return subprocess.run([sys.executable, str(REPO / 'scripts' / script), str(self.root)],
                              capture_output=True, text=True)

    def change_manifest(self, change):
        path = self.root / 'manifest.json'
        manifest = json.loads(path.read_text())
        change(manifest)
        path.write_text(json.dumps(manifest))

    def test_produced_manifest_and_exact_artifacts(self):
        result = self.command('verify-release.py')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len((self.root / 'SHA256SUMS').read_text().splitlines()), 4)

    def test_modified_package_is_rejected(self):
        (self.root / 'csqtt-0.1.0-r1.apk').write_bytes(b'changed package bytes')
        self.assertNotEqual(self.command('verify-release.py').returncode, 0)

    def test_extra_package_is_rejected_by_both_commands(self):
        (self.root / 'extra-1.apk').write_bytes(b'extra fixture')
        self.assertNotEqual(self.command('verify-release.py').returncode, 0)
        self.assertNotEqual(self.command('release-manifest.py').returncode, 0)

    def test_wrong_target_duplicate_role_and_path_escape(self):
        for change in [lambda m: m.update(target='other/target'),
                       lambda m: m['packages'][0].update(name=m['packages'][1]['name']),
                       lambda m: m['packages'][0].update(name='../outside.apk')]:
            self.assertEqual(self.command('release-manifest.py').returncode, 0)
            self.change_manifest(change)
            self.assertNotEqual(self.command('verify-release.py').returncode, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
