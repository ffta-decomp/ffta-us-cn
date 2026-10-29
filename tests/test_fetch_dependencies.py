import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from fetch_dependencies import fetch, git


@unittest.skipUnless(shutil.which('git'), 'Git required')
class DependencyFetchTests(unittest.TestCase):
    def test_fetches_pinned_git_sources_then_rejects_modified_checkout(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); upstream = root / 'upstream'; upstream.mkdir()
            source = upstream / 'source.c'; source.write_bytes(b'int value = 7;\n')
            subprocess.run(['git', 'init', '-q', str(upstream)], check=True)
            git(upstream, 'add', 'source.c')
            git(upstream, '-c', 'user.name=Dependency test', '-c', 'user.email=test@example.invalid',
                '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Synthetic source')
            revision = git(upstream, 'rev-parse', 'HEAD')
            (root / 'config').mkdir()
            dependency = dict(name='example', url=str(upstream), revision=revision,
                directory='vendor/example', files={'source.c': hashlib.sha256(source.read_bytes()).hexdigest()})
            (root / 'config/dependencies.lock.json').write_text(json.dumps(dict(schema=1, dependencies=[dependency])))
            self.assertEqual(fetch(root), 1)
            self.assertEqual(git(root / 'vendor/example', 'rev-parse', 'HEAD'), revision)
            self.assertEqual((root / 'vendor/example/source.c').read_bytes(), source.read_bytes())
            self.assertEqual(fetch(root), 1)
            (root / 'vendor/example/source.c').write_text('edited dependency')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                fetch(root)


if __name__ == '__main__':
    unittest.main()
