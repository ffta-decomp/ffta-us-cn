"""Validate the public plugin catalogue and select pages for a build.

Only display metadata belongs here. No game text, glyphs, or private resource
paths are discovered or read. Explicit newlines are preserved. The UI wraps each paragraph to the content
width without interpreting ordinary spaces as line breaks.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEATURES = frozenset({'cjk', 'link_fix', 'info', 'italic_font'})


def load_catalogue(path=None):
    path = ROOT / 'plugins.json' if path is None else Path(path)
    catalogue = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(catalogue, dict) or catalogue.get('schema') != 1:
        raise ValueError('Unsupported plugins.json schema')
    plugins = catalogue.get('plugins')
    if not isinstance(plugins, list):
        raise ValueError('plugins must be an array')
    expanded = []
    for plugin in plugins:
        if isinstance(plugin, dict) and 'project' in plugin:
            from plugin_projects import describe
            declaration = describe(plugin['project'], plugin['id'])
            declaration.update(plugin)  # Explicit host settings override defaults.
            plugin = declaration
        expanded.append(plugin)
    return expanded


def load_pages(features, path=None):
    plugins = load_catalogue(path)
    seen = set()
    pages = []
    for plugin in plugins:
        if not isinstance(plugin, dict):
            raise ValueError('Plugin must be an object')
        for field in ('id', 'feature', 'name', 'content'):
            if not isinstance(plugin.get(field), str) or not plugin[field].strip():
                raise ValueError('Plugin requires nonempty ' + field)
        identifier = plugin['id']
        if identifier in seen:
            raise ValueError('Duplicate plugin id: ' + identifier)
        seen.add(identifier)
        if plugin['feature'] not in FEATURES:
            raise ValueError('Unknown plugin feature: ' + plugin['feature'])
        for field in ('name', 'content'):
            if any(ord(c) < 32 and c != '\n' for c in plugin[field]):
                raise ValueError('Unsupported control character in ' + field)
            if any(0xd800 <= ord(c) <= 0xdfff for c in plugin[field]):
                raise ValueError('Invalid Unicode scalar in ' + field)
        if '\n' in plugin['name']:
            raise ValueError('Plugin names must fit one row')
        if features.get(plugin['feature'], False):
            pages.append({'id': identifier, 'name': plugin['name'],
                          'lines': plugin['content'].split('\n')})
    if len(pages) > 4:
        raise ValueError('Info sidebar supports at most four plugins')
    return pages
