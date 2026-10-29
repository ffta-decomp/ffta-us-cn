"""Joint source build using the published, unmodified decomp extension API."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DECOMP = ROOT / 'vendor/fftadecomp'
TOOLKIT = DECOMP
BASE_MODULES = (
    'CoreRegion_0012A084', 'CoreRegion_0012A440', 'CoreRegion_0012A91C',
    'Remaining38_0012B208', 'Remaining38_0012B230',
)
REPLACEMENTS = {
    'CoreRegion_0012A084': 'advance_save_name_editor.c',
    'Remaining38_0012B208': 'start_primary_name_editor.c',
    'Remaining38_0012B230': 'start_secondary_name_editor.c',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pin(path):
    return {'path': str(path.resolve()), 'sha256': sha(path.read_bytes())}


def build(args):
    from verify_vendor import verify
    verify()
    reference = args.retail.read_bytes()
    config = json.loads((DECOMP / 'config/completed-build.json').read_text())
    if len(reference) != config['size'] or sha(reference) != config['sha256']:
        raise ValueError('Wrong authenticated US retail input')
    out = args.output_dir.resolve()
    build_dir = out / 'decomp-build'
    build_dir.mkdir(parents=True, exist_ok=True)
    compiler = build_dir / 'toolchain/agbcc'
    if args.compiler is not None:
        compiler.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(args.compiler, compiler)
    else:
        from bootstrap import bootstrap
        bootstrap(build_dir)
    # Use only the pinned official source/toolkit export. Generated files and
    # compiler outputs stay outside the immutable vendor directory.
    sys.path.insert(0, str(TOOLKIT / 'tools'))
    import build_rom as engine
    from build_extensions import apply_extensions
    engine.ROOT = DECOMP
    engine.BUILD_ROOT = build_dir
    engine.ASSET_JSON_CACHE.footprint_dir = build_dir / 'json-footprints'
    (build_dir / 'generated').mkdir(parents=True, exist_ok=True)
    modules = {module['name']: module for module in config['modules']}
    image = bytearray(reference)
    compiled = []

    def compile_source(module, group):
        work = out / group / module['name']
        work.mkdir(parents=True, exist_ok=False)
        previous = Path.cwd()
        try:
            os.chdir(DECOMP)
            data = engine.compile_module(module, work, config['rom_base'], None, reference=reference)
        finally:
            os.chdir(previous)
        engine.check_linked_function_entries(module, work, config['rom_base'])
        return data

    for name in BASE_MODULES:
        module = modules[name]
        if module['kind'] != 'c' or module.get('match_policy', 'exact') != 'exact':
            raise ValueError('Required decompiled C entry is not exact: ' + name)
        data = compile_source(copy.deepcopy(module), 'decomp-base')
        start = module['offset']
        if data != reference[start:start + module['size']]:
            raise ValueError('Decomp source baseline differs: ' + name)
        image[start:start + len(data)] = data
        compiled.append({'module': name, 'bytes': len(data), 'sha256': sha(data),
                         'source': pin(DECOMP / module['source'])})
    baseline_hash = sha(image)
    if baseline_hash != sha(reference):
        raise ValueError('English source-built compatibility baseline changed')
    extension = None
    extension_report = None
    if args.cjk:
        from migrate_us_cn import compose
        if args.pinyin:
            stage = out / 'cn-module-stage'
            command = [sys.executable, str(ROOT / 'tools/build_native_pinyin.py'),
                       '--retail', str(args.retail), '--pack-dir', str(args.pack_dir),
                       '--glyph-map', str(args.glyph_map), '--map-report', str(args.map_report),
                       '--output-dir', str(stage), '--tool-prefix', args.tool_prefix,
                       '--clang', args.clang, '--source-extensions']
            if args.rime_dictionary:
                command += ['--rime-dictionary', str(args.rime_dictionary)]
            subprocess.run(command, check=True)
            target = (stage / 'ffta-zh-pinyin.gba').read_bytes()
            cn_report = json.loads((stage / 'baseline-report.json').read_text())
            pinyin_report = json.loads((stage / 'build-report.json').read_text())
            (build_dir / 'generated/cjk_name_bindings.h').write_text(
                '#define CJK_NAME_CALLBACK "' + pinyin_report['callback_entry'] + '"\n')
        else:
            target, cn_report = compose(reference, args.pack_dir, out / 'cn-module-stage', args.tool_prefix)
            pinyin_report = None
        fragment_dir = out / 'extension-fragments'
        fragment_dir.mkdir()
        extension = {'schema': 'build-extension-v1', 'reference_sha256': sha(reference),
                     'sources': [pin(ROOT / 'engine/us_cn_hooks.s'),
                                 pin(args.pack_dir / 'pack-manifest.json')],
                     'source_replacements': [], 'fragments': []}

        def fragment(offset, size, kind):
            path = fragment_dir / ('%06d.bin' % len(extension['fragments']))
            data = target[offset:offset + size]
            path.write_bytes(data)
            extension['fragments'].append(dict(pin(path), rom_offset=offset, kind=kind,
                                                reference_sha256=sha(reference[offset:offset + size])))

        for row in cn_report['components']:
            code_kinds = {'readable assembled engine hook', 'resource copy BL redirect',
                          'ARM startup branch', 'LDR R0 literal and epilogue extension BL',
                          'Thumb MOVS immediate'}
            kind = 'code' if row['kind'] in code_kinds else 'resource'
            if row['kind'] == 'typed ROM pointer relocation':
                kind = 'data'
            fragment(row['rom_offset'], row['bytes'], kind)
        if pinyin_report:
            for source in ['native_name_pinyin.c', 'native_name_pinyin_support.s']:
                extension['sources'].append(pin(ROOT / 'engine' / source))
            extension['sources'].append(pin(build_dir / 'generated/cjk_name_bindings.h'))
            for source in (ROOT / 'engine/pinyin').rglob('*'):
                if source.is_file():
                    extension['sources'].append(pin(source))
            for source in [ROOT / 'tools/generate_optional_pinyin.py',
                           args.glyph_map, args.map_report]:
                extension['sources'].append(pin(source))
            payload = pinyin_report['payload']
            fragment(payload['rom_offset'], payload['bytes'], 'code')
            for row in pinyin_report['patches']:
                fragment(row['rom_offset'], row['bytes'], 'code')
            for name, source in REPLACEMENTS.items():
                module = modules[name]
                extension['source_replacements'].append({
                    'module': name, 'source': pin(ROOT / 'engine/extensions' / source),
                    'reference_sha256': sha(reference[module['offset']:module['offset'] + module['size']]),
                    'fill_byte': 0})
        manifest = out / 'extension.json'
        manifest.write_text(json.dumps(extension, indent=2) + '\n')
        image, extension_report = apply_extensions(
            image, reference, config, manifest,
            lambda module: compile_source(module, 'cn-source-extensions'))
        if not args.pinyin and sha(image) != cn_report['target_sha256']:
            raise ValueError('Feature-off CN differs from the exact translated reference')
    link_report = None
    if args.link_fix:
        from link_timeout_fix import prepare
        link_manifest, link_report = prepare(reference, image, out / 'link-timeout-fix', args.tool_prefix)
        before = bytes(image)
        image, link_extension = apply_extensions(image, reference, config, link_manifest)
        if image[:0x4d78] != before[:0x4d78] or image[0x4d7a:] != before[0x4d7a:]:
            raise ValueError('Link comparison extension changed bytes outside its instruction')
        link_report['extension'] = link_extension
    font_report = None
    if args.italic_font:
        from font_plugins import prepare as prepare_font
        font_manifest, font_report = prepare_font(reference, image,
            {'cjk': args.cjk, 'link_fix': args.link_fix, 'info': args.info, 'italic_font': args.italic_font},
            out / 'font-extensions')
        image, font_extension = apply_extensions(image, reference, config, font_manifest)
        font_report['extension'] = font_extension
    args.font_extension_report = font_report
    info_report = None
    if args.info:
        from build_plugin_info import prepare as prepare_info
        if args.cjk:
            font_image = image
        else:
            from migrate_us_cn import compose
            font_image, _ = compose(reference, args.pack_dir, out / 'info-font-stage', args.tool_prefix)
        info_manifest, info_report = prepare_info(
            reference, image, font_image, args, out / 'plugin-info', config)
        image, info_extension = apply_extensions(
            image, reference, config, info_manifest,
            lambda module: compile_source(module, 'info-source-extensions'))
        info_report['extension'] = info_extension
    report = {'schema': 1, 'build_mode': 'joint-decomp-extension',
              'cjk_enabled': args.cjk, 'pinyin_enabled': args.pinyin,
              'link_fix_enabled': args.link_fix, 'link_fix': link_report,
              'info_enabled': args.info, 'plugin_info': info_report,
              'italic_font_enabled': args.italic_font, 'font_extension': font_report,
              'output_bytes': len(image), 'output_sha256': sha(image),
              'english_baseline_sha256': baseline_hash,
              'compiled_decomp_modules': compiled,
              'compiled_decomp_original_bytes': sum(row['bytes'] for row in compiled),
              'extension': extension_report, 'recovery_credit_eligible': False,
              'compiler_sha256': sha(compiler.read_bytes()),
              'vendor_lock_sha256': sha((ROOT / 'vendor/lock.json').read_bytes()),
              'plugin_projects_lock_sha256': sha((ROOT / 'config/plugin-projects.lock.json').read_bytes()),
              'scope': 'Five published naming C entries plus optional CN source/resources. Other original game code remains supplied by the authenticated input; this is not a whole-game decomp claim.'}
    return bytes(image), report
