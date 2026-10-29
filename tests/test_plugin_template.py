"""Exercise the documented fork/add/declaration/build path with synthetic bytes."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'vendor/fftadecomp/tools'))
import joint_build
import plugin_info
from plugin_projects import sync


class PluginTemplateTests(unittest.TestCase):
    def test_added_plugin_is_registered_and_applied_without_host_edits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'config').mkdir()
            (root / 'plugins/my_plugin').mkdir(parents=True)
            (root / 'plugins.json').write_text(json.dumps(dict(schema=1, plugins=[])))
            (root / 'config/plugin-projects.json').write_text(json.dumps(dict(schema=1, projects=[
                dict(id='builtin', source=dict(kind='builtin', path='plugins'))])))
            declaration = json.loads((ROOT / 'examples/plugin-template/declaration.json').read_text())
            starter = (ROOT / 'examples/plugin-template/build.py').read_text()
            # Turn the unchanged starter into a tiny synthetic resource extension.
            starter = starter.replace("'fragments': [],", """'fragments': [{
                'path': str(output / 'data.bin'),
                'sha256': hashlib.sha256(b'X').hexdigest(),
                'rom_offset': 2, 'kind': 'data',
                'reference_sha256': hashlib.sha256(reference[2:3]).hexdigest(),
            }],""")
            starter = starter.replace("path = output / 'extension.json'",
                                      "(output / 'data.bin').write_bytes(b'X')\n    path = output / 'extension.json'")
            (root / 'plugins/my_plugin/build.py').write_text(starter)
            manifest = root / 'plugins/plugins.json'
            manifest.write_text(json.dumps(dict(schema=1, plugins=[declaration])))
            sync(root)
            args = SimpleNamespace(cjk=False, link_fix=False, info=False, italic_font=False)
            with patch.object(plugin_info, 'ROOT', root), patch.object(joint_build, 'ROOT', root):
                self.assertEqual(plugin_info.load_pages({})[0]['id'], 'my_plugin')
                image, reports = joint_build.apply_project_plugins(
                    b'1234', b'1234', args, root / 'out', {'modules': []}, None)
                self.assertEqual(image, b'12X4')
                self.assertEqual(reports[0]['id'], 'my_plugin')
                declaration['enabled'] = False
                manifest.write_text(json.dumps(dict(schema=1, plugins=[declaration])))
                sync(root)
                self.assertEqual(plugin_info.load_pages({}), [])
                image, reports = joint_build.apply_project_plugins(
                    b'1234', b'1234', args, root / 'disabled', {'modules': []}, None)
                self.assertEqual(image, b'1234')
                self.assertEqual(reports, [])
            self.assertFalse((root / 'vendor').exists())


if __name__ == '__main__':
    unittest.main()
