"""Minimal project plugin: return a pinned upstream build-extension manifest."""
import hashlib
import json
from pathlib import Path


def prepare(reference, image, args, output, config):
    """Build into output, never into plugins/ or vendor/.

    reference: authenticated US bytes; image: current bytes after CN/Info stages.
    args: build options; config: pinned decomp module descriptors.
    Add complete source_replacements or classified fragments to the manifest.
    This starter intentionally leaves the ROM unchanged.
    """
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    source = Path(__file__).resolve()
    manifest = {
        'schema': 'build-extension-v1',
        'reference_sha256': hashlib.sha256(reference).hexdigest(),
        'sources': [{'path': str(source),
                     'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}],
        'source_replacements': [],
        'fragments': [],
    }
    path = output / 'extension.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    return path, {'description': 'Template plugin; no ROM changes yet'}
