import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import ci_private_build as ci


class PrivateBuildTests(unittest.TestCase):
    def archive(self, root, members):
        path = root / 'private.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            for name, data in members:
                archive.writestr(name, data)
        return path

    def test_hashes_select_roles_regardless_of_names_and_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = {name: hashlib.sha256(data).hexdigest()
                        for name, data in [('retail', b'US!!'), ('translated', b'CN!!')]}
            archive = self.archive(root, [('wrong-us-name.gba', b'CN!!'), ('../../elsewhere', b'US!!')])
            with patch.object(ci, 'ROM_BYTES', 4), patch.object(ci, 'ROM_HASHES', expected):
                found = ci.identify(archive, root / 'inputs')
            self.assertEqual(found['retail'].read_bytes(), b'US!!')
            self.assertEqual(found['translated'].read_bytes(), b'CN!!')
            self.assertEqual(set(p.name for p in (root / 'inputs').iterdir()),
                             {'retail.gba', 'translated.gba'})

    def test_wrong_missing_and_duplicate_roms_fail(self):
        expected = dict(retail=ci.sha(b'US!!'), translated=ci.sha(b'CN!!'))
        cases = [([('us.gba', b'bad!')], 'Unsupported ROM'),
                 ([('us.gba', b'US!!')], 'exactly one'),
                 ([('one', b'US!!'), ('two', b'US!!')], 'Duplicate ROM'),
                 ([('small.gba', b'bad')], 'ROM size')]
        for members, error in cases:
            with self.subTest(error=error), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                archive = self.archive(root, members)
                with patch.object(ci, 'ROM_BYTES', 4), patch.object(ci, 'ROM_HASHES', expected):
                    with self.assertRaisesRegex(ValueError, error):
                        ci.identify(archive, root / 'inputs')

    def test_workflow_is_manual_opt_in_and_uploads_only_allowlisted_outputs(self):
        workflow = (ci.ROOT / '.github/workflows/private-rom-build.yml').read_text()
        self.assertIn('  workflow_dispatch:', workflow)
        self.assertNotIn('  push:', workflow)
        self.assertNotIn('  pull_request:', workflow)
        self.assertNotIn('  schedule:', workflow)
        self.assertIn("vars.ENABLE_PRIVATE_ROM_BUILD == 'true'", workflow)
        upload = workflow.split('      - name: Upload patch')[1].split('      - name: Remove')[0]
        self.assertIn('ffta-us-cn.ips', upload)
        self.assertIn('build-report.json', upload)
        self.assertNotIn('.gba', upload)
        self.assertNotIn('ffta-private', upload)
        self.assertIn('always()', workflow)
        self.assertIn('secrets.PRIVATE_ROM_SSH_KEY', workflow)
        self.assertIn('vars.PRIVATE_ROM_REVISION', workflow)
        self.assertIn('python3 tools/fetch_dependencies.py', workflow)


if __name__ == '__main__':
    unittest.main()
