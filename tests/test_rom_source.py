from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import rom_source


class RomSourceTests(unittest.TestCase):
    def test_one_url_supports_https_and_ssh_without_workflow_variables(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'rom-source.txt'
            self.assertIsNone(rom_source.load(path))
            for url in ('https://github.com/owner/ffta-roms.git', 'git@github.com:owner/ffta-roms.git'):
                path.write_text(url + '\n')
                self.assertEqual(rom_source.load(path), dict(url=url, repository='owner/ffta-roms'))
            for invalid in ('https://token@github.com/owner/repo.git', 'file:///private/data',
                            'https://github.com/owner/repo.git\nsecond-line', ''):
                path.write_text(invalid)
                with self.assertRaisesRegex(ValueError, 'one GitHub'):
                    rom_source.load(path)

    def test_clone_is_external_and_preserves_existing_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = root / 'source'; source.mkdir()
            config = source / 'rom-source.txt'
            config.write_text('https://github.com/owner/ffta-roms.git\n')
            with self.assertRaisesRegex(ValueError, 'outside'):
                rom_source.checkout(source / 'private', config)
            existing = root / 'existing'; existing.mkdir()
            with self.assertRaisesRegex(ValueError, 'never overwritten'):
                rom_source.checkout(existing, config)
            with patch.object(rom_source.subprocess, 'run') as run:
                rom_source.checkout(root / 'inputs', config)
                self.assertEqual(run.call_args.args[0][-2:],
                                 ['https://github.com/owner/ffta-roms.git', str((root / 'inputs').resolve())])

    def test_missing_config_disables_manual_template_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); output = root / 'output'
            subprocess.run([sys.executable, str(rom_source.ROOT / 'tools/rom_source.py'),
                            '--config', str(root / 'rom-source.txt'), '--github-output', str(output)], check=True)
            self.assertEqual(output.read_text(), 'configured=false\n')
            (root / 'rom-source.txt').write_text('https://github.com/owner/ffta-roms.git\n')
            subprocess.run([sys.executable, str(rom_source.ROOT / 'tools/rom_source.py'),
                            '--config', str(root / 'rom-source.txt'), '--github-output', str(output)], check=True)
            self.assertTrue(output.read_text().endswith('configured=true\nrepository=owner/ffta-roms\n'))


if __name__ == '__main__':
    unittest.main()
