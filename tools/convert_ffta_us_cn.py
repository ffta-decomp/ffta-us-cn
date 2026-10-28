#!/usr/bin/env python3
"""Convert an external ffta_us_cn checkout into optional localization assets.

No upstream Python is executed and no ROM is patched. Output uses the existing
scene_text_codec token schema and font_codec tile layout, with explicit binding
and missing-glyph gates for a later localization linker.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

import decomp_formats  # Register the external, read-only format library.
from extract_resources import decode_word
from font_codec import decode_atlas, encode_atlas
from scene_text_codec import PARAMETER_BYTES, RETAIL_SHA256, encode_tokens

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_REVISION = "cd32ebce88bb26cae030115d5538c1d01a0772f3"
SOURCE_FILES = ("trans_txt.json", "trans_fix_txt.json", "charset_us.json",
                "charset_cn.json", "LICENSE", "ffta_font_generator.py",
                "font/BoutiqueBitmap9x9_1.7.ttf")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def controls(value):
    """Interpret upstream numeric controls without discarding unknown values."""
    if value == " ":
        return {"type": "control_eos"}
    if value.startswith("U:"):
        return {"type": "full_glyph", "code": int(value[2:], 16)}
    number = int(value, 16)
    if 0x400 <= number <= 0x4ff:
        code, parameters = 4, bytes((number & 255,))
    elif 0x100 <= number <= 0x1ff:
        code, parameters = 0, bytes((number & 255,))
    else:
        raw = number.to_bytes(max(1, (number.bit_length() + 7) // 8), "big")
        code, parameters = raw[0], raw[1:]
    if code not in PARAMETER_BYTES or len(parameters) != PARAMETER_BYTES[code]:
        raise ValueError(f"Unsupported control @[{value}]")
    return {"type": "control", "code": code, "parameters_hex": parameters.hex()}


def tokenize(text, charset):
    result = []
    cursor = 0
    while cursor < len(text):
        if text.startswith("@[", cursor):
            end = text.find("]", cursor + 2)
            if end < 0:
                raise ValueError("Unterminated control")
            result.append(controls(text[cursor + 2:end]))
            cursor = end + 1
        else:
            character = text[cursor]
            if character == " ":
                result.append({"type": "control", "code": 0x52, "parameters_hex": ""})
            else:
                if character not in charset:
                    raise ValueError(f"Unmapped character U+{ord(character):04X}")
                result.append({"type": "full_glyph", "code": charset[character]})
            cursor += 1
    return result


def canonical(tokens):
    return [("glyph", t["code"]) if t["type"].endswith("glyph") else
            (t["type"], t.get("code"), t.get("parameters_hex", "")) for t in tokens]


def serialize(tokens):
    payload = bytearray()
    for token in tokens:
        if token["type"] == "full_glyph":
            code = token["code"]
            if not 0 <= code < 0x8000:
                raise ValueError("Glyph code exceeds standard encoding")
            payload.extend((0x80 | (code >> 8), code & 255))
        elif token["type"] == "control_eos":
            payload.append(0)
        else:
            payload.extend((0x40, token["code"] + 0x21))
            payload.extend(bytes.fromhex(token["parameters_hex"]))
    payload.append(0)
    entry = {"encoding": "standard", "tokens": tokens,
             "decoded_sha256": sha(payload), "rom_offset": 0}
    if encode_tokens(entry) != payload:
        raise ValueError("Existing token serializer disagrees")
    decoded = decode_word(payload, 0)
    if canonical(decoded["tokens"]) != canonical(tokens) or decoded["size"] != len(payload):
        raise ValueError("Existing decoder did not round-trip the complete stream")
    return entry, bytes(payload)


def retail_bindings(assets):
    bindings = {}
    for filename, family in (("scene-text-pages.json", "s_text"),
                             ("fixed-text-pages.json", "fx_text")):
        document = json.loads((assets / filename).read_text())
        if document["reference_sha256"] != RETAIL_SHA256:
            raise ValueError("Wrong extracted text revision")
        def visit(page, indices):
            for entry in page.get("entries", []):
                if "tokens" in entry:
                    bindings[family, "/".join(map(str, indices + [entry["index"]]))] = entry
            for subpage_index, child in enumerate(page.get("subpages", [])):
                visit(child, indices + [subpage_index])
        for page in document["pages"]:
            visit(page, [page["page_index"]])
    words = json.loads((assets / "word-tables.json").read_text())
    if words["reference_sha256"] != RETAIL_SHA256:
        raise ValueError("Wrong extracted word revision")
    for name, table in words["tables"].items():
        for entry in table["entries"]:
            if "tokens" in entry:
                bindings["words:" + name, str(entry["index"])] = entry
    return bindings


def generate_font(path, characters, destination, bear_assets=None):
    """Render upstream's selected face; preserve its documented decoration order."""
    import PIL
    from PIL import Image, ImageDraw, ImageFont
    from fontTools.ttLib import TTFont
    with TTFont(path) as face:
        cmap = face.getBestCmap()
        notices = sorted({record.toUnicode() for record in face["name"].names
                          if record.nameID in (0, 13, 14)})
    write_json(destination / "font-notices.json", notices)
    font = ImageFont.truetype(str(path), 10)
    payload = bytearray()
    missing, inventory = [], []
    source_font = (bear_assets / "font-4bpp.bin").read_bytes() if bear_assets else b""
    source_charset = json.loads((bear_assets / "source-charset.json").read_text())[1] if bear_assets else {}
    for character, code in sorted(characters.items(), key=lambda pair: pair[1]):
        if character in source_charset:
            source_code = source_charset[character]
            raw = source_font[source_code * 128:(source_code + 1) * 128]
            if len(raw) != 128:
                raise ValueError("Bear source glyph outside extracted font")
            inventory.append({"character": character, "game_code": code,
                              "payload_offset": len(payload), "size": 128,
                              "source": "bear_rom", "source_game_code": source_code,
                              "advance": None, "advance_status": "requires_renderer_validation"})
            payload.extend(raw)
            continue
        if ord(character) not in cmap:
            missing.append(character)
            continue
        bitmap = Image.new("1", (10, 10), 1)
        ImageDraw.Draw(bitmap).text((0, 0), character, fill=0, font=font, spacing=0)
        # Match the upstream generator's one-pixel work margin plus (0, 1)
        # placement offset. Decoration is based on strokes, never on outlines.
        strokes = {(x + 1, y + 2) for y in range(10) for x in range(10)
                   if not bitmap.getpixel((x, y))}
        if not strokes:
            missing.append(character)
            continue
        pixels = {}
        for offsets, shade in (([(x, y) for x in (-1, 0, 1) for y in (-1, 0, 1)
                                  if (x, y) != (0, 0)], 1),
                                ([(1, 0), (1, 1)], 2), ([(0, 0)], 3)):
            for x, y in strokes:
                for dx, dy in offsets:
                    if not (0 <= x + dx < 16 and 0 <= y + dy < 16):
                        raise ValueError("Font decoration clips cell")
                    pixels[x + dx, y + dy] = shade
        raw = bytearray(128)
        for (x, y), shade in pixels.items():
            raw[(x // 8) * 64 + y * 4 + (x % 8) // 2] |= shade << (4 * (x % 2))
        inventory.append({"character": character, "game_code": code,
                          "payload_offset": len(payload), "size": 128, "source": "bundled_ttf",
                          "advance": None, "advance_status": "requires_renderer_validation"})
        payload.extend(raw)
    if payload:
        atlas = decode_atlas(payload, len(inventory), 64)
        if encode_atlas(atlas, len(inventory), 64) != payload:
            raise ValueError("Font atlas round trip failed")
        (destination / "font-4bpp.bin").write_bytes(payload)
        (destination / "font-atlas.pgm").write_bytes(atlas)
    return {"glyphs": inventory, "missing_characters": missing,
            "payload_sha256": sha(payload), "pillow_version": PIL.__version__,
            "pixel_roles": {"transparent": 0, "outline": 1, "shadow": 2, "fill": 3},
            "palette_policy": "retain retail palette and style remapping"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--assets-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--generate-font", action="store_true")
    parser.add_argument("--bear-assets", type=Path, help="Verified extract_bear_localization output")
    args = parser.parse_args()
    for path in (args.upstream, args.assets_dir, args.output_dir):
        if path.resolve().is_relative_to(ROOT):
            raise ValueError("External inputs and output required")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError("Use a clean output directory")
    revision = subprocess.check_output(["git", "-C", str(args.upstream), "rev-parse", "HEAD"], text=True).strip()
    if revision != UPSTREAM_REVISION:
        raise ValueError("Unreviewed upstream revision")
    if subprocess.check_output(["git", "-C", str(args.upstream), "status", "--porcelain", "--", *SOURCE_FILES]):
        raise ValueError("Upstream inputs have local changes")
    bindings = retail_bindings(args.assets_dir)
    us_charset = json.loads((args.upstream / "charset_us.json").read_text())[1]
    records, skipped = {}, []
    base_report = None
    sources = []
    if args.bear_assets:
        if args.bear_assets.resolve().is_relative_to(ROOT):
            raise ValueError("Bear assets must remain external")
        base_report = json.loads((args.bear_assets / "report.json").read_text())
        from extract_bear_localization import BEAR_REVISIONS
        if (base_report["reference_sha256"] != RETAIL_SHA256 or
                base_report["source_rom_sha256"] not in BEAR_REVISIONS or
                base_report["upstream_revision"] != UPSTREAM_REVISION):
            raise ValueError("Unreviewed Bear extraction")
        for name, expected in base_report["file_sha256"].items():
            if Path(name).name != name or sha((args.bear_assets / name).read_bytes()) != expected:
                raise ValueError("Bear extraction file hash mismatch")
        sources.append(("base-pairs.json", args.bear_assets / "base-pairs.json"))
    sources.extend((name, args.upstream / name) for name in ("trans_txt.json", "trans_fix_txt.json"))
    for filename, source_path in sources:
        data = json.loads(source_path.read_text())
        for family, rows in data.items():
            for key, value in rows.items():
                if family.startswith("#") or key.startswith("#") or not isinstance(value, list) or len(value) != 2:
                    skipped.append({"file": filename, "family": family, "key": key, "reason": "inactive_or_placeholder"})
                    continue
                original, translated = value
                translated = translated.split("#", 1)[0]
                if not translated:
                    skipped.append({"file": filename, "family": family, "key": key, "reason": "untranslated"})
                    continue
                records[family, key] = {"source_file": filename, "family": family, "key": key,
                                       "original_text": original.split("#", 1)[0], "text": translated}
    characters = sorted({c for record in records.values() for c in re.sub(r"@\[[^]]*\]", "", record["text"]) if c != " "})
    charset = {c: us_charset[c] for c in characters if c in us_charset and us_charset[c] < 0x122}
    dynamic = {c: 0x122 + i for i, c in enumerate(c for c in characters if c not in charset)}
    charset.update(dynamic)
    if max(charset.values(), default=0) >= 3175:
        raise ValueError("Localized glyph inventory exceeds retail atlas capacity")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    font = generate_font(args.upstream / "font/BoutiqueBitmap9x9_1.7.ttf", dynamic, args.output_dir, args.bear_assets) if args.generate_font else None
    payload = bytearray()
    for identity, record in records.items():
        target = bindings.get(identity)
        record["binding_status"] = "unmapped_family_or_index"
        if target:
            record["target_rom_offset"] = target["rom_offset"]
            record["expected_original_sha256"] = target.get("decoded_sha256", target.get("raw_sha256"))
            try:
                record["binding_status"] = "verified" if canonical(tokenize(record["original_text"], us_charset)) == canonical(target["tokens"]) else "source_mismatch"
            except (ValueError, KeyError):
                record["binding_status"] = "source_not_decodable"
        try:
            entry, encoded = serialize(tokenize(record["text"], charset))
            record.update(entry)
            record.pop("rom_offset")
            record["payload_offset"], record["payload_size"] = len(payload), len(encoded)
            payload.extend(encoded)
            record["conversion_status"] = "round_trip_verified"
            record["missing_font_characters"] = sorted(set(record["text"]) & set(font["missing_characters"])) if font else None
            record["integration_ready"] = False
            record["integration_blockers"] = ["dedicated_localization_linker_required", "advance_metrics_unverified"]
            if record["binding_status"] != "verified":
                record["integration_blockers"].append(record["binding_status"])
            if record["missing_font_characters"]:
                record["integration_blockers"].append("missing_font_glyphs")
        except (ValueError, KeyError) as error:
            record["conversion_status"], record["error"] = "blocked", str(error)
    (args.output_dir / "text-streams.bin").write_bytes(payload)
    (args.output_dir / "UPSTREAM-LICENSE.txt").write_bytes((args.upstream / "LICENSE").read_bytes())
    write_json(args.output_dir / "localized-text.json", {"reference_sha256": RETAIL_SHA256,
               "encoding": "standard", "records": list(records.values()), "skipped": skipped})
    write_json(args.output_dir / "charset.json", {"assignment_status": "temporary_full_localization_profile",
               "warning": "Not safe to overlay onto untranslated retail text; requires dedicated linker",
               "characters": charset, "dynamic_characters": dynamic})
    if font:
        write_json(args.output_dir / "font.json", font)
    report = {"upstream_url": "https://github.com/BSoD123456/ffta_us_cn", "upstream_revision": revision,
              "source_sha256": {name: sha((args.upstream / name).read_bytes()) for name in SOURCE_FILES},
              "repository_license": "GPL-3.0; retain separate font and original game provenance",
              "records": len(records), "skipped": len(skipped), "dynamic_glyphs": len(dynamic),
              "bindings": dict(Counter(r["binding_status"] for r in records.values())),
              "conversions": dict(Counter(r["conversion_status"] for r in records.values())),
              "font_missing": len(font["missing_characters"]) if font else None,
              "rom_integration": "not_attempted", "text_payload_sha256": sha(payload),
              "bear_source": base_report}
    write_json(args.output_dir / "report.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
