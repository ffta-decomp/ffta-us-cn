#include "native.h"
#include "build_bindings.h"

#define LEGACY_MAGIC 0x314e5252u
#define MAGIC 0x324e5252u
#define LIVE_NAME ((u8 *)0x02001f1c)
#define GRAPHICS_BYTES 0xc000u
#define EDITOR_HEAP_BYTES 0xe000u
#define RECRUIT_SCENE_BYTES 0xc600u
#define MAIN_HEAP RAM(void *, 0x0200f434)
#define WINDOW_HEAP RAM(void *, 0x020159c4)
#define FLASH_SECTOR_BYTES 4096u
#define PALETTE_SHADOW ((u16 *)0x03003860)
#define HARDWARE_PALETTE ((volatile u16 *)0x05000000)

/* Preview and existing CN saves stored zero in this byte. */
enum { ENCODING_CN, ENCODING_US };

struct Alias {
    u16 name_id;
    u8 race;
    u8 encoding;
    u8 name[NAME_BYTES];
};

struct NameBlock {
    u32 magic;
    u32 sequence;
    u32 native_crc;
    u32 names_crc;
    struct Alias aliases[UNIT_COUNT];
};

struct EditorSession {
    _Alignas(4) u8 original[NAME_BYTES];
    struct NameEvent event;
    u32 editor[NAME_TASK_BYTES / 4];
    void *editor_heap;
    void *owner_heap;
    u16 *graphics;
    u8 display[0x50];
    u8 surface_a[0x24];
    u8 surface_b[0x24];
    u16 palette[512];
    u16 blank_tile[16];
};

struct Runtime {
    struct NameBlock names;
    const struct Unit *candidate;
    const u8 *recruit_step;
    u8 stage;
    u8 editor_caller[8];
    u16 dialog[40];
    _Alignas(4) u8 draft[NAME_BYTES];
    union {
        struct EditorSession naming;
        u8 flash_page[FLASH_SECTOR_BYTES];
    } scratch;
};

enum { FRESH, EDITING, OFFERED, JOINED };
#define STATE ((struct Runtime *)STATE_ADDRESS)
#define ROSTER ((const struct Unit *)FIRST_UNIT)
_Static_assert(sizeof(struct Runtime) <= 0x0203fff0u - STATE_ADDRESS, "reserved EWRAM");
_Static_assert(sizeof(struct NameBlock) < 4096, "name sector");

static void copy(u8 *dest, const u8 *src, unsigned size)
{
    for (unsigned i = 0; i < size; ++i)
        dest[i] = src[i];
}

static void clear(void *dest, unsigned size)
{
    u8 *bytes = dest;
    for (unsigned i = 0; i < size; ++i)
        bytes[i] = 0;
}

static unsigned same(const u8 *a, const u8 *b, unsigned extent)
{
    for (unsigned i = 0; i < extent; ++i)
        if (a[i] != b[i])
            return 0;
    return 1;
}

/* Seed the native eight-cell editor with the editable prefix. An unchanged
 * prefix leaves the full original name on the recruit. */
static unsigned prefill(u8 *out, const u8 *source)
{
    clear(out, NAME_BYTES);
    unsigned compact = *source == 1;
    source += compact;
    for (unsigned i = 0; i < 8 && *source; ++i) {
        if (compact) {
            out[2*i] = 0x80;
            out[2*i+1] = *source++ - 1;
        } else {
            if (*source < 0x80)
                return 0;
            out[2*i] = *source++;
            out[2*i+1] = *source++;
        }
    }
    return out[0] != 0;
}

static unsigned candidate_is_generic(const struct Unit *unit)
{
    return (u32)unit == GENERATED_UNIT && unit->kind == 1 && unit->name >= (const u8 *)NAMES_FIRST &&
           unit->name < (const u8 *)NAMES_END;
}

static const u8 *pool_name(unsigned id)
{
    return id && id <= NAME_POOL_COUNT ? NAME_POOL[id - 1] : 0;
}

static u16 pool_id(const u8 *name)
{
    for (unsigned i = 0; i < NAME_POOL_COUNT; ++i)
        if (NAME_POOL[i] == name)
            return i + 1;
    return 0;
}

/* Native units stay in their physical 24-record array even when the party
 * menu sorts its view. The index disambiguates identical recruit names. */
static unsigned roster_index(const struct Unit *unit)
{
    for (unsigned i = 0; i < UNIT_COUNT; ++i)
        if (&ROSTER[i] == unit)
            return i;
    return UNIT_COUNT;
}

static unsigned alias_matches(const struct Alias *alias, const struct Unit *unit)
{
    return alias->name_id && unit->kind == 1 && unit->race == alias->race &&
           unit->name == pool_name(alias->name_id);
}

static void prune(void)
{
    for (unsigned i = 0; i < UNIT_COUNT; ++i) {
        struct Alias *alias = &STATE->names.aliases[i];
        if (!alias_matches(alias, &ROSTER[i]))
            clear(alias, sizeof(*alias));
    }
}

/* Both fonts share the Latin and digit tokens. Keep other names in the
 * companion block and use the native name when displaying in another locale. */
static unsigned alias_is_displayable(const struct Alias *alias)
{
    if (alias->encoding == NAME_ENCODING)
        return alias->name[0] != 0;
    for (unsigned i = 0; i < 16 && alias->name[i]; i += 2) {
        const u16 token = (alias->name[i] << 8) | alias->name[i + 1];
        if (token != 0x4073 && (token < 0x80a6 || token > 0x80e3))
            return 0;
    }
    return alias->name[0] != 0;
}

__attribute__((noinline))
static const u8 *display_name(const struct Unit *unit)
{
    if (STATE->candidate == unit && STATE->stage == OFFERED && STATE->draft[0])
        return STATE->draft;
    if (STATE->names.magic == MAGIC && unit->kind == 1) {
        unsigned index = roster_index(unit);
        if (index < UNIT_COUNT) {
            const struct Alias *alias = &STATE->names.aliases[index];
            if (alias_matches(alias, unit) && alias_is_displayable(alias))
                return alias->name;
        }
    }
    return unit->name;
}

/* Only the recruit callback uses this name task. Native start/new-game and
 * clan name tasks keep their own callback and save buffers. */
static void copy_halfwords(volatile u16 *dest, const volatile u16 *src, unsigned bytes)
{
    for (unsigned i = 0; i < bytes / 2; ++i)
        dest[i] = src[i];
}

/* Only the keyboard text, BG maps and the editor's OBJ tiles overlap the
 * recruitment screen. Its BG0 wallpaper lies outside these ranges. */
static const struct { u32 offset, bytes; } graphics_ranges[] = {
    {0x5000, 0x2000}, {0x9800, 0x3000}, {0xe000, 0x1800}, {0x12800, 0x5800},
};

static void transfer_graphics(u16 *buffer, unsigned restore)
{
    for (unsigned i = 0; i < sizeof(graphics_ranges) / sizeof(graphics_ranges[0]); ++i) {
        u32 offset = graphics_ranges[i].offset;
        u16 *vram = (u16 *)(0x06000000 + offset);
        unsigned bytes = graphics_ranges[i].bytes;
        if (restore)
            copy_halfwords(vram, buffer, bytes);
        else
            copy_halfwords(buffer, vram, bytes);
        buffer += bytes / 2;
    }
}
_Static_assert(0x2000 + 0x3000 + 0x1800 + 0x5800 == GRAPHICS_BYTES, "graphics backup size");

static unsigned reserve_editor_memory(struct EditorSession *session, const u8 *scene)
{
    void *owner = MAIN_HEAP;
    const u8 *arena = RAM(const u8 *, 0x03002778);
    /* The recruit object is a suballocation of the native scene arena. */
    if ((u32)owner < 0x0200f390 || (u32)arena <= (u32)owner ||
        (u32)arena > STATE_ADDRESS - RECRUIT_SCENE_BYTES ||
        (u32)scene < (u32)arena ||
        (u32)scene - (u32)arena > RECRUIT_SCENE_BYTES - 0x1d10 ||
        HeapAllocationSize(owner, arena) < RECRUIT_SCENE_BYTES)
        return 0;
    void *graphics = HeapAllocate(owner, GRAPHICS_BYTES + EDITOR_HEAP_BYTES);
    if (!graphics)
        return 0;
    session->owner_heap = owner;
    session->graphics = graphics;
    session->editor_heap = InitHeap((u8 *)graphics + GRAPHICS_BYTES, EDITOR_HEAP_BYTES);
    return 1;
}

static void clear_keyboard_maps(struct EditorSession *session)
{
    volatile u16 *tile = (u16 *)0x06008000;
    copy_halfwords(session->blank_tile, tile, sizeof(session->blank_tile));
    for (unsigned i = 0; i < sizeof(session->blank_tile) / 2; ++i)
        tile[i] = 0;
    /* BG2 and BG3 scroll across two screen blocks each. Initialize their
     * offscreen halves before the native editor draws either window. */
    for (unsigned i = 0; i < 0x800; ++i) {
        ((volatile u16 *)0x06005000)[i] = 0;
        ((volatile u16 *)0x0600e000)[i] = 0;
    }
}

static unsigned supports_bank(void);

static void capture_draft(const struct NameEditor *editor)
{
    unsigned length = 0;
    clear(STATE->draft, NAME_BYTES);
    for (unsigned i = 0; i < 16; i += 2) {
        unsigned high = editor->name[i];
        unsigned low = editor->name[i + 1];
        if (!high)
            break;
        if (high < 0x80 && (high != 0x40 || low != 0x73)) {
            clear(STATE->draft, NAME_BYTES);
            return;
        }
        STATE->draft[i] = high;
        STATE->draft[i + 1] = low;
        if (high >= 0x80)
            length = i + 2;
    }
    clear(STATE->draft + length, NAME_BYTES - length);
}

static u32 recruit_editor(u32 task, struct NameEvent *event, struct NameEditor *editor)
{
    const unsigned state = event->state;
    const unsigned buttons = RAM(volatile u16, NAME_INPUT);
    const unsigned spelling = USE_PINYIN && editor->page == 0 && editor->spelling_length;
    if (state == 260 && (buttons & 8) && spelling) {
        SetSound(104);
        return 0;
    }
    if (state == 260 && (buttons & 4) && !spelling) {
        clear(STATE->draft, NAME_BYTES);
        event->state = 263;
        SetSound(104);
        return 0;
    }
    if (state == 256) {
        u8 backup[NAME_BYTES];
        copy(backup, LIVE_NAME, NAME_BYTES);
        copy(LIVE_NAME, STATE->scratch.naming.original, NAME_BYTES);
        u32 result = NATIVE(NAME_CALLBACK, u32, (u32, void *, void *))(task, event, editor);
        copy(LIVE_NAME, backup, NAME_BYTES);
        editor->portrait_unit = STATE->candidate;
        editor->portrait = NATIVE(0x080cb928, void *, (const struct Unit *))(STATE->candidate);
        return result;
    }
    if (state == 262 && editor->phase == 0) {
        capture_draft(editor);
        if (same(STATE->draft, STATE->scratch.naming.original, NAME_BYTES))
            clear(STATE->draft, NAME_BYTES);
        editor->reset = 0;
        ShowDialog(editor->window, 1, 8, (void *)0x030008b0, (void *)0x03000990,
                   5, 5, 19, 4, 928);
        SetDialogMode(2);
        editor->phase = 1;
        return 0;
    }
    if (state == 264) {
        event->state = 3;
        return 0;
    }
    return NATIVE(NAME_CALLBACK, u32, (u32, void *, void *))(task, event, editor);
}

void RecruitStep(u32 task, u8 *step)
{
    u8 *root = RAM(u8 *, 0x03002818);
    struct EditorSession *session = &STATE->scratch.naming;
    if (*step == 0 && (u32)root >= 0x0200f390 &&
        (u32)root <= STATE_ADDRESS - RECRUIT_SCENE_BYTES &&
        RAM(u32, 0x03000e54) == RECRUIT_SCENE_BYTES) {
        const struct Unit *slot = RAM(const struct Unit *, LIVE_SAVE + 0x2c78);
        const struct Unit *unit = RAM(const struct Unit *, (u32)root + 0x1d0c);
        if (STATE->stage == FRESH && (u32)slot >= FIRST_UNIT &&
            (u32)slot < FIRST_UNIT + sizeof(*slot)*UNIT_COUNT && slot->kind == 0 &&
            candidate_is_generic(unit) &&
            supports_bank() && prefill(session->original, unit->name) &&
            reserve_editor_memory(session, root)) {
            clear(STATE->draft, NAME_BYTES);
            clear(&session->event, sizeof(session->event));
            clear(session->editor, sizeof(session->editor));
            STATE->candidate = unit;
            STATE->recruit_step = step;
            session->event.caller = STATE->editor_caller;
            session->event.kind = 1;
            transfer_graphics(session->graphics, 0);
            clear_keyboard_maps(session);
            copy_halfwords(session->palette, PALETTE_SHADOW, sizeof(session->palette));
            copy(session->display, (const u8 *)0x03000940, sizeof(session->display));
            copy(session->surface_a, (const u8 *)0x030008b0, sizeof(session->surface_a));
            copy(session->surface_b, (const u8 *)0x03000990, sizeof(session->surface_b));
            RAM(u32, 0x030008b4) = 0x03000952;
            RAM(u32, 0x030008b8) = 0x03000954;
            RAM(u32, 0x03000994) = 0x03000956;
            RAM(u32, 0x03000998) = 0x03000958;
            RAM(u16, 0x03000946) = 0x5c08;
            RAM(u16, 0x03000948) = 0x4a09;
            for (unsigned i = 0; i < 4; ++i)
                ((u16 *)0x03000952)[i] = 0;
            /* Keep the native recruit wallpaper under the keyboard. */
            RAM(u16, 0x03000940) = 0x1d40;
            STATE->stage = EDITING;
        }
        if (STATE->stage == EDITING) {
            void *old_main_heap = MAIN_HEAP;
            void *old_window_heap = WINDOW_HEAP;
            MAIN_HEAP = session->editor_heap;
            WINDOW_HEAP = session->editor_heap;
            recruit_editor(task, &session->event, (struct NameEditor *)session->editor);
            MAIN_HEAP = old_main_heap;
            WINDOW_HEAP = old_window_heap;
            if (session->event.state >= 258 && session->event.state <= 264) {
                copy_halfwords(PALETTE_SHADOW + 0xa0, (const u16 *)0x0894ed1c, 32);
                copy_halfwords(PALETTE_SHADOW + 0xb0, (const u16 *)0x0841a0c0, 32);
                copy_halfwords(PALETTE_SHADOW + 0x100, (const u16 *)0x08419d60, 32);
                copy_halfwords(HARDWARE_PALETTE + 0xa0, PALETTE_SHADOW + 0xa0, 64);
                copy_halfwords(HARDWARE_PALETTE + 0x100, PALETTE_SHADOW + 0x100, 32);
            }
            if (session->event.state == 0)
                session->event.state = 256;
            if (session->event.state != 3)
                return;
            copy((u8 *)0x03000940, session->display, sizeof(session->display));
            copy((u8 *)0x030008b0, session->surface_a, sizeof(session->surface_a));
            copy((u8 *)0x03000990, session->surface_b, sizeof(session->surface_b));
            transfer_graphics(session->graphics, 1);
            HeapFree(session->owner_heap, session->graphics);
            copy_halfwords((u16 *)0x06008000, session->blank_tile, sizeof(session->blank_tile));
            copy_halfwords(PALETTE_SHADOW, session->palette, sizeof(session->palette));
            copy_halfwords(HARDWARE_PALETTE, session->palette, sizeof(session->palette));
            STATE->stage = OFFERED;
        }
    }
    if (*step == 254 || *step == 255) {
        STATE->candidate = 0;
        STATE->recruit_step = 0;
        STATE->stage = FRESH;
    }
    OriginalRecruit(task, step);
}

void *RecruitAccepted(void *destination, const void *source, unsigned bytes)
{
    CopyRecord(destination, source, bytes);
    const struct Unit *unit = destination;
    unsigned index = roster_index(unit);
    if (index < UNIT_COUNT && candidate_is_generic(source)) {
        if (STATE->names.magic != MAGIC) {
            clear(&STATE->names, sizeof(STATE->names));
            STATE->names.magic = MAGIC;
        }
        struct Alias *alias = &STATE->names.aliases[index];
        clear(alias, sizeof(*alias));
        if (STATE->candidate == source && STATE->stage == OFFERED) {
            STATE->stage = JOINED;
            if (STATE->draft[0]) {
                alias->name_id = pool_id(unit->name);
                alias->race = unit->race;
                alias->encoding = NAME_ENCODING;
                copy(alias->name, STATE->draft, NAME_BYTES);
            }
        }
    }
    STATE->candidate = 0;
    return destination;
}

static u8 *append_tokens(u8 *out, const u8 *text)
{
    while (*text) {
        const u8 token = *text++;
        *out++ = token;
        if (token & 0x80)
            *out++ = *text++;
    }
    return out;
}

const u8 *RecruitDialog(void *context, u32 page, u16 *index, u8 *flags)
{
    const u16 message = *index;
    const u8 *original = NATIVE(0x08018028, const u8 *, (void *, u32, u16 *, u8 *))(
        context, page, index, flags);
    if (!STATE->recruit_step)
        return original;
    const unsigned welcome = message == 21 && STATE->stage == OFFERED && *STATE->recruit_step == 2;
    const unsigned joined = message == 22 && STATE->stage == JOINED &&
                            (*STATE->recruit_step == 6 || *STATE->recruit_step == 7);
    if (page != 1 || !STATE->draft[0] || !(welcome || joined))
        return original;

    STATE->dialog[0] = 2;
    STATE->dialog[1] = welcome ? 0x20 : 0x10;
    u8 *out = (u8 *)&STATE->dialog[2];
    if (welcome)
        out = append_tokens(out, recruit_question_prefix);
    out = append_tokens(out, STATE->draft);
    if (welcome)
        copy(out, recruit_question_suffix, sizeof(recruit_question_suffix));
    else
        copy(out, recruit_joined_suffix, sizeof(recruit_joined_suffix));
    *index = 0;
    return (const u8 *)STATE->dialog;
}


const u8 *RenderNameFar(const struct Unit *unit, u8 field)
{
    if (field == 0)
        return display_name(unit);
    return NATIVE(0x080c7ea4, const u8 *, (const struct Unit *, u8))(unit, field);
}


void *AcceptFar(void *destination, const void *source, unsigned bytes)
{
    return RecruitAccepted(destination, source, bytes);
}


__attribute__((naked, used)) void DialogRestoreR3(void)
{
    __asm__("mov r3, ip\n b DialogFar");
}

const u8 *DialogFar(void *context, u32 page, u16 *index, u8 *flags)
{
    return RecruitDialog(context, page, index, flags);
}

static void recruit_heap(void *base, void **handle)
{
    unsigned bytes = STATE_ADDRESS - (u32)base;
    typedef void (*ClearBytes)(void *, unsigned);
    RAM(ClearBytes, 0x0836d4b8)(base, bytes);
    *handle = InitHeap(base, bytes);
}

void MenuHeap(void)
{
    recruit_heap((void *)0x020159d0, (void **)0x0200f434);
}

void MissionHeap(void)
{
    recruit_heap((void *)0x0201f550, (void **)0x0201f53c);
}

void SaveHeap(void)
{
    recruit_heap((void *)0x0200f3c4, (void **)0x0200f3bc);
}

static unsigned supports_bank(void)
{
    return RAM(void *, SAVE_DEVICE) && FlashId() == FLASH_ID_SANYO_1M;
}

static void switch_bank(u8 bank)
{
    RAM(volatile u8, 0x0e005555) = 0xaa;
    RAM(volatile u8, 0x0e002aaa) = 0x55;
    RAM(volatile u8, 0x0e005555) = 0xb0;
    RAM(volatile u8, 0x0e000000) = bank;
}

/* mGBA starts AFXE as Flash 512 Kbit and upgrades on the first Bank 1
 * selection. Restore Bank 0 before the native driver selects its descriptor. */

u16 IdentifyRecruitFlashFar(void)
{
    u16 id = FlashId();
    if (id == FLASH_ID_PANASONIC_512) {
        switch_bank(1);
        switch_bank(0);
        id = FlashId();
    }
    return id;
}

struct PointerAlias {
    const u8 *name;
    u8 race;
    u8 reserved[3];
    u8 text[NAME_BYTES];
};

struct ReadNames {
    u32 magic;
    u32 sequence;
    u32 native_crc;
    u32 names_crc;
    union {
        struct Alias slots[UNIT_COUNT];
        struct PointerAlias pointers[UNIT_COUNT];
    } records;
};

static void restore_preview_alias(const struct Unit *units, const struct Alias *alias)
{
    unsigned match = UNIT_COUNT;
    for (unsigned i = 0; i < UNIT_COUNT; ++i) {
        if (!alias_matches(alias, &units[i]))
            continue;
        if (match < UNIT_COUNT)
            return;
        match = i;
    }
    if (match < UNIT_COUNT)
        copy((u8 *)&STATE->names.aliases[match], (const u8 *)alias, sizeof(*alias));
}

static void normalize_restored_names(void)
{
    for (unsigned i = 0; i < UNIT_COUNT; ++i) {
        struct Alias *alias = &STATE->names.aliases[i];
        if (alias->encoding != ENCODING_CN)
            continue;
        for (unsigned j = 0; j < 16 && alias->name[j]; j += 2) {
            if (alias->name[j] == 0x8c && alias->name[j + 1] == 0x67) {
                alias->name[j] = 0x85; /* Obsolete preview glyph becomes 招. */
                alias->name[j + 1] = 0x70;
            }
        }
    }
}

static unsigned read_names(const u8 *image, u8 slot, u8 sector)
{
    if (!supports_bank())
        return 0;
    struct ReadNames *block = (struct ReadNames *)STATE->scratch.flash_page;
    switch_bank(1);
    NativeRead(sector, 0, block, sizeof(*block));
    switch_bank(0);
    if ((block->magic != MAGIC && block->magic != LEGACY_MAGIC) ||
        block->sequence != *(const u32 *)(image+8) ||
        block->native_crc != *(const u32 *)(image+12) || image[16] != slot)
        return 0;

    const struct Unit *units = (const struct Unit *)(image + (FIRST_UNIT - LIVE_SAVE));
    if (block->names_crc == NameCrc(block->records.slots, sizeof(block->records.slots), 0)) {
        if (block->magic == MAGIC)
            copy((u8 *)STATE->names.aliases, (const u8 *)block->records.slots,
                 sizeof(STATE->names.aliases));
        else
            for (unsigned i = 0; i < UNIT_COUNT; ++i)
                restore_preview_alias(units, &block->records.slots[i]);
    } else if (block->magic == LEGACY_MAGIC &&
               block->names_crc == NameCrc(block->records.pointers, sizeof(block->records.pointers), 0)) {
        for (unsigned i = 0; i < UNIT_COUNT; ++i) {
            const struct PointerAlias *old = &block->records.pointers[i];
            if (!old->name)
                continue;
            struct Alias alias;
            alias.name_id = pool_id(old->name);
            alias.race = old->race;
            alias.encoding = ENCODING_CN;
            copy(alias.name, old->text, NAME_BYTES);
            restore_preview_alias(units, &alias);
        }
    } else {
        return 0;
    }
    STATE->names.magic = MAGIC;
    normalize_restored_names();
    return 1;
}

__attribute__((noinline))
static u32 recruit_load(u8 slot, u8 *image, u32 caller)
{
    u32 status = OriginalLoad(slot, image);
    if (status == 1 && ((u32)image == LIVE_SAVE ||
        ((u32)image == 0x02003cb0 && (caller == 0x0813aa2d || caller == 0x0813aac7)))) {
        clear(STATE, sizeof(*STATE));
        u8 sectors[20];
        if (slot > 2 ||
            NATIVE(0x0813b060, u32, (u8, void *))(slot, sectors) != 4 ||
            !read_names(image, slot, sectors[2]))
            clear(&STATE->names, sizeof(STATE->names));
    }
    return status;
}

__attribute__((noinline))
static u32 recruit_save(u8 slot, u8 *image)
{
    u32 status = OriginalSave(slot, image);
    if (status != 1 || (u32)image != LIVE_SAVE || slot > 2 ||
        STATE->names.magic != MAGIC || !supports_bank())
        return status;

    prune();
    u8 sectors[20];
    if (NATIVE(0x0813b060, u32, (u8, void *))(slot, sectors) != 4)
        return status;
    STATE->names.sequence = RAM(u32, LIVE_SAVE+8);
    STATE->names.native_crc = RAM(u32, LIVE_SAVE+12);
    STATE->names.names_crc = NameCrc(STATE->names.aliases, sizeof(STATE->names.aliases), 0);
    u8 *page = STATE->scratch.flash_page;
    for (unsigned i = 0; i < FLASH_SECTOR_BYTES; ++i)
        page[i] = 0xff;
    copy(page, (const u8 *)&STATE->names, sizeof(STATE->names));
    switch_bank(1);
    u32 failed = NativeWrite(sectors[2], page);
    switch_bank(0);
    return failed ? 0 : status;
}


u32 LoadFar(u8 slot, u8 *image)
{
    return recruit_load(slot, image, (u32)__builtin_return_address(0));
}


u32 SaveFar(u8 slot, u8 *image)
{
    return recruit_save(slot, image);
}
