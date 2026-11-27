"""Plugin memory regressions independent of the private game inputs."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from plugin_memory import (FASTSKIP_RAM, NATIVE_HEAP_END, RECRUIT_RAM, R_INFO_END,
                           check_recruit_memory, check_reservations, checked_menu_heap_end, menu_heap_end)


class PluginMemoryTests(unittest.TestCase):
    def test_deployment_requires_the_contiguous_arena(self):
        self.assertEqual(R_INFO_END, 0x0203EDD8)
        self.assertEqual(R_INFO_END - 0x0203ED20, 184)
        for ceiling in (0x0203ED20, R_INFO_END - 4, R_INFO_END + 1):
            with self.assertRaisesRegex(ValueError, 'R Info arena'):
                checked_menu_heap_end(ceiling)

    def test_each_feature_combination_has_one_heap_ceiling(self):
        self.assertEqual(menu_heap_end(recruit=False), NATIVE_HEAP_END)
        self.assertEqual(menu_heap_end(recruit=False, fastskip=True), FASTSKIP_RAM[0])
        self.assertEqual(menu_heap_end(recruit=True), RECRUIT_RAM[0])
        self.assertEqual(menu_heap_end(recruit=True, fastskip=True), RECRUIT_RAM[0])
        check_reservations([
            ('recruit', {'menu_heap_end': RECRUIT_RAM[0], 'ram_reservation': RECRUIT_RAM}),
            ('fastskip', {'menu_heap_end': RECRUIT_RAM[0], 'ram_reservation': FASTSKIP_RAM}),
        ])
        with self.assertRaisesRegex(ValueError, 'disagree'):
            check_reservations([('recruit', {'menu_heap_end': RECRUIT_RAM[0]}),
                                ('fastskip', {'menu_heap_end': FASTSKIP_RAM[0]})])

    def test_live_heap_and_plugin_overlaps_are_rejected(self):
        recruit = ('recruit', {'menu_heap_end': RECRUIT_RAM[0], 'ram_reservation': RECRUIT_RAM})
        with self.assertRaisesRegex(ValueError, 'native menu heap'):
            check_reservations([recruit, ('new', {'ram_reservation': [0x0203F7FC, 0x0203F800]})])
        with self.assertRaisesRegex(ValueError, 'Overlapping EWRAM'):
            check_reservations([recruit, ('new', {'ram_reservation': [0x0203F900, 0x0203FA00]})])

    def test_editor_flash_and_resident_budgets(self):
        values = [RECRUIT_RAM[0], 908, 108692, 4096, 4120]
        check_recruit_memory(*values)
        for index, invalid in enumerate((0x0203ED20, 1025, 108696, 8192, 4300)):
            changed = values.copy()
            changed[index] = invalid
            with self.assertRaises(ValueError):
                check_recruit_memory(*changed)
