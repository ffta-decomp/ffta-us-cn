"""Add a Sanyo Flash ID alias without changing the native 64 KiB save layout."""
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RETAIL_SHA = '43fc8204c6dceee58828aebc7af0c72eb807e99f35ad641c8bb0a4fa8b6edc19'
BASE = 0x08000000
LOOKUP = 0x141DC4
ORIGINAL_TABLE = 0x36CE38
PANASONIC = 0x36CF64
ARENA = 0xF30000
SANYO_ID = 0x1362


def sha(data):
    return hashlib.sha256(data).hexdigest()


def prepare(reference, image, output_dir):
    if sha(reference) != RETAIL_SHA or len(image) != len(reference):
        raise ValueError('Unexpected US revision for VBA-M Flash compatibility')
    for start, end in ((0x141D9C, 0x141E28), (ORIGINAL_TABLE, ORIGINAL_TABLE + 16),
                       (PANASONIC, PANASONIC + 44)):
        if image[start:end] != reference[start:end]:
            raise ValueError('Native Flash lookup or descriptor already modified')
    if struct.unpack_from('<I', image, LOOKUP)[0] != BASE + ORIGINAL_TABLE:
        raise ValueError('Unexpected native Flash lookup pointer')

    # Native lookup stops at the zero-ID fallback descriptor. Preserve all
    # original entries and insert an ID-specific descriptor before that fallback.
    original = image[ORIGINAL_TABLE:ORIGINAL_TABLE + 16]
    alias = bytearray(image[PANASONIC:PANASONIC + 44])
    struct.pack_into('<H', alias, 40, SANYO_ID)
    table = original[:12] + struct.pack('<I', BASE + ARENA + 20) + original[12:]
    payload = table + alias
    if any(v[ARENA:ARENA + len(payload)] != b'\xff' * len(payload) for v in (image, reference)):
        raise ValueError('VBA-M Flash descriptor reservation is occupied')

    out = Path(output_dir).resolve()
    if out.is_relative_to(ROOT):
        raise ValueError('VBA-M Flash build output must be outside the source tree')
    out.mkdir(parents=True, exist_ok=False)
    fragments = []
    for name, at, data in (
        ('flash-table.bin', ARENA, payload),
        ('flash-table-pointer.bin', LOOKUP, struct.pack('<I', BASE + ARENA)),
    ):
        dest = out / name
        dest.write_bytes(data)
        fragments.append(dict(path=str(dest), kind='data', rom_offset=at,
                              sha256=sha(data), reference_sha256=sha(reference[at:at + len(data)])))

    source = Path(__file__).resolve()
    path = out / 'extension.json'
    path.write_text(json.dumps(dict(schema='build-extension-v1', reference_sha256=RETAIL_SHA,
                                    sources=[dict(path=str(source), sha256=sha(source.read_bytes()))],
                                    fragments=fragments), indent=2) + '\n')
    return path, dict(flash_id='0x1362', save_geometry_bytes=65536,
                      descriptor_offset=ARENA + 20, lookup_pointer_offset=LOOKUP,
                      scope='Sanyo Flash ID alias for 64 KiB native operations; no SRAM support')
