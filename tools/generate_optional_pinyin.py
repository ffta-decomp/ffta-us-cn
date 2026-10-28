#!/usr/bin/env python3
"""Generate an optional, glyph-filtered FFTA single-character pinyin table."""

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RIME_SHA256 = "e341598343a0f0f2035bb1aafc34a7f3bb7887deeecb3f60796262aaa2983e6b"
RIME_LICENSE_SHA256 = "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"
SPELLING = re.compile(r"[a-z]{1,6}\Z")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require_external(path, label):
    """Keep licensed dictionaries and generated game data outside the source tree."""
    if path.resolve().is_relative_to(ROOT):
        raise ValueError(f"{label} must be outside the source repository")


def pack(spelling):
    key = 0
    for letter in spelling:
        key = (key << 5) | (ord(letter) - ord("a") + 1)
    return key << (5 * (6 - len(spelling)))


def read_chars(path):
    return {character for character in path.read_text(encoding="utf-8")
            if "\u3400" <= character <= "\u9fff"}


def read_map(path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not raw:
        raise ValueError("Glyph map must be a nonempty JSON object")
    result = {}
    for character, token in raw.items():
        if len(character) != 1 or not ("\u3400" <= character <= "\u9fff"):
            raise ValueError(f"Glyph map key is not one Hanzi: {character!r}")
        if isinstance(token, str):
            token = int(token, 0)
        if not isinstance(token, int) or isinstance(token, bool) or not 0 <= token <= 65535:
            raise ValueError(f"Invalid FFTA u16 token for {character}")
        if token in result.values():
            raise ValueError(f"Duplicate FFTA token: {token:#06x}")
        result[character] = token
    return result


def parse_dictionary(path, eligible):
    raw = path.read_bytes()
    if digest(raw) != RIME_SHA256:
        raise ValueError("Unexpected Rime dictionary SHA-256; expected pinned revision")
    readings = defaultdict(dict)
    for line in raw.decode("utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) < 3:
            continue
        character, spelling, weight = fields[:3]
        if character not in eligible or not SPELLING.fullmatch(spelling):
            continue
        try:
            weight = int(weight)
        except ValueError:
            continue
        readings[spelling][character] = max(weight, readings[spelling].get(character, -1))
    return readings


def make_table(glyph_map, readings, ranks):
    rows = []
    tokens = []
    covered = set()
    for spelling in sorted(readings, key=pack):
        candidates = sorted(readings[spelling],
                            key=lambda char: (ranks.get(char, 3),
                                              -readings[spelling][char],
                                              ord(char)))
        first = len(tokens)
        tokens.extend(glyph_map[char] for char in candidates)
        rows.append((pack(spelling), first, len(candidates), spelling))
        covered.update(candidates)
    if len(rows) > 65535 or len(tokens) > 65535:
        raise ValueError("Table exceeds its u16 row or candidate index")
    return rows, tokens, covered


def write_outputs(output_dir, rows, tokens, report):
    output_dir.mkdir(parents=True, exist_ok=True)
    source = [
        "/* Generated optional CJK IME table. See coverage.json for provenance. */",
        '#include "optional_pinyin.h"',
        "",
        "static const struct PinyinRow kPinyinRows[] = {",
    ]
    source += [f"    {{0x{key:08x}u, {first}, {count}}}, /* {spelling} */"
               for key, first, count, spelling in rows]
    source += ["};", "static const uint16_t kPinyinTokens[] = {"]
    source += ["    " + ", ".join(f"0x{token:04x}" for token in tokens[i:i + 12]) + ","
               for i in range(0, len(tokens), 12)]
    source += ["};", "", "const struct PinyinTable gOptionalPinyinTable = {",
               "    kPinyinRows, kPinyinTokens,",
               f"    {len(rows)}, {len(tokens)}", "};", ""]
    header = ["#ifndef OPTIONAL_PINYIN_TABLE_H", "#define OPTIONAL_PINYIN_TABLE_H",
              '#include "optional_pinyin.h"',
              "extern const struct PinyinTable gOptionalPinyinTable;",
              "#endif", ""]
    source_bytes = "\n".join(source).encode("ascii")
    header_bytes = "\n".join(header).encode("ascii")
    report["generated_c_sha256"] = digest(source_bytes)
    (output_dir / "optional_pinyin_table.c").write_bytes(source_bytes)
    (output_dir / "optional_pinyin_table.h").write_bytes(header_bytes)
    (output_dir / "coverage.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rime-dictionary", required=True, type=Path)
    parser.add_argument("--glyph-map", required=True, type=Path,
                        help="JSON Hanzi -> installed two-byte FFTA game token")
    parser.add_argument("--candidate-chars", type=Path,
                        help="Optional character inventory; default all mapped Hanzi")
    parser.add_argument("--required-chars", type=Path,
                        help="Reject requested name characters without a Rime reading")
    parser.add_argument("--rank-chars", action="append", type=Path, default=[],
                        help="Priority tiers in order, e.g. person/place/weapon names")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    for path, label in ((args.rime_dictionary, "Rime dictionary"),
                        (args.glyph_map, "Glyph map"),
                        (args.output_dir, "Output directory")):
        if label == "Rime dictionary" and path.resolve() == (ROOT / "vendor/rime-pinyin-simp/pinyin_simp.dict.yaml").resolve():
            continue  # Licensed, hash-pinned dependency; private glyph inputs remain external.
        require_external(path, label)
    for path, label in ((args.candidate_chars, "Candidate inventory"),
                        (args.required_chars, "Required inventory")):
        if path is not None:
            require_external(path, label)
    for path in args.rank_chars:
        require_external(path, "Ranking inventory")
    glyph_map = read_map(args.glyph_map)
    wanted = read_chars(args.candidate_chars) if args.candidate_chars else set(glyph_map)
    absent = wanted - glyph_map.keys()
    if absent:
        raise ValueError(f"Candidates lack installed glyph tokens: {''.join(sorted(absent))}")
    required = read_chars(args.required_chars) if args.required_chars else set()
    if required - wanted:
        raise ValueError("Required name characters must be in candidate inventory")
    ranks = {}
    for tier, path in enumerate(args.rank_chars):
        for character in read_chars(path):
            ranks.setdefault(character, tier)
    readings = parse_dictionary(args.rime_dictionary, wanted)
    license_bytes = (args.rime_dictionary.parent / "LICENSE").read_bytes()
    if digest(license_bytes) != RIME_LICENSE_SHA256:
        raise ValueError("Pinned Rime Apache-2.0 license file is missing or changed")
    rows, tokens, covered = make_table(glyph_map, readings, ranks)
    missing = wanted - covered
    if required - covered:
        raise ValueError(f"Required name characters lack Rime readings: {''.join(sorted(required - covered))}")
    if not rows:
        raise ValueError("No single-character Rime candidates remain")
    report = {
        "format": "optional-pinyin-u32-u16-v1",
        "rime_dictionary_sha256": RIME_SHA256,
        "glyph_map_sha256": digest(args.glyph_map.read_bytes()),
        "candidate_inventory_count": len(wanted),
        "covered_character_count": len(covered),
        "missing_reading_characters": "".join(sorted(missing)),
        "syllable_count": len(rows),
        "character_reading_pairs": len(tokens),
        "max_candidates_per_syllable": max(row[2] for row in rows),
        "index_bytes": len(rows) * 8,
        "candidate_bytes": len(tokens) * 2,
        "table_bytes_excluding_compiler_padding": len(rows) * 8 + len(tokens) * 2,
        "candidate_tokens_are_mapped_glyphs": True,
        "single_character_only": True,
    }
    write_outputs(args.output_dir, rows, tokens, report)
    (args.output_dir / "RIME-LICENSE.txt").write_bytes(license_bytes)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
