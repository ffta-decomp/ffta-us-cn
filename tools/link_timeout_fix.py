"""Source-assembled, revision-guarded US serial counter comparison extension."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OFFSET = 0x4D78
ENTRY = 0x4D68
END = 0x4E0E  # Final BX included; the following two alignment bytes are excluded.
FUNCTION_SHA256 = '87140ce84964969c01541c2a593eb5a4b16d796bcc8e59b69ae1fab8fe3d1fd6'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def prepare(reference, image, output_dir, tool_prefix='arm-none-eabi-'):
    if sha(reference[ENTRY:END]) != FUNCTION_SHA256:
        raise ValueError('Serial poll function differs from authenticated US revision')
    if image[ENTRY:END] != reference[ENTRY:END]:
        raise ValueError('Serial poll already modified; refusing overlapping extension')
    if reference[OFFSET:OFFSET + 4] != bytes.fromhex('46 29 05 d9'):
        raise ValueError('Original CMP/BLS identity differs')
    out = Path(output_dir).resolve()
    if out.is_relative_to(ROOT):
        raise ValueError('Link-fix output must be external')
    out.mkdir(parents=True, exist_ok=False)
    source = ROOT / 'engine/link_timeout_fix.s'
    obj, binary = out / 'comparison.o', out / 'comparison.bin'
    subprocess.run([tool_prefix + 'as', '-mcpu=arm7tdmi', '-mthumb',
                    str(source), '-o', str(obj)], check=True)
    subprocess.run([tool_prefix + 'objcopy', '-O', 'binary', '-j', '.text',
                    str(obj), str(binary)], check=True)
    data = binary.read_bytes()
    if data != bytes.fromhex('fe 29'):
        raise ValueError('Assembled comparison is not exactly CMP R1, #0xFE')
    manifest = {
        'schema': 'build-extension-v1', 'reference_sha256': sha(reference),
        'sources': [{'path': str(source), 'sha256': sha(source.read_bytes())},
                    {'path': str(Path(__file__).resolve()),
                     'sha256': sha(Path(__file__).read_bytes())}],
        'fragments': [{'path': str(binary), 'sha256': sha(data), 'kind': 'code',
                       'rom_offset': OFFSET,
                       'reference_sha256': sha(reference[OFFSET:OFFSET + 2])}],
    }
    path = out / 'extension.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    return path, {
        'kind': 'source-assembled Thumb instruction extension',
        'rom_offset': OFFSET, 'cpu_address': '0x08004D78',
        'function_entry': '0x08004D69', 'function_sha256': FUNCTION_SHA256,
        'original_instruction': 'cmp r1, #0x46', 'original_bytes': '4629',
        'replacement_instruction': 'cmp r1, #0xFE', 'replacement_bytes': data.hex(),
        'counter_address': '0x03002B60', 'counter_bits': 8,
        'old_maximum': 70, 'new_maximum': 254,
        'unchanged_branch': 'BLS 0x08004D88',
        'scope': 'Counter threshold only; no emulator GP-mode implementation',
        'source_sha256': sha(source.read_bytes()),
        'recovery_credit_eligible': False,
    }
