"""Memory limits shared by the US menu heap patches and their build reports."""

EWRAM_START = 0x02000000
EWRAM_END = 0x02040000
RECRUIT_RAM = (0x0203F800, 0x0203FC00)  # The native cold boot clears through this end.
FASTSKIP_RAM = (0x0203FFF0, EWRAM_END)
NATIVE_HEAP_END = EWRAM_END

# R Info requests 0xc600 bytes at the first free block in the authenticated
# deployment replay. The native allocator puts a 12-byte header before it.
MENU_HEAP_BASE = 0x020159D0
R_INFO_FREE_BLOCK = 0x020327CC
NATIVE_BLOCK_HEADER = 12
R_INFO_ARENA = 0xC600
R_INFO_END = R_INFO_FREE_BLOCK + NATIVE_BLOCK_HEADER + R_INFO_ARENA

SHARED_OPTIONS_REQUEST = 0x1C80
RECRUIT_EDITOR_REQUEST = 108692
FLASH_PAGE_BYTES = 4096
# In addition to write_sector's compiler frame, the synchronous native Flash
# calls use at least 284 bytes (program wrapper and its read-back verifier).
FLASH_CALLEE_ALLOWANCE = 0x200
FLASH_STACK_MIN = 0x03007A00
FLASH_STACK_LIMIT = FLASH_STACK_MIN - 0x0300616C - 0x600 - FLASH_CALLEE_ALLOWANCE


def checked_menu_heap_end(end):
    if type(end) is not int or end % 4 or not R_INFO_END <= end <= NATIVE_HEAP_END:
        raise ValueError(f'Menu heap cannot fit the R Info arena ending at {R_INFO_END:#010x}')
    return end


def menu_heap_end(*, recruit, fastskip=False):
    return checked_menu_heap_end(RECRUIT_RAM[0] if recruit else
                                 FASTSKIP_RAM[0] if fastskip else NATIVE_HEAP_END)


def check_recruit_memory(start, resident, editor, page, writer_stack):
    if start != RECRUIT_RAM[0] or not 0 < resident <= RECRUIT_RAM[1] - start:
        raise ValueError('Recruit runtime exceeds its cold-cleared EWRAM reservation')
    if editor != RECRUIT_EDITOR_REQUEST or page != FLASH_PAGE_BYTES:
        raise ValueError('Recruit editor or Flash workspace changed; review its budget and Info')
    if not page <= writer_stack <= FLASH_STACK_LIMIT:
        raise ValueError('Recruit Flash writer exceeds its IWRAM stack budget')


def check_reservations(reports):
    reports = list(reports)
    ceilings = {report['menu_heap_end'] for _, report in reports if 'menu_heap_end' in report}
    if len(ceilings) > 1:
        raise ValueError('Menu heap patches disagree about the EWRAM ceiling')
    ceiling = checked_menu_heap_end(next(iter(ceilings), NATIVE_HEAP_END))
    claimed = []
    for plugin, report in reports:
        if 'ram_reservation' not in report:
            continue
        bounds = report['ram_reservation']
        if (not isinstance(bounds, (tuple, list)) or len(bounds) != 2 or any(type(value) is not int or value % 4 for value in bounds)
                or not EWRAM_START <= bounds[0] < bounds[1] <= EWRAM_END):
            raise ValueError(f'Invalid EWRAM reservation for {plugin}')
        start, end = bounds
        if start < ceiling and MENU_HEAP_BASE < end:
            raise ValueError(f'EWRAM reservation for {plugin} overlaps the native menu heap')
        for earlier, earlier_start, earlier_end in claimed:
            if start < earlier_end and earlier_start < end:
                raise ValueError(f'Overlapping EWRAM reservations for {earlier} and {plugin}')
        claimed.append((plugin, start, end))
