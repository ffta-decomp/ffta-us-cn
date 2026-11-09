"""Detect the installed CN patch and stamp its startup bitmap with native glyphs.

Only hashes and layout contracts live here; game pixels stay in private outputs.
"""
import hashlib
import json
from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / 'config/charsets/us-cn-v1.1/character-table.json'
AUTHOR = ROOT / 'author.txt'
BITMAP, BITMAP_BYTES = 0xa6d000, 240 * 160 * 2
STARTUP, STARTUP_BYTES = 0xa7fc00, 0x1b0
ENTRY = bytes.fromhex('2dff29ea')
STARTUP_SHA = 'a81b533e138014f2c390b9cedd3bfe68229d7eba0914839b39c72097cdda6401'
BITMAP_SHA = '3803c4d908d166963db0213bf29bf85fa4613eff341af375f0c4907a96abb3a7'
CAPTION = (4, 139, 144, 20)
PROTECTED_SHA = '27457a41b4844d43fcf2d6e850230f0e066e6646b3a993eddca6d0985da14193'
FONT, WIDTHS = 0x433330, 0x4966b0


def sha(data):
    return hashlib.sha256(data).hexdigest()


def detect(image):
    """Require both the live startup redirect and the supported patch payload."""
    entry = image[0xec:0xf0] == ENTRY
    startup = sha(image[STARTUP:STARTUP + STARTUP_BYTES]) == STARTUP_SHA
    if not entry and not startup:
        return False
    if not entry or not startup or len(image) != 0x1000000:
        raise ValueError('Detected an incomplete or unsupported CN splash patch')
    bitmap = image[BITMAP:BITMAP + BITMAP_BYTES]
    x, y, width, height = CAPTION
    protected = b''.join(bitmap[row * 480:row * 480 + x * 2] +
        bitmap[row * 480 + (x + width) * 2:(row + 1) * 480]
        if y <= row < y + height else bitmap[row * 480:(row + 1) * 480]
        for row in range(160))
    if sha(protected) != PROTECTED_SHA:
        raise ValueError('Detected CN patch but its splash bitmap is modified or unsupported')
    return True


def read_author(path):
    data = Path(path).read_bytes()
    if len(data) > 1024:
        raise ValueError('author.txt exceeds 1024 bytes')
    text = data.decode('utf-8-sig').strip()
    if not text or any(ord(c) < 32 or c in '\u2028\u2029' for c in text):
        raise ValueError('author.txt must contain one nonempty UTF-8 line')
    return text, data


def stamp(image, author_file=AUTHOR, enabled=True):
    if not enabled:
        return bytes(image), dict(applied=False, reason='disabled')
    if not detect(image):
        return bytes(image), dict(applied=False, reason='no-supported-cn-patch')
    text, author_data = read_author(author_file)
    table_data = TABLE.read_bytes()
    rows = json.loads(table_data)['glyphs']
    mapping = {}
    for row in rows:
        if row['unicode'] is not None:
            mapping.setdefault(row['unicode'], row)
    glyphs, width = [], 0
    for char in text:
        if char == ' ':
            glyphs.append((None, 4)); width += 4
            continue
        if char not in mapping:
            raise ValueError('Author character absent from native CN font: ' + char)
        row = mapping[char]
        index, advance = row['index'], row['advance']
        cell = image[FONT + index * 128:FONT + (index + 1) * 128]
        if sha(cell) != row['glyph_sha256'] or image[WIDTHS + index] != advance:
            raise ValueError('Author glyph differs from pinned native font: ' + char)
        if not 1 <= advance <= 16:
            raise ValueError('Invalid author glyph advance')
        glyphs.append((cell, advance)); width += advance
    # Bottom left keeps the group's credits and URL on the right unobstructed.
    # Reserve the full final cell, including the native drop shadow.
    ink_width = width + (16 - glyphs[-1][1] if glyphs[-1][0] else 0)
    if ink_width > 136:
        raise ValueError('Author text is too wide for the splash (maximum 136 pixels)')
    pixels = list(struct.unpack_from('<38400H', image, BITMAP))
    x0, y0, box_width, box_height = CAPTION
    cursor = x0 + 4
    foreground = set()
    for cell, advance in glyphs:
        if cell is not None:
            for y in range(16):
                for x in range(16):
                    shade = (cell[x // 8 * 64 + y * 4 + x % 8 // 2] >> (x % 2 * 4)) & 15
                    if shade:
                        if shade not in (2, 3):
                            raise ValueError('Unsupported native author glyph shade')
                        if shade == 3:
                            foreground.add((cursor + x, y0 + 2 + y))
        cursor += advance
    # A two-pixel white halo follows the letter shapes; no panel or background
    # fill obscures the original artwork. Draw all outlines before foregrounds.
    for x, y in foreground:
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                if dx * dx + dy * dy > 5:
                    continue
                if not (x0 <= x + dx < x0 + box_width and y0 <= y + dy < y0 + box_height):
                    raise ValueError('Author glyph outline exceeds its reserved bounds')
                pixels[(y + dy) * 240 + x + dx] = 0x7fff
    for x, y in foreground:
        pixels[y * 240 + x] = 0
    bitmap = struct.pack('<38400H', *pixels)
    result = bytearray(image)
    result[BITMAP:BITMAP + BITMAP_BYTES] = bitmap
    return bytes(result), dict(applied=True, detected_patch='us-cn-v1.1', text=text,
        author_file_sha256=sha(author_data), glyph_table_sha256=sha(table_data),
        startup_sha256=STARTUP_SHA, bitmap_rom_offset=BITMAP,
        reference_bitmap_sha256=BITMAP_SHA,
        input_bitmap_sha256=sha(image[BITMAP:BITMAP + BITMAP_BYTES]), bitmap_sha256=sha(bitmap),
        style='native-black-text-white-outline', outline_pixels=2,
        bounds=dict(x=x0, y=y0, width=box_width, height=box_height),
        glyph_tokens=[None if c == ' ' else 0x8000 | mapping[c]['index'] for c in text],
        recovery_credit_eligible=False)


def write_preview(image, path):
    """Write a lossless 240x160 RGB PNG of the actual startup DMA pixels."""
    pixels = struct.unpack_from('<38400H', image, BITMAP)
    rgb = bytes(c * 255 // 31 for p in pixels for c in (p & 31, p >> 5 & 31, p >> 10 & 31))
    raw = b''.join(b'\0' + rgb[y * 720:(y + 1) * 720] for y in range(160))
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n' +
        chunk(b'IHDR', struct.pack('>2I5B', 240, 160, 8, 2, 0, 0, 0)) +
        chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))
