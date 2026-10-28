#!/usr/bin/env python3
"""Build an opt-in Chinese dialogue demonstration from the retail baseline."""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

from decomp_formats import DECOMP_ROOT
from scene_text_codec import encode_compression


ROOT = DECOMP_ROOT
RETAIL_SHA256 = "43fc8204c6dceee58828aebc7af0c72eb807e99f35ad641c8bb0a4fa8b6edc19"
FONT_ARCHIVE_SHA256 = "76ed4adde0cc43ae8312041960d586c130c75a9d0f7c1c64a7cace7e4130c358"
BDF_NAME = "fusion-pixel-12px-monospaced-zh_hans.bdf"
FONT_OFFSET = 0x433330
FONT_GLYPHS = 3175
FONT_CELL_BYTES = 128
WIDTH_TABLE_OFFSET = 0x4966b0
DEMO_ADVANCE = 13
TEXT_END_CONTROLS = (0x40, 0x42)
NAME_TOKEN = "{NAME03}"
CJK_PAGE_TAB_LABEL = "中"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def iter_entries(node):
    if isinstance(node, dict):
        if "tokens" in node:
            yield node
        else:
            for value in node.values():
                yield from iter_entries(value)
    elif isinstance(node, list):
        for value in node:
            yield from iter_entries(value)


def read_bdf_subset(bdf, characters):
    """Parse only requested ISO10646 glyphs; preserve each native bitmap pixel."""
    wanted = {ord(character) for character in characters}
    found = {}
    lines = bdf.decode("ascii").splitlines()
    index = 0
    while index < len(lines):
        if not lines[index].startswith("STARTCHAR "):
            index += 1
            continue
        encoding = None
        box = None
        bitmap = None
        index += 1
        while index < len(lines) and lines[index] != "ENDCHAR":
            line = lines[index]
            if line.startswith("ENCODING "):
                encoding = int(line.split()[1])
            elif line.startswith("BBX "):
                box = tuple(map(int, line.split()[1:]))
            elif line == "BITMAP":
                require(box is not None, "BDF bitmap without BBX")
                bitmap = lines[index + 1:index + 1 + box[1]]
                index += box[1]
            index += 1
        if encoding in wanted:
            require(bitmap is not None and box is not None, f"Missing BDF pixels U+{encoding:04X}")
            found[encoding] = (box, bitmap)
        index += 1
        if len(found) == len(wanted):
            break
    missing = sorted(wanted - found.keys())
    require(not missing, f"Font lacks glyphs: {[hex(value) for value in missing]}")
    return found


def render_glyph(box, bitmap):
    width, height, xoff, yoff = box
    require(0 < width <= 12 and 0 < height <= 12, "Unexpected BDF dimensions")
    # Retail Latin pixels occupy rows 3-12. The 12px face uses rows 2-13,
    # with one surrounding outline row; yoff is measured from the baseline.
    origin_x = 1 + xoff
    origin_y = 12 - yoff - height
    pixels = set()
    for y, row in enumerate(bitmap):
        value = int(row, 16)
        storage_bits = len(row) * 4
        for x in range(width):
            if value & (1 << (storage_bits - 1 - x)):
                px, py = origin_x + x, origin_y + y
                require(1 <= px <= 14 and 1 <= py <= 14, "Glyph clips its 16px cell")
                pixels.add((px, py))
    require(pixels, "Empty requested glyph")
    # Build separate masks so overlapping strokes cannot change shade priority.
    # Keep retail indices: transparent 0, outline 1, shadow 2, fill 3.
    outline = {(x + dx, y + dy) for x, y in pixels
               for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))} - pixels
    # Retail shadow pixels lie within one right/down step of the fill.
    # Projecting the outline too would extend the effect a second pixel.
    shadow = {(x + dx, y + dy) for x, y in pixels
              for dx, dy in ((1, 0), (0, 1), (1, 1))} - pixels - outline
    palette = {}
    for mask, shade in ((shadow, 2), (outline, 1), (pixels, 3)):
        for x, y in mask:
            require(0 <= x < 16 and 0 <= y < 16, "Glyph effect clips its 16px cell")
            palette[x, y] = shade
    raw = bytearray(FONT_CELL_BYTES)
    for (x, y), shade in palette.items():
        raw[(x // 8) * 64 + y * 4 + (x % 8) // 2] |= shade << (4 * (x % 2))
    return bytes(raw)


def encode_control(code, parameter=b""):
    return bytes((0x40, code + 0x21)) + parameter


def encode_message(boxes, game_codes):
    output = bytearray()
    for box_index, lines in enumerate(boxes):
        require(1 <= len(lines) <= 3, "Dialogue boxes must contain 1-3 lines")
        for line_index, line in enumerate(lines):
            for part in re.split(r"(\{NAME03\})", line):
                if part == NAME_TOKEN:
                    output.extend(encode_control(0x51, b"\x03"))
                else:
                    for character in part:
                        code = game_codes[character]
                        output.extend((0x80 | (code >> 8), code & 255))
            if line_index + 1 != len(lines):
                output.extend(encode_control(0x4d))
        if box_index + 1 != len(boxes):
            output.extend(encode_control(0x4f))
            output.extend(encode_control(0x42))
    for code in TEXT_END_CONTROLS:
        output.extend(encode_control(code))
    output.append(0)
    return bytes(output)


def compressed_entry(flags, decoded):
    operations = [{"form": "literal", "data_hex": decoded[i:i + 64].hex()}
                  for i in range(0, len(decoded), 64)]
    return flags.to_bytes(2, "little") + len(decoded).to_bytes(4, "big") + encode_compression(operations)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--assets-dir", required=True, type=Path)
    parser.add_argument("--dialogue", required=True, type=Path)
    parser.add_argument("--font-archive", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--reuse-baseline", action="store_true",
                        help="Reuse an already verified baseline during visual iteration")
    args = parser.parse_args()
    for path in (args.input, args.output_dir, args.assets_dir, args.dialogue,
                 args.font_archive):
        require(not path.resolve().is_relative_to(ROOT), "Inputs and outputs must remain outside Git")
    require(digest(args.input.read_bytes()) == RETAIL_SHA256, "Wrong retail ROM revision")
    archive = args.font_archive.read_bytes()
    require(digest(archive) == FONT_ARCHIVE_SHA256, "Unexpected font release archive")
    with zipfile.ZipFile(args.font_archive) as bundle:
        bdf = bundle.read(BDF_NAME)
        license_text = bundle.read("OFL.txt")
        license_notices = {name: bundle.read(name) for name in bundle.namelist()
                           if name.startswith("LICENSES/") and not name.endswith("/")}
    dialogue_bytes = args.dialogue.read_bytes()
    dialogue = json.loads(dialogue_bytes)
    require(dialogue.get("reference_sha256") == RETAIL_SHA256, "Dialogue revision mismatch")
    replacements = dialogue["replacements"]
    require(len(replacements) == 2 and
            3 <= sum(len(record["boxes"]) for record in replacements) <= 6,
            "Demo must select both opening entries and 3-6 boxes")
    for record in replacements:
        require(record["page"] == 1 and record["entry"] in (0, 1), "Only verified opening entries are supported")
    require({record["entry"] for record in replacements} == {0, 1}, "Opening entries 0 and 1 required")
    for record in replacements:
        expected_boxes = 2 if record["entry"] == 0 else 1
        expected_names = 0 if record["entry"] == 0 else 1
        require(len(record["boxes"]) == expected_boxes, "Opening box boundaries changed")
        require(sum(line.count(NAME_TOKEN) for box in record["boxes"] for line in box)
                == expected_names, "Dynamic name token changed")
    text = json.loads((args.assets_dir / "scene-text-pages.json").read_text())
    fixed = json.loads((args.assets_dir / "fixed-text-pages.json").read_text())
    require(text["reference_sha256"] == fixed["reference_sha256"] == RETAIL_SHA256,
            "Text source revision mismatch")
    used_codes = {token["code"] for document in (text, fixed)
                  for entry in iter_entries(document["pages"])
                  for token in entry["tokens"]
                  if token["type"] in ("full_glyph", "half_glyph")}
    dialogue_characters = {character for record in replacements
                           for box in record["boxes"] for line in box
                           for character in line.replace(NAME_TOKEN, "")}
    characters = sorted(dialogue_characters | {CJK_PAGE_TAB_LABEL})
    available_codes = [code for code in range(0x118, FONT_GLYPHS) if code not in used_codes]
    require(len(available_codes) >= len(characters), "No unused retail font slots")
    game_codes = dict(zip(characters, available_codes))
    glyphs = read_bdf_subset(bdf, characters)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    baseline_rom = args.output_dir / "retail-baseline.gba"
    baseline_report = args.output_dir / "retail-baseline-build.json"
    if not args.reuse_baseline:
        require(not ROOT.is_relative_to(Path(__file__).resolve().parents[1] / 'vendor'),
                'Historical demo needs an explicitly selected non-vendored engine checkout; use tools/build.py for the current joint build')
        subprocess.run([sys.executable, str(ROOT / "tools/build_rom.py"),
                        "--input", str(args.input), "--config", str(ROOT / "config/retail-us.json"),
                        "--assets-dir", str(args.assets_dir), "--output", str(baseline_rom),
                        "--report", str(baseline_report)], check=True)
    original = baseline_rom.read_bytes()
    prior_report = json.loads(baseline_report.read_text())
    require(prior_report["input_sha256"] == RETAIL_SHA256 and
            prior_report["output_sha256"] == digest(original), "Baseline report/ROM mismatch")
    demo = bytearray(original)
    ranges = []
    for character in characters:
        code = game_codes[character]
        offset = FONT_OFFSET + FONT_CELL_BYTES * code
        payload = render_glyph(*glyphs[ord(character)])
        demo[offset:offset + FONT_CELL_BYTES] = payload
        ranges.append({"kind": "font_glyph", "character": character, "game_code": code,
                       "offset": offset, "size": FONT_CELL_BYTES})
        # Retail uses a separate per-glyph advance table. The selected unused
        # codes may have narrow Latin metrics, which overlap a CJK bitmap.
        advance_offset = WIDTH_TABLE_OFFSET + code
        demo[advance_offset] = DEMO_ADVANCE
        ranges.append({"kind": "font_advance", "character": character, "game_code": code,
                       "offset": advance_offset, "size": 1, "advance": DEMO_ADVANCE})
    for record in replacements:
        entry = text["pages"][1]["entries"][record["entry"]]
        require(entry["encoding"] == "standard", "Unexpected scene text encoding")
        require(digest(bytes.fromhex(record["expected_decoded_hex"])) == entry["decoded_sha256"],
                "Selected scene entry changed")
        decoded = encode_message(record["boxes"], game_codes)
        payload = compressed_entry(entry["flags"], decoded) if entry["compressed"] else \
                  entry["flags"].to_bytes(2, "little") + decoded
        offset = entry["rom_offset"]
        next_offset = text["pages"][1]["entries"][record["entry"] + 1]["rom_offset"]
        require(len(payload) <= next_offset - offset, "Translated entry exceeds fixed page slot")
        demo[offset:offset + len(payload)] = payload
        ranges.append({"kind": "scene_text", "page": 1, "entry": record["entry"],
                       "offset": offset, "size": len(payload), "slot_size": next_offset - offset,
                       "decoded_bytes": len(decoded)})
    result = bytes(demo)
    require(len(result) == len(original), "ROM size changed")
    allowed = bytearray(len(result))
    for entry in ranges:
        start = entry["offset"]
        allowed[start:start + entry["size"]] = b"\x01" * entry["size"]
    changes = [index for index, (before, after) in enumerate(zip(original, result)) if before != after]
    require(changes and all(allowed[index] for index in changes), "Unexpected ROM change outside demo ranges")
    output_rom = args.output_dir / "ffta-zh-demo.gba"
    output_rom.write_bytes(result)
    (args.output_dir / "FONT-OFL.txt").write_bytes(license_text)
    for name, notice in license_notices.items():
        destination = args.output_dir / "font-notices" / Path(name).relative_to("LICENSES")
        require(destination.resolve().is_relative_to(args.output_dir.resolve()),
                "Unsafe font license path")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(notice)
    report = {"input_sha256": RETAIL_SHA256, "baseline_sha256": digest(original),
              "demo_sha256": digest(result), "font_release": "2026.10.16",
              "font_archive_sha256": digest(archive), "font_bdf_sha256": digest(bdf),
              "font_license": "SIL Open Font License 1.1",
              "font_license_notices": {name: digest(notice)
                                       for name, notice in license_notices.items()},
              "dialogue_sha256": digest(dialogue_bytes), "selected_entries": [
                  [record["page"], record["entry"]] for record in replacements],
              "glyph_map_status": "temporary",
              "glyph_assignment_policy": (
                  "Codes are allocated from the current inventory for this build only. "
                  "They are not stable and must not be reused as release assignments. "
                  "After the CJK translation inventory is locked, freeze existing "
                  "Unicode-to-game-code assignments and permit additions only; never "
                  "renumber or reuse an assigned code."
              ),
              "unicode_inventory": [{"character": char, "unicode": f"U+{ord(char):04X}",
                                     "game_code": game_codes[char],
                                     "assignment_status": "temporary"} for char in characters],
              "additional_ui_glyphs": [{
                  "character": CJK_PAGE_TAB_LABEL,
                  "unicode": f"U+{ord(CJK_PAGE_TAB_LABEL):04X}",
                  "game_code": game_codes[CJK_PAGE_TAB_LABEL],
                  "assignment_status": "temporary",
                  "purpose": "third name-entry page tab label",
              }],
              "pixel_roles": {"transparent": 0, "outline": 1, "shadow": 2, "fill": 3},
              "shadow_offset_pixels": [1, 1],
              "palette_policy": "Reuse retail palette and text style index remapping",
              "glyph_count": len(characters), "missing_glyph_count": 0,
              "glyph_payload_bytes": len(characters) * FONT_CELL_BYTES,
              "font_advance_bytes": len(characters), "font_advance_pixels": DEMO_ADVANCE,
              "retail_font_region_bytes": FONT_GLYPHS * FONT_CELL_BYTES,
              "changed_byte_count": len(changes), "changed_ranges": ranges,
              "toolchain": json.loads(baseline_report.read_text())["toolchain"]}
    (args.output_dir / "subset-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n")
    print(json.dumps({key: report[key] for key in ("baseline_sha256", "demo_sha256",
                                                   "glyph_count", "changed_byte_count")}))


if __name__ == "__main__":
    main()
