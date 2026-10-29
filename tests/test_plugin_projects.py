import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from plugin_projects import sync, locked, load_entry, declared


class PluginProjectTests(unittest.TestCase):
    def test_declared_python_helper_uses_isolated_relative_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = self.setup_project(root)
            (source / 'helper.py').write_text('VALUE = 7\n')
            (source / 'one.py').write_text('from .helper import VALUE\n')
            path = source / 'plugins.json'; data = json.loads(path.read_text())
            data['plugins'][0]['files'].append('helper.py')
            path.write_text(json.dumps(data))
            sync(root)
            self.assertEqual(load_entry('one', root).VALUE, 7)

    def setup_project(self, root):
        source = root / 'builtin'; source.mkdir()
        for name, value in [('one', 1), ('two', 2)]:
            (source / (name + '.py')).write_text('VALUE = %d\n' % value)
        (source / 'vendor').mkdir(); (source / 'vendor/private.bin').write_bytes(b'private test fixture')
        (source / 'tests').mkdir(); (source / 'tests/test_internal.py').write_text('raise RuntimeError()\n')
        (source / 'plugins.json').write_text(json.dumps(dict(schema=1, plugins=[
            dict(id=name, entry=name + '.py', files=[name + '.py']) for name in ['one', 'two']])))
        (root / 'config').mkdir()
        self.registry(root, dict(kind='builtin', path='builtin'))
        return source

    def registry(self, root, source):
        (root / 'config/plugin-projects.json').write_text(json.dumps(dict(schema=1, projects=[dict(id='sample', source=source)])))

    def test_one_project_exports_multiple_plugins_and_no_private_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = self.setup_project(root)
            lock = sync(root); record = lock['projects']['sample']
            self.assertEqual(set(record['plugins']), {'one', 'two'})
            self.assertEqual(set(record['files']), {'plugins.json', 'one.py', 'two.py'})
            snapshot = root / record['directory']
            self.assertEqual(snapshot, source)
            self.assertFalse((root / 'vendor/plugins').exists())
            self.assertEqual(load_entry('one', root).VALUE, 1)
            self.assertEqual(load_entry('two', root).VALUE, 2)
            (source / 'vendor/private.bin').write_bytes(b'changed internal dependency')
            locked(root)  # Undeclared development files do not affect consumers.
            (source / 'one.py').write_text('VALUE = 3\n')
            with self.assertRaisesRegex(ValueError, 'Builtin plugin changed'):
                locked(root)

    @unittest.skipUnless(shutil.which('git'), 'Git required for Git-source import')
    def test_git_import_is_commit_pinned_and_exports_only_declared_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = self.setup_project(root)
            subprocess.run(['git', 'init', '-q', str(source)], check=True)
            subprocess.run(['git', '-C', str(source), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(source), '-c', 'user.name=Plugin test',
                            '-c', 'user.email=plugin@example.invalid', '-c', 'commit.gpgsign=false',
                            'commit', '-qm', 'Synthetic plugin project'], check=True)
            revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
            self.registry(root, dict(kind='git', url=str(source), revision=revision))
            lock = sync(root)
            self.assertEqual(lock['projects']['sample']['source']['revision'], revision)
            self.assertEqual(set(lock['projects']['sample']['files']), {'plugins.json', 'one.py', 'two.py'})
            snapshot = root / lock['projects']['sample']['directory']
            self.assertFalse((snapshot / 'vendor').exists())
            self.assertFalse((snapshot / 'tests').exists())
            self.assertEqual(load_entry('two', root).VALUE, 2)
            self.registry(root, dict(kind='git', url=str(source), revision='main'))
            with self.assertRaisesRegex(ValueError, 'complete commit'):
                sync(root)

    def test_undeclared_entry_and_path_escape_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = self.setup_project(root)
            path = source / 'plugins.json'; data = json.loads(path.read_text())
            data['plugins'][0]['entry'] = 'tests/test_internal.py'
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'declare'):
                declared(source)
            data['plugins'][0].update(entry='../outside.py', files=['../outside.py'])
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'Invalid exported'):
                declared(source)


if __name__ == '__main__': unittest.main()
