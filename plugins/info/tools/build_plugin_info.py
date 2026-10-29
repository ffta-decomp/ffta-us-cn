"""Info plugin build entry using the host-v1 native extension services."""
import hashlib
import json
from pathlib import Path
import subprocess

from plugin_info import ROOT, load_pages
PLUGIN_ROOT = Path(__file__).resolve().parents[1]

ORIGIN = 0x08C00000
TITLE_MODULE = 'Registered39_00136084'
FONT_START, FONT_END, WIDTHS = 0x433330, 0x4966B0, 0x4966B0


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pin(path):
    return {'path': str(path.resolve()), 'sha256': sha(path.read_bytes())}


def tiles(pixels, columns=8, rows=5, palette_indices=(0, 6, 4)):
    """OBJ 1D mapping, one 32x32 sprite per chunk; pad the right edge."""
    result = bytearray()
    for row in range(rows):
        for column in range(columns):
            for ty in range(4):
                for tx in range(4):
                    for y in range(8):
                        for x in range(0, 8, 2):
                            sx = column * 32 + tx * 8 + x
                            sy = row * 32 + ty * 8 + y
                            low = pixels[sy * 240 + sx] if sx < 240 and sy < 160 else 0
                            high = pixels[sy * 240 + sx + 1] if sx + 1 < 240 and sy < 160 else 0
                            result.append(palette_indices[low] | (palette_indices[high] << 4))
    return bytes(result)


def title_label(pixels):
    """Use the native title ramp: dark ink, light outline, lower shadow.

    Normal and selected title labels use the same pixel indices and switch
    between OBJ palette banks 1 and 3. A single-color mask loses that styling.
    """
    ink = {(x, y) for y in range(16) for x in range(64) if pixels[y * 240 + x] == 2}
    if not ink:
        raise ValueError('Empty Info entry label')
    outlined = {(x + dx, y + dy) for x, y in ink
                for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                if 0 <= x + dx < 64 and 0 <= y + dy < 16}
    result = bytearray(240 * 160)
    for x, y in outlined:
        if y + 1 < 16:
            result[(y + 1) * 240 + x] = 6
    for x, y in outlined:
        result[y * 240 + x] = 8
    for x, y in ink:
        result[y * 240 + x] = 1
    return result, max(x for x, _ in outlined) + 1


def generate_assets(font_image, args, out, pages):
    mapping = json.loads(args.glyph_map.read_text())
    provenance = json.loads(args.map_report.read_text())
    if provenance['glyph_map_sha256'] != sha(args.glyph_map.read_bytes()) or \
       provenance['native_font_sha256'] != sha(font_image[FONT_START:FONT_END]):
        raise ValueError('Info glyph map provenance does not match the native font')
    required = set('InfoB: Close')
    for page in pages:
        required.update(page['name'] + '\n'.join(page['lines']))
    required -= {' ', '\n'}
    # Native full-glyph Latin/digit ranges, also used by the name editor.
    # Keep these token semantics separate from private Unicode/Hanzi maps.
    latin = {chr(ord('A') + i): 0x80b0 + i for i in range(26)}
    latin.update({chr(ord('a') + i): 0x80ca + i for i in range(26)})
    latin.update({str(i): 0x80a6 + i for i in range(10)})
    latin['.'] = 0x80e4
    latin[':'] = 0x80ee
    mapping = dict(latin, **mapping)
    missing = sorted(required - mapping.keys())
    if missing:
        raise ValueError('Info needs explicit native glyph mappings for: ' + ''.join(missing))
    glyphs = {}
    bindings = {}
    for character in sorted(required):
        token = mapping[character]
        if type(token) is not int or not 0x8000 <= token < 0x8000 + 3175:
            raise ValueError('Info glyph token outside native font')
        index = token & 0x7fff
        cell = font_image[FONT_START + index * 128:FONT_START + (index + 1) * 128]
        advance = font_image[WIDTHS + index]
        if not 1 <= advance <= 16:
            raise ValueError('Invalid native glyph advance')
        glyphs[ord(character)] = (cell, advance)
        bindings[character] = dict(token=hex(token), advance=advance, sha256=sha(cell))
    render_data = out / 'plugin_info_render_data.h'
    glyph_rows = []
    for code, (cell, advance) in sorted(glyphs.items()):
        glyph_rows.append('{%d,%d,{%s}}' % (code, advance, ','.join(map(str, cell))))
    label_glyphs, label_bindings = [], {}
    font_report = getattr(args, 'font_extension_report', None)
    if font_report:
        font_start, widths_start = font_report['font_rom_offset'], font_report['widths_rom_offset']
        if sha(font_image[font_start:widths_start]) != font_report['font_sha256']:
            raise ValueError('Appended font provenance mismatch')
    for character in sorted(set('Info')):
        code = ord(character)
        cell, advance = glyphs[code]
        token = int(bindings[character]['token'], 16)
        if font_report:
            token = font_report['styles']['italic'][character]
            index = token & 0x7fff
            if not 3175 <= index < font_report['glyph_count']:
                raise ValueError('Italic label token must address an appended glyph')
            cell = font_image[font_start + index * 128:font_start + (index + 1) * 128]
            advance = font_image[widths_start + index]
        label_glyphs.append('{%d,%d,{%s}}' % (code, advance, ','.join(map(str, cell))))
        label_bindings[character] = dict(token=hex(token), advance=advance, sha256=sha(cell))
    page_rows = []
    for page in pages:
        # C UTF-8 literals: escape only syntax and control characters, retaining
        # Unicode bytes rather than C universal escapes for surrogate pairs.
        page_rows.append('{%s,%s}' % (json.dumps(page['name'], ensure_ascii=False),
                                     json.dumps('\n'.join(page['lines']), ensure_ascii=False)))
    render_data.write_text('static const struct HostGlyph host_glyphs[] = {' +
        ','.join(glyph_rows) + '};\nstatic const struct HostGlyph host_label_glyphs[] = {' +
        ','.join(label_glyphs) + '};\nstatic const struct PluginInfoPage host_pages[] = {' +
        ','.join(page_rows) + '};\n')
    renderer = out / 'render-info'
    subprocess.run([args.clang, '-O2', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-I', str(PLUGIN_ROOT / 'src'), '-I', str(out),
                    str(PLUGIN_ROOT / 'tools/render_plugin_info.c'),
                    str(PLUGIN_ROOT / 'src/plugin_info_ui.c'), '-o', str(renderer)], check=True)
    layout = json.loads(subprocess.check_output([str(renderer), str(out)], text=True))
    chunks, records = [], []
    page_views = [[] for _ in pages]
    for view in layout['views']:
        pixels_path = out / (view['symbol'] + '.pixels')
        pixels = pixels_path.read_bytes()
        data = tiles(pixels)
        chunks.append((view['symbol'], data))
        page_views[view['page']].append(view['symbol'])
        records.append(dict(plugin=pages[view['page']]['id'], first_line=view['first_line'],
                            sha256=sha(data), bytes=len(data)))
        def native_color(index):
            start = 0x41a160 + index * 2  # Native menu palette zero, default mode.
            value = int.from_bytes(font_image[start:start + 2], 'little')
            return tuple(((value >> shift) & 31) * 255 // 31 for shift in (0, 5, 10))
        rgb = ((0, 0, 0), native_color(6), native_color(4))
        ppm = b'P6\n240 160\n255\n' + bytes(c for pixel in pixels for c in rgb[pixel])
        (out / (view['symbol'] + '.ppm')).write_bytes(ppm)
        pixels_path.unlink()
    label_path = out / 'gPluginInfoLabel.pixels'
    label_pixels, label_width = title_label(label_path.read_bytes())
    chunks.append(('gPluginInfoLabel', tiles(label_pixels, columns=2, rows=1, palette_indices=tuple(range(16)))))
    label_path.unlink()
    renderer.unlink()
    source = []
    for name, data in chunks:
        values = [str(int.from_bytes(data[i:i + 2], 'little')) for i in range(0, len(data), 2)]
        source.append('const unsigned short %s[] = {%s};' % (name, ','.join(values)))
    for number, views in enumerate(page_views):
        source.append('static const unsigned short *const page_%d[] = {%s};' %
                      (number, ','.join(views)))
    source.append('const struct PluginInfoAssetPage gPluginInfoPages[] = {%s};' %
                  ','.join('{page_%d,%d}' % (n, len(views)) for n, views in enumerate(page_views)))
    header = out / 'plugin_info_assets.h'
    header.write_text('#define PLUGIN_INFO_PAGE_COUNT %d\n' % len(pages) +
        '#define PLUGIN_INFO_LABEL_CURSOR_X %d\n' % (154 + label_width + 4) +
        'struct PluginInfoAssetPage { const unsigned short *const *views; unsigned view_count; };\n'
        'extern const struct PluginInfoAssetPage gPluginInfoPages[];\n'
        'extern const unsigned short gPluginInfoLabel[];\n')
    generated = out / 'plugin_info_assets.c'
    generated.write_text('#include "plugin_info_assets.h"\n' + '\n'.join(source) + '\n')
    return generated, header, {'glyphs': bindings, 'views': records,
        'title_label': {'palette_banks': [1, 3], 'ink_index': 1,
                        'outline_index': 8, 'shadow_index': 6,
                        'width': label_width, 'cursor_x': 154 + label_width + 4,
                        'style': 'italic' if font_report else 'default', 'glyphs': label_bindings}}


def prepare(reference, image, font_image, args, out, config):
    out = Path(out).resolve()
    if out.is_relative_to(ROOT):
        raise ValueError('Info build artifacts must be external')
    out.mkdir(parents=True, exist_ok=False)
    pages = load_pages({'cjk': args.cjk, 'link_fix': args.link_fix,
                        'info': getattr(args, 'info', False)})
    if not pages:
        raise ValueError('Info has no enabled plugins')
    generated, header, report = generate_assets(font_image, args, out, pages)
    objects = []
    for source in [PLUGIN_ROOT / 'src/plugin_info_title.c', generated]:
        obj = out / (source.stem + '.o')
        subprocess.run([args.clang, '--target=arm-none-eabi', '-mcpu=arm7tdmi',
                        '-mthumb', '-Os', '-std=c11', '-ffreestanding', '-fno-builtin',
                        '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
                        '-Wall', '-Wextra', '-Werror', '-I', str(out), '-c', str(source),
                        '-o', str(obj)], check=True)
        objects.append(obj)
    linker = out / 'info.ld'
    linker.write_text('SECTIONS { . = 0x08c00000; .text : { *(.text*) *(.rodata*) } '
        '.data : { *(.data*) } .bss : { *(.bss*) *(COMMON) } '
        '/DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) } }\n'
        'ASSERT(SIZEOF(.data) == 0 && SIZEOF(.bss) == 0, "Unexpected static RAM")\n')
    elf, binary = out / 'info.elf', out / 'info.bin'
    subprocess.run([args.tool_prefix + 'ld', '-T', str(linker), *map(str, objects), '-o', str(elf)], check=True)
    subprocess.run([args.tool_prefix + 'objcopy', '-O', 'binary', '-j', '.text',
                    str(elf), str(binary)], check=True)
    symbols = subprocess.check_output([args.tool_prefix + 'nm', '-n', str(elf)], text=True)
    callback = next(int(row.split()[0], 16) | 1 for row in symbols.splitlines()
                    if row.endswith(' PluginInfoTitleUpdate'))
    payload = binary.read_bytes()
    offset = ORIGIN - 0x08000000
    if not payload or offset + len(payload) > len(image) or \
       image[offset:offset + len(payload)] != b'\xff' * len(payload) or \
       reference[offset:offset + len(payload)] != b'\xff' * len(payload):
        raise ValueError('Info payload requires verified erased ROM space')
    module = next(m for m in config['modules'] if m['name'] == TITLE_MODULE)
    if image[module['offset']:module['offset'] + module['size']] != \
       reference[module['offset']:module['offset'] + module['size']]:
        raise ValueError('Title module already modified')
    bindings = args.output_dir / 'decomp-build/generated/plugin_info_bindings.h'
    bindings.write_text('#define PLUGIN_INFO_CALLBACK 0x%08xu\n' % callback)
    sources = [ROOT / 'plugins.json', ROOT / 'tools/plugin_info.py', Path(__file__),
               PLUGIN_ROOT / 'src/plugin_info_ui.c', PLUGIN_ROOT / 'src/plugin_info_ui.h',
               PLUGIN_ROOT / 'src/plugin_info_title.c', PLUGIN_ROOT / 'tools/render_plugin_info.c', args.glyph_map, args.map_report,
               generated, header, bindings]
    replacement = PLUGIN_ROOT / 'src/advance_title_with_info.c'
    manifest = dict(schema='build-extension-v1', reference_sha256=sha(reference),
        sources=[pin(path) for path in sources],
        source_replacements=[dict(module=TITLE_MODULE, source=pin(replacement),
            reference_sha256=sha(reference[module['offset']:module['offset'] + module['size']]),
            fill_byte=0)],
        fragments=[dict(pin(binary), kind='code', rom_offset=offset,
                        reference_sha256=sha(reference[offset:offset + len(payload)]))])
    path = out / 'extension.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    report.update(pages=pages, callback_entry=hex(callback), payload_bytes=len(payload),
                  plugins_sha256=sha((ROOT / 'plugins.json').read_bytes()),
                  recovery_credit_eligible=False)
    return path, report
