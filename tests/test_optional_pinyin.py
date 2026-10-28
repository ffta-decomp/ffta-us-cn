"""Host checks for the optional, ROM-resident single-character IME core."""

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "generate_optional_pinyin", ROOT / "tools/generate_optional_pinyin.py")
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)


class PinyinTests(unittest.TestCase):
    def test_external_data_path_guard(self):
        with self.assertRaisesRegex(ValueError, "outside the source repository"):
            GENERATOR.require_external(ROOT / "build" / "private-map.json", "Glyph map")
        with tempfile.TemporaryDirectory() as temporary:
            GENERATOR.require_external(Path(temporary) / "private-map.json", "Glyph map")

    def test_packing_preserves_prefix_order(self):
        words = ["a", "ai", "an", "ba", "zhuang"]
        self.assertEqual(words, sorted(words, key=GENERATOR.pack))
        self.assertLess(GENERATOR.pack("a"), GENERATOR.pack("ai"))

    def test_candidate_filter_and_ranking(self):
        glyph_map = {"你": 0x8A10, "尼": 0x8A11, "我": 0x8A12}
        readings = {"ni": {"你": 100, "尼": 200}, "wo": {"我": 10}}
        rows, tokens, covered = GENERATOR.make_table(glyph_map, readings, {"你": 0})
        self.assertEqual([row[3] for row in rows], ["ni", "wo"])
        self.assertEqual(tokens, [0x8A10, 0x8A11, 0x8A12])
        self.assertEqual(covered, set(glyph_map))

    def test_rejects_duplicate_or_non_hanzi_token_map(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "glyphs.json"
            path.write_text(json.dumps({"你": 0x011F, "我": 0x011F}),
                            encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                GENERATOR.read_map(path)
            path.write_text(json.dumps({"A": 0x011F}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Hanzi"):
                GENERATOR.read_map(path)

    def test_generated_table_runs_without_runtime_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            rows, tokens, _ = GENERATOR.make_table(
                {"你": 0x8A10, "尼": 0x8A11, "我": 0x8A12},
                {"ni": {"你": 100, "尼": 200}, "wo": {"我": 10}},
                {"你": 0})
            GENERATOR.write_outputs(folder, rows, tokens, {})
            harness = folder / "harness.c"
            harness.write_text('''
#include <assert.h>
#include "optional_pinyin.h"
#include "optional_pinyin_table.h"
int main(void) {
    uint16_t output[2] = {0, 0};
    struct PinyinComposition text;
    struct PinyinPage result;
    PinyinClear(&text);
    assert(PinyinAppend(&text, 'n'));
    assert(PinyinAppend(&text, 'i'));
    assert(!PinyinAppend(&text, '1'));
    result = PinyinLookup(&gOptionalPinyinTable, text.letters, 0, output, 1);
    assert(result.total_candidates == 2 && result.returned_candidates == 1);
    assert(output[0] == 0x8a10);
    result = PinyinLookup(&gOptionalPinyinTable, "ni", 1, output, 1);
    assert(result.total_candidates == 2 && output[0] == 0x8a11);
    assert(PinyinLookup(&gOptionalPinyinTable, "n", 0, output, 2).total_candidates == 0);
    assert(PinyinLookup(&gOptionalPinyinTable, "NI", 0, output, 2).total_candidates == 0);
    assert(PinyinLookup(&gOptionalPinyinTable, "ni", 999, output, 2).returned_candidates == 0);
    assert(PinyinLookup(&gOptionalPinyinTable, "ni", 0, output, 0).total_candidates == 2);
    assert(PinyinBackspace(&text) && text.length == 1);
    return 0;
}
''', encoding="ascii")
            executable = folder / "test-ime"
            subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                            "-I", str(ROOT / "engine/pinyin/include"), "-I", str(folder),
                            str(ROOT / "engine/pinyin/optional_pinyin.c"),
                            str(folder / "optional_pinyin_table.c"), str(harness),
                            "-o", str(executable)], check=True)
            subprocess.run([str(executable)], check=True)

    @unittest.skipUnless((ROOT / "vendor/rime-pinyin-simp/pinyin_simp.dict.yaml").is_file(),
                         "Vendored licensed dictionary is unavailable")
    def test_pinned_rime_end_to_end(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            mapping = folder / "glyphs.json"
            mapping.write_text(json.dumps({"你": "0x8a10", "我": "0x8a12"}),
                               encoding="utf-8")
            args = ["python3", str(ROOT / "tools/generate_optional_pinyin.py"),
                    "--rime-dictionary", str(ROOT / "vendor/rime-pinyin-simp/pinyin_simp.dict.yaml"),
                    "--glyph-map", str(mapping), "--output-dir", str(folder)]
            subprocess.run(args, check=True, capture_output=True)
            first = (folder / "optional_pinyin_table.c").read_bytes()
            report = json.loads((folder / "coverage.json").read_text())
            self.assertTrue(report["candidate_tokens_are_mapped_glyphs"])
            self.assertEqual(report["covered_character_count"], 2)
            self.assertEqual((folder / "RIME-LICENSE.txt").read_bytes(),
                             (Path(str(ROOT / "vendor/rime-pinyin-simp/pinyin_simp.dict.yaml")).parent / "LICENSE").read_bytes())
            subprocess.run(args, check=True, capture_output=True)
            self.assertEqual(first, (folder / "optional_pinyin_table.c").read_bytes())


if __name__ == "__main__":
    unittest.main()
