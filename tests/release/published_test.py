import importlib.util
import pathlib
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('published', ROOT / 'scripts/verify-published-release.py')
published = importlib.util.module_from_spec(spec)
spec.loader.exec_module(published)


class PublishedTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js unavailable')
    def test_signature_rejects_tampered_bytes_and_wrong_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            code = ("const c=require('node:crypto'),fs=require('node:fs'),p=require('node:path');"
                    "const d=process.argv[1],a=c.generateKeyPairSync('ec',{namedCurve:'prime256v1'}),"
                    "b=c.generateKeyPairSync('ec',{namedCurve:'prime256v1'});"
                    "fs.writeFileSync(p.join(d,'key.pem'),a.publicKey.export({type:'spki',format:'pem'}));"
                    "fs.writeFileSync(p.join(d,'other.pem'),b.publicKey.export({type:'spki',format:'pem'}));"
                    "fs.writeFileSync(p.join(d,'doc'),'{\"public\":true}');"
                    "fs.writeFileSync(p.join(d,'sig'),c.sign('sha256',fs.readFileSync(p.join(d,'doc')),a.privateKey));")
            subprocess.run([shutil.which('node'), '-e', code, str(root)], check=True, capture_output=True)
            published.verify_signature(root / 'doc', root / 'sig', root / 'key.pem')
            with self.assertRaises(ValueError):
                published.verify_signature(root / 'doc', root / 'sig', root / 'other.pem')
            (root / 'doc').write_bytes(b'{"public":false}')
            with self.assertRaises(ValueError):
                published.verify_signature(root / 'doc', root / 'sig', root / 'key.pem')

    def test_cached_bytes_cannot_bypass_signed_size_or_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / 'public.apk').write_bytes(b'original')
            descriptor = published.describe(root / 'public.apk')
            (root / 'public.apk').write_bytes(b'corrupted')
            with mock.patch.object(published, 'download', side_effect=lambda url, path, limit: path.write_bytes(b'bad')):
                with self.assertRaises(ValueError):
                    published.checked_asset(descriptor, 'https://github.com/', root)
            with self.assertRaises(ValueError):
                published.checked_asset({**descriptor, 'name': '../outside'}, 'https://github.com/', root)

    def test_foreign_origins_redirects_and_oversize_refuse(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'asset'
            with self.assertRaises(ValueError):
                published.download('http://github.com/asset', path)
            response = mock.MagicMock()
            response.__enter__.return_value = response
            response.url = 'https://unapproved.example/asset'
            with mock.patch.object(published.urllib.request, 'urlopen', return_value=response):
                with self.assertRaises(ValueError):
                    published.download('https://github.com/asset', path)
            response.url = 'https://release-assets.githubusercontent.com/asset'
            response.read.return_value = b'12345'
            with mock.patch.object(published.urllib.request, 'urlopen', return_value=response):
                with self.assertRaises(ValueError):
                    published.download('https://github.com/asset', path, 4)
            self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
