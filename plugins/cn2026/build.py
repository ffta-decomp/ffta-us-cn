"""Apply pinned CN2026 translation revisions and private image enhancements."""
import hashlib
import json
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def revision_rows(image, args, plan):
    """Mirror formerly blank glyph additions into the active appended font."""
    if plan.get('schema') != 'ffta-cn2026-translation-revisions-v1':
        raise ValueError('Unsupported CN2026 translation revision plan')
    rows = list(plan['fragments'])
    native = plan['native_font_offset']
    site = plan['font_pointer_offset']
    active = int.from_bytes(image[site:site + 4], 'little') - 0x08000000
    font_report = getattr(args, 'font_extension_report', None)
    count = 3175
    if active != native:
        if not font_report or active != font_report['font_rom_offset']:
            raise ValueError('Unrecognized active font for translation revisions')
        count = font_report['glyph_count']
        if sha(image[active:active + count * 128]) != font_report['font_sha256']:
            raise ValueError('Active font changed before translation revisions')
        for row in plan['fragments']:
            if row['category'] != 'glyph':
                continue
            start, end = row['rom_offset'], row['rom_offset'] + row['bytes']
            if not native <= start < end <= native + 3175 * 128:
                raise ValueError('Translation glyph span outside the native font')
            first, last = (start - native) // 128, (end - native - 1) // 128
            if any(i not in plan['glyph_slots'] for i in range(first, last + 1)):
                raise ValueError('Translation glyph span touches undeclared slots')
            rows.append(dict(row, rom_offset=active + start - native, mirrored=True))
    if not 0 <= active < active + count * 128 <= len(image):
        raise ValueError('Active translation font outside ROM')
    return rows, active, count


def prepare(reference, image, args, output, config):
    if not args.cjk or not getattr(args, 'cn2026', False):
        raise ValueError('cn2026 requires the cn2025 translation base')
    supplied = getattr(args, 'image_enhancement_pack', None)
    if supplied is None:
        raise ValueError('cn2026 requires --image-enhancement-pack')
    pack = Path(supplied).resolve()
    plan_path = PLUGIN / 'images.json'
    plan = json.loads(plan_path.read_text())
    if plan.get('schema') != 'ffta-cn2026-image-pack-v1' or plan.get('base_translation') != 'cn2025':
        raise ValueError('Unsupported cn2026 image plan')
    if len(image) != plan['rom_bytes'] or len(reference) != len(image):
        raise ValueError('Unexpected cn2026 ROM size')
    # The checked-in plan owns all offsets and hashes. No external code, paths,
    # replacement declarations or optional extra fragments are imported.
    sources = [Path(__file__).resolve(), plan_path]
    rows = list(plan['fragments'])
    revision = None
    if plan.get('translation_revisions'):
        name = plan['translation_revisions']
        if Path(name).name != name:
            raise ValueError('Revision plan must be a local filename')
        revision_path = PLUGIN / name
        revision = json.loads(revision_path.read_text())
        extra, active_font, glyph_count = revision_rows(image, args, revision)
        rows.extend(extra)
        sources.append(revision_path)
    fragments, occupied = [], []
    for row in rows:
        name = Path(row['file'])
        if name.name != row['file'] or name.is_absolute():
            raise ValueError('Image fragment must be a flat relative filename')
        source = pack / name
        if source.is_symlink() or not source.is_file():
            raise ValueError('Missing or symlinked cn2026 fragment: ' + name.name)
        at, size = row['rom_offset'], row['bytes']
        if (type(at) is not int or type(size) is not int or size <= 0 or
                not 0 <= at < at + size <= len(image) or row['kind'] not in ('resource', 'data')):
            raise ValueError('Invalid image-only fragment span')
        if any(at < end and start < at + size for start, end in occupied):
            raise ValueError('Overlapping cn2026 image fragments')
        occupied.append((at, at + size))
        if sha(image[at:at + size]) != row['preimage_sha256']:
            raise ValueError('cn2026 resource preimage differs at ' + hex(at))
        data = source.read_bytes()
        if len(data) != size or sha(data) != row['sha256']:
            raise ValueError('cn2026 fragment identity differs: ' + name.name)
        fragments.append((row, data))
    layout_rows = []
    if plan.get('layout_repairs'):
        if plan['layout_repairs'] != 'save-layout.json':
            raise ValueError('Unsupported CN2026 layout repair')
        layout_path = PLUGIN / 'save-layout.json'
        layout = json.loads(layout_path.read_text())
        expected = {0x1389aa: '0322', 0x1389b6: '0522', 0x1389be: '0534',
                    0x1389c4: '0322', 0x1389d0: '0522'}
        if (layout['schema'] != 'ffta-cn2026-save-caption-layout-v1' or
                {r['offset']: r['expected_hex'] for r in layout['patches']} != expected):
            raise ValueError('Unexpected save-caption instruction set')
        replacements = {0x1389aa: '0022', 0x1389b6: '0822', 0x1389be: '0834',
                        0x1389c4: '0022', 0x1389d0: '0822'}
        if {r['offset']: r['replacement_hex'] for r in layout['patches']} != replacements:
            raise ValueError('Unexpected save-caption replacement instructions')
        for change in layout['patches']:
            at = change['offset']
            before, data = bytes.fromhex(change['expected_hex']), bytes.fromhex(change['replacement_hex'])
            if len(data) != 2 or image[at:at+2] != before or reference[at:at+2] != before:
                raise ValueError('Save-caption instruction preimage differs')
            if any(at < end and start < at+2 for start, end in occupied):
                raise ValueError('Save-caption instruction overlaps an image fragment')
            row = dict(file=f'layout-{at:08x}.bin',rom_offset=at,bytes=2,kind='code')
            fragments.append((row,data))
            layout_rows.append(at)
        sources.append(layout_path)
    # Validate every input before creating output or returning any writes.
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = dict(schema='build-extension-v1', reference_sha256=sha(reference),
                    sources=[dict(path=str(p), sha256=sha(p.read_bytes())) for p in sources],
                    source_replacements=[], fragments=[])
    for row, data in fragments:
        target = output / row['file']
        target.write_bytes(data)
        at, size = row['rom_offset'], row['bytes']
        manifest['fragments'].append(dict(path=str(target.resolve()), sha256=sha(data),
            rom_offset=at, kind=row['kind'], reference_sha256=sha(reference[at:at + size])))
    path = output / 'extension.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    report = dict(version=plan['version'], base_plugin='cn2025',
        plan_sha256=sha(plan_path.read_bytes()), image_only=revision is None,
        fragments=len(fragments), save_caption_layout_sites=layout_rows, included=plan['included'], deferred=plan['deferred'],
        validation_limits=plan['validation_limits'])
    if revision:
        final_font = bytearray(image[active_font:active_font + glyph_count * 128])
        for row, data in fragments:
            at = row['rom_offset']
            if active_font <= at and at + len(data) <= active_font + len(final_font):
                final_font[at - active_font:at - active_font + len(data)] = data
        report['translation_revisions'] = dict(version=revision['version'], author=revision['author'],
            plan_sha256=sha(revision_path.read_bytes()), source_segments=revision['source_segment_count'],
            skipped_residue=revision['skipped_residue_segments'], glyph_slots=revision['glyph_slots'],
            mirrored_font_fragments=sum(bool(r.get('mirrored')) for r, _ in fragments),
            active_font_rom_offset=active_font, final_active_font_sha256=sha(final_font),
            relocation=revision['relocation'], validation=revision['validation'])
    return path, report
