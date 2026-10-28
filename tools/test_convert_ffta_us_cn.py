"""Boundary checks for the optional upstream resource adapter."""
import unittest
from convert_ffta_us_cn import canonical, controls, serialize, tokenize
from extract_resources import decode_word


class TranslationAdapterTests(unittest.TestCase):
    def test_variable_and_name_controls(self):
        self.assertEqual(controls("400"), {"type": "control", "code": 4, "parameters_hex": "00"})
        self.assertEqual(controls("5103"), {"type": "control", "code": 0x51, "parameters_hex": "03"})

    def test_choice_embedded_terminators_round_trip(self):
        tokens = tokenize("@[3211]A@[ ]B@[ ]@[42]", {"A": 0xb0, "B": 0xb1})
        _, payload = serialize(tokens)
        self.assertEqual(canonical(decode_word(payload, 0)["tokens"]), canonical(tokens))

    def test_reject_stray_terminator(self):
        with self.assertRaises(ValueError):
            serialize(tokenize("A@[ ]B", {"A": 0xb0, "B": 0xb1}))

    def test_reject_unknown_and_truncated_controls(self):
        for text in ("@[DEAD]", "@[51]", "@[4D", "?"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                tokenize(text, {})

    def test_single_glyph_change_changes_stream(self):
        _, first = serialize(tokenize("A", {"A": 0xb0}))
        _, second = serialize(tokenize("B", {"B": 0xb1}))
        self.assertEqual([i for i, (a, b) in enumerate(zip(first, second)) if a != b], [1])


if __name__ == "__main__":
    unittest.main()
