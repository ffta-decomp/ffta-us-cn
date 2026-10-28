#!/usr/bin/env python3
"""Extract a hash-pinned Bear translation through the external upstream parser.

Unlike the independent format adapter, this bridge imports upstream GPL-3.0
modules from the caller-supplied checkout. Original ROM bytes remain unchanged;
the upstream CN parser applies three documented repair operations in memory.
"""
import argparse
import copy
import json
from pathlib import Path
import struct
import subprocess
import sys

import decomp_formats  # Register the external, read-only format library.
from convert_ffta_us_cn import ROOT, UPSTREAM_REVISION, sha, write_json
from font_codec import decode_atlas, encode_atlas
from scene_text_codec import RETAIL_SHA256

BEAR_REVISIONS = {
    "672dca7222a0e2b1f7b759bfb9e453fb03069ebe4250cc0293e741ff3de6427e": "small-fixed",
    "aee65df70410f9c72c2e9b7a5ac9206b826f8559050c94018907be00ef8c4574": "large",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--retail-rom", required=True, type=Path)
    parser.add_argument("--upstream", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    for path in (args.rom, args.retail_rom, args.upstream, args.output_dir):
        if path.resolve().is_relative_to(ROOT):
            raise ValueError("External inputs and output required")
    raw = args.rom.read_bytes()
    source_hash = sha(raw)
    if source_hash not in BEAR_REVISIONS or sha(args.retail_rom.read_bytes()) != RETAIL_SHA256:
        raise ValueError("Unreviewed source or retail ROM revision")
    revision = subprocess.check_output(["git", "-C", str(args.upstream), "rev-parse", "HEAD"], text=True).strip()
    if revision != UPSTREAM_REVISION or subprocess.check_output([
            "git", "-C", str(args.upstream), "status", "--porcelain", "--untracked-files=no"]):
        raise ValueError("Upstream must be the clean pinned revision")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError("Use a clean output directory")
    sys.path.insert(0, str(args.upstream))
    from ffta_modifier import CONF, c_ffta_modifier
    modifier = c_ffta_modifier(copy.deepcopy(CONF))
    modifier.srom, modifier.chst = {}, {}
    for name, path, kind, charset in (
            ("base", args.retail_rom, "us", "charset_us.json"),
            ("text", args.rom, "cn", "charset_cn.json")):
        modifier.srom[name], modifier.chst[name] = modifier.load_rom({
            "path": str(path), "type": kind, "charset": str(args.upstream / charset)})
    # Only parse and align. Never call load(), export() or repack(), which can
    # update upstream work files or generate a patched ROM.
    pairs, uncovered = modifier.parse_texts(True, True)
    font_offset = struct.unpack_from("<I", raw, 0x133f4)[0] - 0x08000000
    glyph_count = 0xc66
    font = raw[font_offset:font_offset + glyph_count * 128]
    if font_offset < 0 or len(font) != glyph_count * 128:
        raise ValueError("Source font span is invalid")
    atlas = decode_atlas(font, glyph_count, 64)
    if encode_atlas(atlas, glyph_count, 64) != font:
        raise ValueError("Source font round trip failed")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "base-pairs.json", pairs)
    write_json(args.output_dir / "uncovered.json", uncovered)
    (args.output_dir / "font-4bpp.bin").write_bytes(font)
    (args.output_dir / "font-atlas.pgm").write_bytes(atlas)
    for source, destination in (("charset_cn.json", "source-charset.json"),
                                ("LICENSE", "UPSTREAM-LICENSE.txt")):
        (args.output_dir / destination).write_bytes((args.upstream / source).read_bytes())
    report = {"reference_sha256": RETAIL_SHA256, "source_rom_sha256": source_hash,
              "source_variant": BEAR_REVISIONS[source_hash], "source_size": len(raw),
              "upstream_revision": revision,
              "parser_repairs": {"0x48cd3f": "set 0x25", "0x9761eb": "shft:50:1", "0x987bdf": "shft:8:-2"},
              "source_file_modified": False, "pairs": sum(map(len, pairs.values())),
              "uncovered": sum(map(len, uncovered.values())),
              "font_offset": font_offset, "glyph_count": glyph_count,
              "file_sha256": {p.name: sha(p.read_bytes()) for p in sorted(args.output_dir.iterdir())},
              "compatibility": "parser acceptance and retail-source alignment only; no runtime proof"}
    write_json(args.output_dir / "report.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
