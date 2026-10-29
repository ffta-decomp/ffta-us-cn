"""Import only the files declared by a plugin project's plugins.json.

A project can export multiple plugins. Its own vendor/tests/development files
are private to that project unless explicitly declared. No dependency graph is
resolved by the host. Builds are offline; Git fetching is an explicit sync step.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
REGISTRY, LOCK = Path('config/plugin-projects.json'), Path('config/plugin-projects.lock.json')
ID = re.compile(r'[a-z][a-z0-9_-]*\Z')
FORBIDDEN = {'.gba', '.rom', '.bin', '.ttf', '.otf', '.bdf', '.ppm', '.png', '.sav', '.state', '.ips', '.bps'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def tree_hash(files):
    return sha(json.dumps(files, sort_keys=True, separators=(',', ':')).encode())


def declared(directory):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / 'plugins.json').read_text())
    if manifest.get('schema') != 1 or not isinstance(manifest.get('plugins'), list):
        raise ValueError('Unsupported plugin project plugins.json')
    exports, names = {}, {'plugins.json'}
    for plugin in manifest['plugins']:
        identifier = plugin['id']
        if not ID.fullmatch(identifier) or identifier in exports:
            raise ValueError('Invalid/duplicate exported plugin ID')
        paths = plugin.get('files')
        if not isinstance(paths, list) or not paths or plugin.get('entry') not in paths or \
           not plugin['entry'].endswith('.py'):
            raise ValueError('Each plugin must declare its files and Python entry')
        exports[identifier] = plugin['entry']
        names.update(paths)
    inventory = {}
    for name in sorted(names):
        relative = Path(name)
        path = directory / relative
        if relative.is_absolute() or any(p in ('..', '.git', '__pycache__') for p in relative.parts) or path.is_symlink() or \
           not path.resolve().is_relative_to(directory) or not path.is_file():
            raise ValueError('Invalid exported plugin file: ' + name)
        if path.suffix.lower() in FORBIDDEN:
            raise ValueError('Private resource cannot be exported as plugin source: ' + name)
        inventory[relative.as_posix()] = sha(path.read_bytes())
    return exports, inventory


def snapshot_matches(directory, inventory):
    actual = {p.relative_to(directory).as_posix(): sha(p.read_bytes())
              for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    return actual == inventory and all(not p.is_symlink() for p in directory.rglob('*'))


def install(root, identifier, source, inventory):
    relative = Path('vendor/plugins') / identifier / tree_hash(inventory)
    destination = root / relative
    if destination.exists():
        if not snapshot_matches(destination, inventory):
            raise ValueError('Modified plugin snapshot; never edit vendor/plugins')
        return relative.as_posix()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='plugin-stage-', dir=destination.parent) as temporary:
        stage = Path(temporary) / 'snapshot'; stage.mkdir()
        for name in inventory:
            target = stage / name; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((source / name).read_bytes())
        if not snapshot_matches(stage, inventory):
            raise ValueError('Plugin source changed during import')
        stage.rename(destination)
    return relative.as_posix()


def sync(root=ROOT):
    root = Path(root).resolve()
    registry = json.loads((root / REGISTRY).read_text())
    if registry.get('schema') != 1:
        raise ValueError('Unsupported plugin registry')
    records = {}
    with tempfile.TemporaryDirectory(prefix='ffta-plugin-sync-') as temporary:
        for project in registry['projects']:
            identifier, source = project['id'], project['source']
            if not ID.fullmatch(identifier) or identifier in records:
                raise ValueError('Invalid/duplicate plugin project ID')
            if source['kind'] == 'builtin':
                directory = (root / source['path']).resolve()
                if not directory.is_relative_to(root):
                    raise ValueError('Builtin plugin project must be inside the template')
            elif source['kind'] == 'git':
                revision = source['revision']
                if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', revision):
                    raise ValueError('Git plugins require a complete commit ID')
                directory = Path(temporary) / identifier
                subprocess.run(['git', 'init', '-q', str(directory)], check=True, capture_output=True)
                subprocess.run(['git', '-C', str(directory), 'fetch', '-q', '--depth=1', '--', source['url'], revision],
                               check=True, capture_output=True)
                subprocess.run(['git', '-C', str(directory), 'checkout', '-q', '--detach', 'FETCH_HEAD'],
                               check=True, capture_output=True)
                if subprocess.check_output(['git', '-C', str(directory), 'rev-parse', 'HEAD'], text=True).strip() != revision:
                    raise ValueError('Fetched plugin commit differs')
            else:
                raise ValueError('Plugin source must be builtin or git')
            exports, inventory = declared(directory)
            records[identifier] = dict(source=source, directory=(source['path'] if source['kind'] == 'builtin' else
                                                  install(root, identifier, directory, inventory)),
                                       files=inventory, tree_sha256=tree_hash(inventory), plugins=exports)
    lock = dict(schema=1, registry_sha256=sha((root / REGISTRY).read_bytes()), projects=records)
    (root / LOCK).write_text(json.dumps(lock, indent=2) + '\n')
    return lock


def locked(root=ROOT):
    root = Path(root).resolve()
    lock = json.loads((root / LOCK).read_text())
    if lock.get('schema') != 1 or lock['registry_sha256'] != sha((root / REGISTRY).read_bytes()):
        raise ValueError('Plugin registry changed; run tools/plugin_projects.py sync')
    for identifier, record in lock['projects'].items():
        source = record['source']
        expected = (Path(source['path']) if source['kind'] == 'builtin' else
                    Path('vendor/plugins') / identifier / record['tree_sha256'])
        if not ID.fullmatch(identifier) or Path(record['directory']) != expected or \
           tree_hash(record['files']) != record['tree_sha256']:
            raise ValueError('Invalid plugin source lock')
        directory = (root / expected).resolve()
        if not directory.is_relative_to(root):
            raise ValueError('Plugin project must be inside the template')
        if source['kind'] == 'builtin':
            if declared(directory) != (record['plugins'], record['files']):
                raise ValueError('Builtin plugin changed; run tools/plugin_projects.py sync')
        elif source['kind'] != 'git' or not snapshot_matches(directory, record['files']):
            raise ValueError('Plugin snapshot missing/modified; run tools/plugin_projects.py sync')
    return lock


def load_entry(identifier, root=ROOT):
    root = Path(root).resolve()
    lock = locked(root)
    matches = [(project, record) for project, record in lock['projects'].items() if identifier in record['plugins']]
    if len(matches) != 1:
        raise ValueError('Plugin must have exactly one declared source: ' + identifier)
    project, record = matches[0]
    name = '_ffta_plugin_' + sha(str(root).encode())[:12] + '_' + project + '_' + identifier + '_' + record['tree_sha256']
    if name not in sys.modules:
        path = root / record['directory'] / record['plugins'][identifier]
        spec = importlib.util.spec_from_file_location(name, path,
                    submodule_search_locations=[str(path.parent)])
        module = importlib.util.module_from_spec(spec)
        module.PLUGIN_SOURCE_ROOT = root / record['directory']
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            del sys.modules[name]; raise
    return sys.modules[name]


def describe(project, identifier, root=ROOT):
    root = Path(root).resolve()
    record = locked(root)['projects'][project]
    if identifier not in record['plugins']:
        raise ValueError('Plugin is not exported by the selected project: ' + identifier)
    data = json.loads((root / record['directory'] / 'plugins.json').read_text())
    return next(dict(plugin) for plugin in data['plugins'] if plugin['id'] == identifier)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['sync', 'verify'])
    args = parser.parse_args()
    result = sync() if args.command == 'sync' else locked()
    print(json.dumps(dict(projects=list(result['projects']),
                          plugins=[p for r in result['projects'].values() for p in r['plugins']])))


if __name__ == '__main__': main()
