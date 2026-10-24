import importlib.util
import hashlib
import json
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('draft', ROOT / 'scripts/publish-preview-draft.py')
draft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(draft)
SOURCE, PREVIOUS = 'a' * 40, 'b' * 40


class DraftPublicationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = pathlib.Path(self.tmp.name)
        for name in ['catalogue.json', 'catalogue.sig', 'install.sh', 'SHA256SUMS', 'RELEASE_NOTES.md']:
            (self.directory / name).write_text('public fixture')

    def perform(self, existing=None, tag_exists=False, previous=PREVIOUS, fail_upload=False,
                publish_during_upload=False, corrupt_upload=False):
        calls = []
        def invoke(args):
            calls.append(args)
            if args[0] == 'git': return subprocess.CompletedProcess(args, 0 if tag_exists else 2, '')
            if args[1] == 'api':
                value = existing if '/releases/' in args[2] else ([existing] if existing else [])
                return subprocess.CompletedProcess(args, 0, json.dumps(value))
            if args[2] == 'upload' and not fail_upload:
                existing['assets'] = [{'name': p.name, 'size': p.stat().st_size,
                    'digest': 'sha256:' + ('0' * 64 if corrupt_upload else hashlib.sha256(p.read_bytes()).hexdigest())}
                    for p in self.directory.iterdir()]
                if publish_during_upload: existing['draft'] = False
            return subprocess.CompletedProcess(args, 1 if fail_upload and args[2] == 'upload' else 0, '')
        try:
            draft.publish(self.directory, 'v0.1.0-preview.10', '10', SOURCE, previous, invoke=invoke)
        finally:
            self.calls = calls

    def test_creates_new_private_draft_and_resumes_only_identified_draft(self):
        self.perform()
        self.assertTrue(any(c[:3] == ['gh', 'release', 'create'] for c in self.calls))
        old = {'id': 7, 'tag_name': 'v0.1.0-preview.10', 'draft': True, 'target_commitish': PREVIOUS}
        self.perform(old)
        self.assertTrue(any(c[:3] == ['gh', 'release', 'upload'] for c in self.calls))
        self.assertTrue(any(c[:3] == ['gh', 'release', 'edit'] for c in self.calls))

    def test_published_tag_release_or_foreign_source_refuse_without_mutation(self):
        for changes, tag_exists, previous in [({}, True, PREVIOUS), ({'draft': False}, False, PREVIOUS),
                ({'target_commitish': 'c' * 40}, False, PREVIOUS), ({}, False, '')]:
            old = {'id': 7, 'tag_name': 'v0.1.0-preview.10', 'draft': True, 'target_commitish': PREVIOUS, **changes}
            with self.assertRaises(ValueError): self.perform(old, tag_exists, previous)
            self.assertFalse(any(c[:2] == ['gh', 'release'] for c in self.calls))

    def test_failed_upload_does_not_retarget_draft(self):
        old = {'id': 7, 'tag_name': 'v0.1.0-preview.10', 'draft': True, 'target_commitish': PREVIOUS}
        with self.assertRaises(ValueError): self.perform(old, fail_upload=True)
        self.assertFalse(any(c[:3] == ['gh', 'release', 'edit'] for c in self.calls))

    def test_unchanged_remote_digests_avoid_reupload(self):
        old = {'id': 7, 'tag_name': 'v0.1.0-preview.10', 'draft': True, 'target_commitish': PREVIOUS,
               'assets': [{'name': p.name, 'size': p.stat().st_size,
                           'digest': 'sha256:' + hashlib.sha256(p.read_bytes()).hexdigest()}
                          for p in self.directory.iterdir()]}
        self.perform(old)
        self.assertFalse(any(c[:3] == ['gh', 'release', 'upload'] for c in self.calls))

    def test_publication_race_or_wrong_uploaded_digest_prevents_retarget(self):
        for changes in ({'publish_during_upload': True}, {'corrupt_upload': True}):
            old = {'id': 7, 'tag_name': 'v0.1.0-preview.10', 'draft': True, 'target_commitish': PREVIOUS}
            with self.assertRaises(ValueError): self.perform(old, **changes)
            self.assertFalse(any(c[:3] == ['gh', 'release', 'edit'] for c in self.calls))


if __name__ == '__main__': unittest.main(verbosity=2)
