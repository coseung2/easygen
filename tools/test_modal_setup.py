import hashlib
import json
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from easygen_runtime.config import resource
from easygen_runtime import provision
from tools.setup_modal import plan


class SetupTest(unittest.TestCase):
    def test_names_are_independent_and_customizable(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(resource('h3'), 'my-workflow-h3')
        with patch.dict(os.environ, {'EASYGEN_WORKFLOW_PREFIX': 'alice'}):
            self.assertEqual(resource('h3-models'), 'alice-h3-models')
        with patch.dict(os.environ, {'EASYGEN_WORKFLOW_PREFIX': '../bad'}):
            with self.assertRaises(ValueError):
                resource('h3')

    def test_plan_never_deploys_personal_app(self):
        for kind in ('h3', 'image', 'music'):
            commands = plan(kind)
            self.assertEqual(commands[-1], ['deploy', f'modal/workflow_{kind}.py'])
            self.assertIn(['run', 'modal/bootstrap.py', '--target', kind], commands)
            self.assertFalse(any('easygen_team' in str(command) for command in commands))

    def test_locks_have_complete_hashes_revisions_and_safe_paths(self):
        root = Path(provision.__file__).parent
        models = json.loads((root / 'models.json').read_text())
        self.assertEqual(set(models), {'h3', 'image', 'music'})
        for group in models.values():
            targets = set()
            for item in group:
                self.assertRegex(item['revision'], r'^[0-9a-f]{40}$')
                self.assertRegex(item['sha256'], r'^[0-9a-f]{64}$')
                self.assertGreater(item['bytes'], 0)
                self.assertNotIn(item['target'], targets)
                targets.add(item['target'])
                self.assertNotIn('..', Path(item['target']).parts)
                self.assertFalse(Path(item['target']).is_absolute())

    def fixture(self):
        return {'repo': 'example/model', 'revision': 'a'*40, 'file': 'model.bin',
                'target': 'weights/model.bin', 'bytes': 7, 'sha256': hashlib.sha256(b'weights').hexdigest()}

    def test_download_verifies_then_skips_existing(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            blob=root/'blob'
            blob.write_bytes(b'weights')
            download=Mock(return_value=str(blob))
            with patch.dict('sys.modules', {'huggingface_hub': types.SimpleNamespace(hf_hub_download=download)}), \
                 patch.object(provision.json, 'loads', return_value={'h3': [self.fixture()]}):
                result=provision.provision('h3', root)
                self.assertEqual((root/'weights/model.bin').read_bytes(), b'weights')
                self.assertEqual(result[0]['bytes'], 7)
                provision.provision('h3', root)
                self.assertEqual(download.call_count, 1)
                self.assertEqual(download.call_args.kwargs['revision'], 'a'*40)

    def test_bad_existing_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'weights').mkdir()
            target=root/'weights/model.bin'
            target.write_bytes(b'wrong')
            download=Mock()
            with patch.dict('sys.modules', {'huggingface_hub': types.SimpleNamespace(hf_hub_download=download)}), \
                 patch.object(provision.json, 'loads', return_value={'h3': [self.fixture()]}):
                with self.assertRaises(ValueError):
                    provision.provision('h3',root)
            self.assertEqual(target.read_bytes(), b'wrong')
            download.assert_not_called()

    def test_verify_only_never_downloads(self):
        with tempfile.TemporaryDirectory() as directory:
            download=Mock()
            with patch.dict('sys.modules', {'huggingface_hub': types.SimpleNamespace(hf_hub_download=download)}), \
                 patch.object(provision.json, 'loads', return_value={'h3': [self.fixture()]}):
                with self.assertRaises(FileNotFoundError):
                    provision.provision('h3', directory, verify_only=True)
            download.assert_not_called()


if __name__ == '__main__':
    unittest.main()
