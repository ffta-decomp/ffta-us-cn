#include "native.h"
#include "build_bindings.h"

#define LEGACY_NAME_BLOCK_MAGIC 0x314e5252u
#define NAME_BLOCK_MAGIC 0x324e5252u
#define ALTERNATE_NAME_BLOCK_MAGIC 0x334e5252u
#define SUSPEND_REF_MAGIC 0x31524d4eu /* NMR1 */
#define LIVE_NAME ((u8 *)0x02001f1c)
#define GRAPHICS_BYTES 0xc000u
#define EDITOR_HEAP_BYTES 0xe000u
#define RECRUIT_SCENE_BYTES 0xc600u
#define MAIN_HEAP RAM(void *, 0x0200f434)
#define WINDOW_HEAP RAM(void *, 0x020159c4)
#define FLASH_SECTOR_BYTES 4096u
#define PALETTE_SHADOW ((u16 *)0x03003860)
#define HARDWARE_PALETTE ((volatile u16 *)0x05000000)

enum {
    VRAM_BASE = 0x06000000,
    KEYBOARD_BLANK_TILE_VRAM = 0x06008000,
    KEYBOARD_BG2_MAP_VRAM = 0x06005000,
    KEYBOARD_BG3_MAP_VRAM = 0x0600e000,
    NATIVE_SCENE_ARENA_PTR = 0x03002778,
    NATIVE_RECRUIT_SCENE_PTR = 0x03002818,
    NATIVE_SCENE_ALLOCATION_SIZE = 0x03000e54,
    SCENE_WORK_RAM_START = 0x0200f390,
    DISPLAY_SHADOW_ADDRESS = 0x03000940,
    KEYBOARD_SURFACE_A_ADDRESS = 0x030008b0,
    KEYBOARD_SURFACE_B_ADDRESS = 0x03000990,
    MENU_HEAP_BASE = 0x020159d0,
    MISSION_HEAP_BASE = 0x0201f550,
    MISSION_HEAP_HANDLE = 0x0201f53c,
    SAVE_HEAP_BASE = 0x0200f3c4,
    SAVE_HEAP_HANDLE = 0x0200f3bc,
    NATIVE_CLEAR_BYTES_CALLBACK_PTR = 0x0836d4b8,
};

enum {
    FLASH_UNLOCK_ADDRESS_1 = 0x0e005555,
    FLASH_UNLOCK_ADDRESS_2 = 0x0e002aaa,
    FLASH_BANK_SELECT_ADDRESS = 0x0e000000,
    NATIVE_STAGED_LOAD_BUFFER = 0x02003cb0,
    NATIVE_LOAD_RETURN_SITE_A = 0x0813aa2d,
    NATIVE_LOAD_RETURN_SITE_B = 0x0813aac7,
};

enum {
    RESOLVE_UNIT_PORTRAIT_ADDRESS = 0x080cb928,
    NATIVE_DIALOG_TEXT_ADDRESS = 0x08018028,
    NATIVE_UNIT_FIELD_TEXT_ADDRESS = 0x080c7ea4,
    NATIVE_SAVE_SECTOR_LIST_ADDRESS = 0x0813b060,
    ORIGINAL_CLAN_NAMING = 0x0812b230,
    CREATE_SCENE_TASK = 0x08121b8c,
    ACTIVE_SCENE_ID = 0x02002192,
    OPENING_CLAN_SCENE = 10,
    OPENING_CLAN_SCRIPT = 0x089a7e51,
    OPENING_CLAN_NAME_PC = 0x7ed,
    NATIVE_NAME_TASK_BYTES = 820,
    FIRST_STARTER_SLOT = 1,
    LAST_STARTER_SLOT = 5,
};

enum {
    EDITOR_BUTTON_A = 1,
    EDITOR_BUTTON_SELECT = 1 << 2,
    EDITOR_BUTTON_START = 1 << 3,
    EDITOR_PROTAGONIST_LAYOUT = 1,
    EDITOR_TASK_COMPLETE_STATE = 3,
    EDITOR_INITIALIZE_STATE = 256,
    EDITOR_INPUT_STATE = 260,
    EDITOR_CONFIRM_STATE = 262,
    EDITOR_CLOSE_STATE = 263,
    EDITOR_RETURN_STATE = 264,
    NAME_CONFIRM_SHOW = 0,
    NAME_CONFIRM_WAIT = 1,
    NAME_DIALOG_FIXED_PAGE = 1,
    NAME_DIALOG_CONFIRM_RECORD = 8,
    NAME_DIALOG_MODE = 2,
    NAME_DIALOG_YES = 0,
    NAME_DIALOG_TILE_INDEX = 928,
    EDITOR_SURFACE_DATA_OFFSET = 20,
    EDITOR_CLEAR_SURFACE = 0x01000400, /* CpuSet fill, 1024 halfwords. */
    FLASH_UNLOCK_FIRST = 0xaa,
    FLASH_UNLOCK_SECOND = 0x55,
    FLASH_COMMAND_SELECT_BANK = 0xb0,
    SAVE_SEQUENCE_OFFSET = 8,
    SAVE_CHECKSUM_OFFSET = 12,
    SAVE_SLOT_OFFSET = 16,
    PRIMARY_SAVE_SECTOR_INDEX = 2,
    SAVE_SECTOR_IDS_OFFSET = 18,
    FLASH_SECTORS_PER_BANK = 16,
    SUSPEND_SLOT = 2,
    MESSAGE_ARGUMENT_OFFSET = 0x20d8,
    NAME_AREA_BYTES = 0xc00,
    EMPTY_NATIVE_TEXT = 0x0814a001, /* Terminator of the native save signature. */
};

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
    struct EditorSession *editor_session;
    const u8 *resolved_names[UNIT_COUNT];
    const u8 *native_names[UNIT_COUNT];
    u8 starter_slot;  /* Zero while the original clan editor owns the task. */
    u8 preserve_file_names;
    u8 protected_sector;
    u8 saving_message_owner;
    const u8 *saving_image;
    u32 matching_names;
};

enum { FRESH, EDITING, OFFERED, JOINED };
#define STATE ((struct Runtime *)STATE_ADDRESS)
#define ROSTER ((const struct Unit *)FIRST_UNIT)
/* The retail boot clear ends at 0x0203FC00. Keep all resident data below it. */
#define EDITOR_REQUEST_BYTES (sizeof(struct EditorSession) + GRAPHICS_BYTES + EDITOR_HEAP_BYTES)
_Static_assert(sizeof(struct Runtime) <= RESIDENT_END - STATE_ADDRESS, "reserved EWRAM");

/* Read from the ARM object by the builder. This section is not installed. */
__attribute__((used, section(".recruit_memory")))
static const u32 memory_usage[] = {
    STATE_ADDRESS, sizeof(struct Runtime), EDITOR_REQUEST_BYTES, FLASH_SECTOR_BYTES
};
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
    unsigned i = 0;
    for (; i < NAME_MAX_CELLS && *source; ++i) {
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
    return i;
}

/* Carry the token count into the padded native editor. Some valid CN
 * glyphs contain a zero low byte, which a byte-length routine would truncate. */
static void seed_editor(struct NameEditor *editor, const u8 *name)
{
    unsigned i = 0;
    while (i < NAME_MAX_CELLS && name[2 * i]) {
        copy(editor->name + 2 * i, name + 2 * i, 2);
        ++i;
    }
    editor->length = i;
    for (; i < sizeof(editor->name) / 2; ++i) {
        editor->name[2 * i] = 0x40;
        editor->name[2 * i + 1] = 0x73;
    }
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
    /* 264 = 8 × 33; the multiplier is the inverse of 33 modulo 2^32. */
    u32 offset = (u32)unit - FIRST_UNIT;
    _Static_assert(sizeof(struct Unit) == 8 * 33, "roster index stride");
    if ((offset & 7) || offset >= sizeof(*unit) * UNIT_COUNT)
        return UNIT_COUNT;
    u32 index = (offset >> 3) * 0x3e0f83e1u;
    return index < UNIT_COUNT ? index : UNIT_COUNT;
}

static unsigned alias_matches(const struct Alias *alias, const struct Unit *unit)
{
    return alias->name_id && alias->name_id <= NAME_POOL_COUNT && unit->kind == 1 && unit->race == alias->race &&
           unit->name == pool_name(alias->name_id);
}

static u32 names_in_image(const u8 *image)
{
    const struct Unit *units = (const struct Unit *)(image + (FIRST_UNIT - LIVE_SAVE));
    u32 mask = 0;
    for (unsigned i = 0; i < UNIT_COUNT; ++i) {
        struct Alias *alias = &STATE->names.aliases[i];
        if (alias_matches(alias, &units[i]))
            mask |= 1u << i;
        else if ((u32)image == LIVE_SAVE) {
            clear(alias, sizeof(*alias));
            STATE->native_names[i] = ROSTER[i].name;
            STATE->resolved_names[i] = ROSTER[i].name;
        }
    }
    return mask;
}

/* Both fonts share the Latin and digit tokens. Keep other names in the
 * companion block and use the native name when displaying in another locale. */
static unsigned alias_is_displayable(const struct Alias *alias)
{
    if (alias->encoding == NAME_ENCODING)
        return alias->name[0] != 0;
    for (unsigned i = 0; i < NAME_MAX_CELLS * 2 && alias->name[i]; i += 2) {
        const u16 token = (alias->name[i] << 8) | alias->name[i + 1];
        if (token != 0x4073 && (token < 0x80a6 || token > 0x80e3))
            return 0;
    }
    return alias->name[0] != 0;
}

static void resolve_roster_name(unsigned index, const struct Unit *unit)
{
    const struct Alias *alias = &STATE->names.aliases[index];
    STATE->native_names[index] = unit->name;
    STATE->resolved_names[index] =
        STATE->names.magic == NAME_BLOCK_MAGIC && alias_matches(alias, unit) && alias_is_displayable(alias)
        ? alias->name : unit->name;
}

__attribute__((noinline))
static const u8 *display_name(const struct Unit *unit)
{
    if (STATE->candidate == unit && STATE->stage == OFFERED && STATE->draft[0])
        return STATE->draft;
    if (STATE->names.magic == NAME_BLOCK_MAGIC && unit->kind == 1) {
        unsigned index = roster_index(unit);
        if (index < UNIT_COUNT && STATE->native_names[index] == unit->name) {
            const struct Alias *alias = &STATE->names.aliases[index];
            if (STATE->resolved_names[index] != alias->name || alias->race == unit->race)
                return STATE->resolved_names[index];
        }
    }
    return unit->name;
}

/* The recruit scene preserves its display while using its own editor task. */
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
        u16 *vram = (u16 *)(VRAM_BASE + offset);
        unsigned bytes = graphics_ranges[i].bytes;
        if (restore)
            copy_halfwords(vram, buffer, bytes);
        else
            copy_halfwords(buffer, vram, bytes);
        buffer += bytes / 2;
    }
}
_Static_assert(0x2000 + 0x3000 + 0x1800 + 0x5800 == GRAPHICS_BYTES, "graphics backup size");

static struct EditorSession *reserve_editor_memory(const u8 *scene)
{
    void *owner = MAIN_HEAP;
    const u8 *arena = RAM(const u8 *, NATIVE_SCENE_ARENA_PTR);
    /* The recruit object is a suballocation of the native scene arena. */
    if ((u32)owner < SCENE_WORK_RAM_START || (u32)arena <= (u32)owner ||
        (u32)arena > STATE_ADDRESS - RECRUIT_SCENE_BYTES ||
        (u32)scene < (u32)arena ||
        (u32)scene - (u32)arena > RECRUIT_SCENE_BYTES - 0x1d10 ||
        HeapAllocationSize(owner, arena) < RECRUIT_SCENE_BYTES)
        return 0;
    struct EditorSession *session = HeapAllocate(owner, EDITOR_REQUEST_BYTES);
    if (!session)
        return 0;
    session->owner_heap = owner;
    session->graphics = (u16 *)(session + 1);
    session->editor_heap = InitHeap((u8 *)session->graphics + GRAPHICS_BYTES, EDITOR_HEAP_BYTES);
    return session;
}

static void clear_keyboard_maps(struct EditorSession *session)
{
    volatile u16 *tile = (u16 *)KEYBOARD_BLANK_TILE_VRAM;
    copy_halfwords(session->blank_tile, tile, sizeof(session->blank_tile));
    for (unsigned i = 0; i < sizeof(session->blank_tile) / 2; ++i)
        tile[i] = 0;
    /* BG2 and BG3 scroll across two screen blocks each. Initialize their
     * offscreen halves before the native editor draws either window. */
    for (unsigned i = 0; i < 0x800; ++i) {
        ((volatile u16 *)KEYBOARD_BG2_MAP_VRAM)[i] = 0;
        ((volatile u16 *)KEYBOARD_BG3_MAP_VRAM)[i] = 0;
    }
}

static unsigned supports_bank(void);

/* A zero low byte is valid glyph data. Only the start of a cell can end a name. */
static unsigned valid_cell(const u8 *cell)
{
    return cell[0] >= 0x80 || (cell[0] == 0x40 && cell[1] == 0x73);
}

static unsigned valid_saved_name(const struct Alias *alias)
{
    if (!alias->name_id || alias->name_id > NAME_POOL_COUNT ||
        alias->encoding > ENCODING_US || !alias->name[0])
        return 0;
    for (unsigned i = 0; i < NAME_MAX_CELLS; ++i) {
        const u8 *cell = alias->name + 2 * i;
        if (!*cell)
            return 1;
        if (!valid_cell(cell))
            return 0;
    }
    return alias->name[2 * NAME_MAX_CELLS] == 0;
}

static unsigned capture_draft(const struct NameEditor *editor)
{
    clear(STATE->draft, NAME_BYTES);
    if (editor->length > NAME_MAX_CELLS)
        return 0;
    unsigned bytes = 0;
    for (unsigned i = 0; i < editor->length; ++i) {
        const u8 *cell = editor->name + 2 * i;
        if (!valid_cell(cell))
            return 0;
        if (cell[0] >= 0x80)
            bytes = 2 * (i + 1);
    }
    copy(STATE->draft, editor->name, bytes);
    return 1;
}

/* The retail keyboard can leave an uncommitted ninth narrow glyph in its
 * measurement cell. Keep that cell free in both companion editors. */
static unsigned reject_full_input(unsigned state, unsigned buttons, const struct NameEditor *editor)
{
    if (state == EDITOR_INPUT_STATE && (buttons & EDITOR_BUTTON_A) &&
        editor->length >= NAME_MAX_CELLS) {
        SetSound(104);
        return 1;
    }
    return 0;
}

static unsigned confirm_draft(struct NameEvent *event, struct NameEditor *editor)
{
    if (capture_draft(editor))
        return 1;
    seed_editor(editor, STATE->draft);
    editor->phase = NAME_CONFIRM_SHOW;
    event->state = EDITOR_INPUT_STATE;
    SetSound(104);
    return 0;
}

typedef u32 (*NameTask)(u32, struct NameEvent *, struct NameEditor *);
#define NativeNameTask NATIVE(NAME_CALLBACK, u32, (u32, struct NameEvent *, struct NameEditor *))

static u16 starter_name_id(const struct Unit *unit)
{
    return unit->kind == 1 ? pool_id(unit->name) : 0;
}

static unsigned next_starter(unsigned after)
{
    for (unsigned i = after + 1; i <= LAST_STARTER_SLOT; ++i)
        if (starter_name_id(&ROSTER[i]))
            return i;
    return 0;
}

/* The scheduler only carries event->state between frames. The native editor's
 * payload owns the caller pointer. Reinitialize that same task after it has
 * closed the previous editor and freed all of its windows and buffers. */
static void start_next_starter(u32 task, struct NameEvent *event,
                               struct NameEditor *editor, u8 *caller, unsigned slot)
{
    struct NameEvent init;
    clear(&init, sizeof(init));
    init.caller = caller;
    init.kind = EDITOR_PROTAGONIST_LAYOUT;
    clear(STATE->draft, NAME_BYTES);
    STATE->starter_slot = slot;
    NativeNameTask(task, &init, editor);
    event->state = EDITOR_INITIALIZE_STATE;
    caller[6] = 0;
}

static void close_starter_editor(struct NameEditor *editor)
{
    /* The native save-name close also regenerates party defaults. This
     * editor owns the keyboard allocations and display only. */
    for (unsigned i = 0; i < sizeof(editor->buffers) / sizeof(editor->buffers[0]); ++i)
        FreeNameBuffer(editor->buffers[i]);
    DestroyNameWindow(editor->window);

    const u16 fill = 0;
    BiosCpuSet(&fill, RAM(void *, KEYBOARD_SURFACE_A_ADDRESS + EDITOR_SURFACE_DATA_OFFSET), EDITOR_CLEAR_SURFACE);
    BiosCpuSet(&fill, RAM(void *, KEYBOARD_SURFACE_B_ADDRESS + EDITOR_SURFACE_DATA_OFFSET), EDITOR_CLEAR_SURFACE);
    RestoreNameDisplay();
    ConfigureNameBackground(2, 1, 0, 0, 0, (void *)KEYBOARD_BLANK_TILE_VRAM, (void *)KEYBOARD_BG3_MAP_VRAM);
    ConfigureNameBackground(3, 1, 1, 0, 0, (void *)KEYBOARD_BLANK_TILE_VRAM, (void *)KEYBOARD_BG2_MAP_VRAM);
}

static u32 opening_name_task(u32 task, struct NameEvent *event, struct NameEditor *editor)
{
    unsigned slot = STATE->starter_slot;
    const unsigned state = event->state;
    if (!slot) {
        u8 *caller = state ? editor->caller : event->caller;
        u32 result = NativeNameTask(task, event, editor);
        if (state == EDITOR_RETURN_STATE && event->state == EDITOR_TASK_COMPLETE_STATE) {
            unsigned next = next_starter(FIRST_STARTER_SLOT - 1);
            if (next)
                start_next_starter(task, event, editor, caller, next);
        }
        return result;
    }
    const struct Unit *unit = &ROSTER[slot];
    if (state == EDITOR_INITIALIZE_STATE) {
        u32 result = NativeNameTask(task, event, editor);
        /* The shared initializer allocates the editor. Seed its private
         * text before the later stages load and draw the keyboard. */
        u8 original[NAME_BYTES];
        prefill(original, unit->name);
        seed_editor(editor, original);
        editor->portrait_unit = unit;
        editor->portrait = NATIVE(RESOLVE_UNIT_PORTRAIT_ADDRESS, void *, (const struct Unit *))(unit);
        return result;
    }
    const unsigned buttons = RAM(volatile u16, NAME_INPUT);
    const unsigned spelling = USE_PINYIN && editor->page == 0 && editor->spelling_length;
    if (reject_full_input(state, buttons, editor))
        return 0;
    if (state == EDITOR_INPUT_STATE && (buttons & EDITOR_BUTTON_START) && spelling) {
        SetSound(104);
        return 0;
    }
    if (state == EDITOR_INPUT_STATE && (buttons & EDITOR_BUTTON_SELECT) && !spelling) {
        clear(STATE->draft, NAME_BYTES);
        event->state = EDITOR_CLOSE_STATE;
        SetSound(104);
        return 0;
    }
    if (state == EDITOR_CONFIRM_STATE) {
        editor->tick_flag = 0;
        if (editor->phase == NAME_CONFIRM_SHOW) {
            ShowDialog(editor->window, NAME_DIALOG_FIXED_PAGE, NAME_DIALOG_CONFIRM_RECORD,
                       (void *)KEYBOARD_SURFACE_A_ADDRESS, (void *)KEYBOARD_SURFACE_B_ADDRESS,
                       5, 5, 19, 4, NAME_DIALOG_TILE_INDEX);
            SetDialogMode(NAME_DIALOG_MODE);
            editor->phase = NAME_CONFIRM_WAIT;
        } else if ((u16)PollDialog()) {
            if ((u8)ReadDialogChoice() == NAME_DIALOG_YES) {
                u8 original[NAME_BYTES];
                if (!confirm_draft(event, editor))
                    return 0;
                prefill(original, unit->name);
                if (same(STATE->draft, original, NAME_BYTES))
                    clear(STATE->draft, NAME_BYTES);
                event->state = EDITOR_CLOSE_STATE;
            } else {
                event->state = EDITOR_INPUT_STATE;
            }
        }
        DrawNameConfirmation(editor);
        return 0;
    }

    if (state != EDITOR_RETURN_STATE)
        return NativeNameTask(task, event, editor);

    close_starter_editor(editor);
    u16 id = starter_name_id(unit);
    if (id && STATE->draft[0]) {
        STATE->names.magic = NAME_BLOCK_MAGIC;
        struct Alias *alias = &STATE->names.aliases[slot];
        alias->name_id = id;
        alias->race = unit->race;
        alias->encoding = NAME_ENCODING;
        copy(alias->name, STATE->draft, NAME_BYTES);
        resolve_roster_name(slot, unit);
    }
    unsigned next = next_starter(slot);
    if (next) {
        start_next_starter(task, event, editor, editor->caller, next);
    } else {
        clear(STATE->draft, NAME_BYTES);
        STATE->starter_slot = 0;
        editor->caller[6] = 1;
        event->state = EDITOR_TASK_COMPLETE_STATE;
    }
    return 0;
}

void ClanNameFar(u8 *caller)
{
    const u16 pc = RAM(u16, (u32)caller);
    if (!OPENING_ROSTER_NAMING || RAM(u16, ACTIVE_SCENE_ID) != OPENING_CLAN_SCENE ||
        RAM(u32, (u32)caller + 12) != OPENING_CLAN_SCRIPT ||
        (pc != OPENING_CLAN_NAME_PC && pc != OPENING_CLAN_NAME_PC + 2) || !supports_bank()) {
        NATIVE(ORIGINAL_CLAN_NAMING, void, (u8 *))(caller);
        return;
    }
    clear(STATE, sizeof(*STATE));
    struct NameEvent init;
    clear(&init, sizeof(init));
    init.caller = caller;
    caller[6] = 0;
    NATIVE(CREATE_SCENE_TASK, void *, (NameTask, u16, const void *, void *))(
        opening_name_task, USE_PINYIN ? NAME_TASK_BYTES : NATIVE_NAME_TASK_BYTES, &init, 0);
}

static u32 recruit_editor(u32 task, struct NameEvent *event, struct NameEditor *editor)
{
    const unsigned state = event->state;
    const unsigned buttons = RAM(volatile u16, NAME_INPUT);
    const unsigned spelling = USE_PINYIN && editor->page == 0 && editor->spelling_length;
    if (reject_full_input(state, buttons, editor))
        return 0;
    if (state == EDITOR_INPUT_STATE && (buttons & EDITOR_BUTTON_START) && spelling) {
        SetSound(104);
        return 0;
    }
    if (state == EDITOR_INPUT_STATE && (buttons & EDITOR_BUTTON_SELECT) && !spelling) {
        clear(STATE->draft, NAME_BYTES);
        event->state = EDITOR_CLOSE_STATE;
        SetSound(104);
        return 0;
    }
    if (state == EDITOR_INITIALIZE_STATE) {
        u8 backup[NAME_BYTES];
        copy(backup, LIVE_NAME, NAME_BYTES);
        copy(LIVE_NAME, STATE->editor_session->original, NAME_BYTES);
        u32 result = NATIVE(NAME_CALLBACK, u32, (u32, void *, void *))(task, event, editor);
        copy(LIVE_NAME, backup, NAME_BYTES);
        seed_editor(editor, STATE->editor_session->original);
        editor->portrait_unit = STATE->candidate;
        editor->portrait = NATIVE(RESOLVE_UNIT_PORTRAIT_ADDRESS, void *, (const struct Unit *))(STATE->candidate);
        return result;
    }
    if (state == EDITOR_CONFIRM_STATE && editor->phase == 0) {
        if (!confirm_draft(event, editor))
            return 0;
        if (same(STATE->draft, STATE->editor_session->original, NAME_BYTES))
            clear(STATE->draft, NAME_BYTES);
        editor->reset = 0;
        ShowDialog(editor->window, 1, 8, (void *)KEYBOARD_SURFACE_A_ADDRESS, (void *)KEYBOARD_SURFACE_B_ADDRESS,
                   5, 5, 19, 4, 928);
        SetDialogMode(2);
        editor->phase = 1;
        return 0;
    }
    if (state == EDITOR_RETURN_STATE) {
        event->state = 3;
        return 0;
    }
    return NATIVE(NAME_CALLBACK, u32, (u32, void *, void *))(task, event, editor);
}

void RecruitStep(u32 task, u8 *step)
{
    u8 *root = RAM(u8 *, NATIVE_RECRUIT_SCENE_PTR);
    struct EditorSession *session = STATE->editor_session;
    if (*step == 0 && (u32)root >= SCENE_WORK_RAM_START &&
        (u32)root <= STATE_ADDRESS - RECRUIT_SCENE_BYTES &&
        RAM(u32, NATIVE_SCENE_ALLOCATION_SIZE) == RECRUIT_SCENE_BYTES) {
        const struct Unit *slot = RAM(const struct Unit *, LIVE_SAVE + 0x2c78);
        const struct Unit *unit = RAM(const struct Unit *, (u32)root + 0x1d0c);
        u8 original[NAME_BYTES];
        if (STATE->stage == FRESH && (u32)slot >= FIRST_UNIT &&
            (u32)slot < FIRST_UNIT + sizeof(*slot)*UNIT_COUNT && slot->kind == 0 &&
            candidate_is_generic(unit) &&
            supports_bank() && prefill(original, unit->name) &&
            (session = reserve_editor_memory(root))) {
            STATE->editor_session = session;
            copy(session->original, original, NAME_BYTES);
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
            copy(session->display, (const u8 *)DISPLAY_SHADOW_ADDRESS, sizeof(session->display));
            copy(session->surface_a, (const u8 *)KEYBOARD_SURFACE_A_ADDRESS, sizeof(session->surface_a));
            copy(session->surface_b, (const u8 *)KEYBOARD_SURFACE_B_ADDRESS, sizeof(session->surface_b));
            RAM(u32, 0x030008b4) = 0x03000952;
            RAM(u32, 0x030008b8) = 0x03000954;
            RAM(u32, 0x03000994) = 0x03000956;
            RAM(u32, 0x03000998) = 0x03000958;
            RAM(u16, 0x03000946) = 0x5c08;
            RAM(u16, 0x03000948) = 0x4a09;
            for (unsigned i = 0; i < 4; ++i)
                ((u16 *)0x03000952)[i] = 0;
            /* Keep the native recruit wallpaper under the keyboard. */
            RAM(u16, DISPLAY_SHADOW_ADDRESS) = 0x1d40;
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
            copy((u8 *)DISPLAY_SHADOW_ADDRESS, session->display, sizeof(session->display));
            copy((u8 *)KEYBOARD_SURFACE_A_ADDRESS, session->surface_a, sizeof(session->surface_a));
            copy((u8 *)KEYBOARD_SURFACE_B_ADDRESS, session->surface_b, sizeof(session->surface_b));
            transfer_graphics(session->graphics, 1);
            copy_halfwords((u16 *)KEYBOARD_BLANK_TILE_VRAM, session->blank_tile, sizeof(session->blank_tile));
            copy_halfwords(PALETTE_SHADOW, session->palette, sizeof(session->palette));
            copy_halfwords(HARDWARE_PALETTE, session->palette, sizeof(session->palette));
            HeapFree(session->owner_heap, session);
            STATE->editor_session = 0;
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
    if (index < UNIT_COUNT) {
        if (STATE->names.magic != NAME_BLOCK_MAGIC) {
            clear(&STATE->names, sizeof(STATE->names));
            STATE->names.magic = NAME_BLOCK_MAGIC;
        }
        struct Alias *alias = &STATE->names.aliases[index];
        clear(alias, sizeof(*alias));
        if (candidate_is_generic(source) && STATE->candidate == source && STATE->stage == OFFERED) {
            STATE->stage = JOINED;
            if (STATE->draft[0]) {
                alias->name_id = pool_id(unit->name);
                alias->race = unit->race;
                alias->encoding = NAME_ENCODING;
                copy(alias->name, STATE->draft, NAME_BYTES);
            }
        }
    }
    if (index < UNIT_COUNT)
        resolve_roster_name(index, unit);
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
    const u8 *original = NATIVE(NATIVE_DIALOG_TEXT_ADDRESS, const u8 *, (void *, u32, u16 *, u8 *))(
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
    return NATIVE(NATIVE_UNIT_FIELD_TEXT_ADDRESS, const u8 *, (const struct Unit *, u8))(unit, field);
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
    RAM(ClearBytes, NATIVE_CLEAR_BYTES_CALLBACK_PTR)(base, bytes);
    *handle = InitHeap(base, bytes);
}

void MenuHeap(void)
{
    recruit_heap((void *)MENU_HEAP_BASE, (void **)0x0200f434);
}

void MissionHeap(void)
{
    recruit_heap((void *)MISSION_HEAP_BASE, (void **)MISSION_HEAP_HANDLE);
}

void SaveHeap(void)
{
    recruit_heap((void *)SAVE_HEAP_BASE, (void **)SAVE_HEAP_HANDLE);
}

static unsigned supports_bank(void)
{
    return RAM(void *, SAVE_DEVICE) && FlashId() == FLASH_ID_SANYO_1M;
}

static void switch_bank(u8 bank)
{
    RAM(volatile u8, FLASH_UNLOCK_ADDRESS_1) = FLASH_UNLOCK_FIRST;
    RAM(volatile u8, FLASH_UNLOCK_ADDRESS_2) = FLASH_UNLOCK_SECOND;
    RAM(volatile u8, FLASH_UNLOCK_ADDRESS_1) = FLASH_COMMAND_SELECT_BANK;
    RAM(volatile u8, FLASH_BANK_SELECT_ADDRESS) = bank;
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

/* The rest of each slot's 4 KiB extension page belongs to future versions. */
struct SuspendNameRef {
    u32 magic;
    u16 name_id;
    u8 owner;  /* One-based physical roster slot. */
    u8 race;
    u32 crc;
};
_Static_assert(sizeof(struct ReadNames) <= NAME_AREA_BYTES, "legacy name bank");
_Static_assert(NAME_AREA_BYTES + sizeof(struct SuspendNameRef) <= FLASH_SECTOR_BYTES, "suspend metadata");
_Static_assert(sizeof(struct SuspendNameRef) == 12, "suspend name reference");

static void read_extension(u8 sector, u32 offset, void *out, u32 size)
{
    switch_bank(1);
    NativeRead(sector, offset, out, size);
    switch_bank(0);
}

enum RecordLayout { INVALID_RECORDS, SLOT_RECORDS, POINTER_RECORDS };

static enum RecordLayout read_record_layout(u8 sector, unsigned alternate, u32 sequence, u32 crc,
                                             struct ReadNames *block)
{
    if (sector >= FLASH_SECTORS_PER_BANK)
        return INVALID_RECORDS;
    read_extension(sector, 0, block, sizeof(*block));
    if ((block->magic != LEGACY_NAME_BLOCK_MAGIC &&
         block->magic != (alternate ? ALTERNATE_NAME_BLOCK_MAGIC : NAME_BLOCK_MAGIC)) ||
        block->sequence != sequence || block->native_crc != crc)
        return INVALID_RECORDS;
    if (block->names_crc == NameCrc(block->records.slots, sizeof(block->records.slots), 0))
        return SLOT_RECORDS;
    if (block->magic == LEGACY_NAME_BLOCK_MAGIC &&
        block->names_crc == NameCrc(block->records.pointers, sizeof(block->records.pointers), 0))
        return POINTER_RECORDS;
    return INVALID_RECORDS;
}

/* Older preview ROMs could serialize this display-only pointer. Recognize
 * exact record starts only; the native argument is also used for numbers. */
static unsigned normalize_message_argument(u8 *image)
{
    const struct Unit *units = (const struct Unit *)(image + (FIRST_UNIT - LIVE_SAVE));
    const u8 **argument = (const u8 **)(image + MESSAGE_ARGUMENT_OFFSET);
    for (unsigned i = 0; i < UNIT_COUNT; ++i) {
        if (*argument == STATE->names.aliases[i].name) {
            *argument = units[i].kind == 1 && pool_id(units[i].name)
                      ? units[i].name : (const u8 *)EMPTY_NATIVE_TEXT;
            return i + 1;
        }
    }
    return 0;
}

static void restore_message_argument(u8 *image, unsigned owner)
{
    if (!owner || owner > UNIT_COUNT)
        return;
    unsigned i = owner - 1;
    const u8 **argument = (const u8 **)(image + MESSAGE_ARGUMENT_OFFSET);
    if (*argument == STATE->native_names[i] &&
        STATE->resolved_names[i] == STATE->names.aliases[i].name)
        *argument = STATE->resolved_names[i];
}

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
        if (!valid_saved_name(alias)) {
            clear(alias, sizeof(*alias));
            continue;
        }
        if (alias->encoding != ENCODING_CN)
            continue;
        for (unsigned j = 0; j < NAME_MAX_CELLS * 2 && alias->name[j]; j += 2) {
            if (alias->name[j] == 0x8c && alias->name[j + 1] == 0x67) {
                alias->name[j] = 0x85; /* Obsolete preview glyph becomes 招. */
                alias->name[j + 1] = 0x70;
            }
        }
    }
}

static unsigned read_names(u8 *image, u8 slot, u8 sector, unsigned alternate)
{
    struct ReadNames buffer;
    struct ReadNames *block = &buffer;
    if (image[SAVE_SLOT_OFFSET] != slot)
        return 0;
    enum RecordLayout layout = read_record_layout(sector, alternate,
        *(const u32 *)(image + SAVE_SEQUENCE_OFFSET), *(const u32 *)(image + SAVE_CHECKSUM_OFFSET), block);
    if (layout == INVALID_RECORDS)
        return 0;
    const struct Unit *units = (const struct Unit *)(image + (FIRST_UNIT - LIVE_SAVE));
    if (layout == SLOT_RECORDS) {
        if (block->magic != LEGACY_NAME_BLOCK_MAGIC)
            copy((u8 *)STATE->names.aliases, (const u8 *)block->records.slots,
                 sizeof(STATE->names.aliases));
        else
            for (unsigned i = 0; i < UNIT_COUNT; ++i)
                restore_preview_alias(units, &block->records.slots[i]);
    } else {
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
    }
    STATE->names.magic = NAME_BLOCK_MAGIC;
    normalize_restored_names();
    for (unsigned i = 0; i < UNIT_COUNT; ++i)
        resolve_roster_name(i, &units[i]);
    if (slot == SUSPEND_SLOT && block->magic != LEGACY_NAME_BLOCK_MAGIC) {
        struct SuspendNameRef ref;
        read_extension(sector, NAME_AREA_BYTES, &ref, sizeof(ref));
        if (ref.magic == SUSPEND_REF_MAGIC && ref.owner && ref.owner <= UNIT_COUNT &&
            ref.crc == NameCrc(&ref, 8, block->native_crc)) {
            const struct Alias *alias = &STATE->names.aliases[ref.owner - 1];
            if (ref.name_id == alias->name_id && ref.race == alias->race)
                restore_message_argument(image, ref.owner);
        }
    }
    return 1;
}

__attribute__((noinline))
static u32 recruit_load(u8 slot, u8 *image, u32 caller)
{
    u32 status = OriginalLoad(slot, image);
    if (status == 1 && ((u32)image == LIVE_SAVE ||
        ((u32)image == NATIVE_STAGED_LOAD_BUFFER && (caller == NATIVE_LOAD_RETURN_SITE_A || caller == NATIVE_LOAD_RETURN_SITE_B)))) {
        clear(STATE, sizeof(*STATE));
        unsigned legacy_owner = slot == SUSPEND_SLOT ? normalize_message_argument(image) : 0;
        u8 sectors[20];
        if (slot > 2 || !supports_bank() ||
            NATIVE(NATIVE_SAVE_SECTOR_LIST_ADDRESS, u32, (u8, void *))(slot, sectors) != 4 ||
            (!read_names(image, slot, sectors[PRIMARY_SAVE_SECTOR_INDEX], 0) &&
             !read_names(image, slot, sectors[PRIMARY_SAVE_SECTOR_INDEX + 1], 1)))
            clear(&STATE->names, sizeof(STATE->names));
        else if (legacy_owner)
            restore_message_argument(image, legacy_owner);
    }
    return status;
}

/* Keep the full sector on the synchronous writer's stack. File menus own no
 * live EWRAM heap here. Guard at the call site before reserving the sector. */
__attribute__((noinline))
static u32 write_sector(u8 sector, u32 magic)
{
    union {
        u8 bytes[FLASH_SECTOR_BYTES];
        struct NameBlock names;
    } page;
    if (STATE->protected_sector < FLASH_SECTORS_PER_BANK)
        read_extension(STATE->protected_sector, 0, &page, sizeof(page));
    else
        for (unsigned i = 0; i < sizeof(page); ++i)
            page.bytes[i] = 0xff;

    if (STATE->preserve_file_names) {
        /* Retain even pointer-layout RRN1 records until a normal load migrates them. */
        if (page.names.magic == LEGACY_NAME_BLOCK_MAGIC)
            magic = LEGACY_NAME_BLOCK_MAGIC;
    } else {
        if (page.names.magic == LEGACY_NAME_BLOCK_MAGIC)
            for (unsigned i = sizeof(struct NameBlock); i < sizeof(struct ReadNames); ++i)
                page.bytes[i] = 0xff;
        for (unsigned i = 0; i < UNIT_COUNT; ++i) {
            struct Alias *out = &page.names.aliases[i];
            if (STATE->matching_names & (1u << i))
                copy((u8 *)out, (const u8 *)&STATE->names.aliases[i], sizeof(*out));
            else
                clear(out, sizeof(*out));
        }
        page.names.names_crc = NameCrc(page.names.aliases, sizeof(page.names.aliases), 0);
    }
    const u8 *image = STATE->saving_image;
    page.names.magic = magic;
    page.names.sequence = *(const u32 *)(image + SAVE_SEQUENCE_OFFSET);
    page.names.native_crc = *(const u32 *)(image + SAVE_CHECKSUM_OFFSET);
    if (image[SAVE_SLOT_OFFSET] == SUSPEND_SLOT) {
        struct SuspendNameRef ref;
        clear(&ref, sizeof(ref));
        unsigned owner = STATE->saving_message_owner;
        if (owner && owner <= UNIT_COUNT) {
            const struct Alias *alias = &STATE->names.aliases[owner - 1];
            ref.magic = SUSPEND_REF_MAGIC;
            ref.name_id = alias->name_id;
            ref.owner = owner;
            ref.race = alias->race;
            ref.crc = NameCrc(&ref, 8, page.names.native_crc);
        }
        copy(page.bytes + NAME_AREA_BYTES, (const u8 *)&ref, sizeof(ref));
    }
    switch_bank(1);
    u32 failed = NativeWrite(sector, &page);
    switch_bank(0);
    return failed;
}

/* The native writer programs logical pages 3, 2, 1, then the header.
 * By the header call its sequence, CRC and physical sector list are final. */
u32 PrepareNameSector(u32 sector, const u8 *page)
{
    if (page != STATE->saving_image || !page)
        return 0;
    if (sector >= FLASH_SECTORS_PER_BANK || page[SAVE_SECTOR_IDS_OFFSET] != sector)
        return 1;
    u32 magic = NAME_BLOCK_MAGIC;
    if (sector == STATE->protected_sector) {
        sector = page[SAVE_SECTOR_IDS_OFFSET + 1];
        if (sector >= FLASH_SECTORS_PER_BANK || sector == STATE->protected_sector)
            return 1;
        magic = ALTERNATE_NAME_BLOCK_MAGIC;
    }
    u32 stack;
    __asm__ volatile ("mov %0, sp" : "=r"(stack));
    /* Leaves at least 0x600 bytes above the native IWRAM work data at 0x616C
     * even after the sector, including nested native Flash calls. */
    return stack < FLASH_STACK_MIN || stack > 0x03007ec0u ? 1 : write_sector(sector, magic);
}

/* Keep the last companion copy for the selected slot until its replacement
 * header is committed. Both possible pages belong to the native slot. */
__attribute__((noinline))
static u8 previous_name_sector(u8 slot)
{
    u8 sectors[20];
    if (NATIVE(NATIVE_SAVE_SECTOR_LIST_ADDRESS, u32, (u8, void *))(slot, sectors) != 4)
        return FLASH_SECTORS_PER_BANK;
    u8 primary = sectors[PRIMARY_SAVE_SECTOR_INDEX];
    if (primary >= FLASH_SECTORS_PER_BANK)
        return FLASH_SECTORS_PER_BANK;
    u32 native_key[2];
    struct ReadNames block;
    NativeRead(primary, SAVE_SEQUENCE_OFFSET, native_key, sizeof(native_key));
    for (unsigned i = 0; i < 2; ++i) {
        u8 sector = sectors[PRIMARY_SAVE_SECTOR_INDEX + i];
        if (read_record_layout(sector, i, native_key[0], native_key[1], &block) != INVALID_RECORDS)
            return sector;
    }
    return FLASH_SECTORS_PER_BANK;
}

__attribute__((noinline))
static u32 recruit_save(u8 slot, u8 *image, unsigned from_file)
{
    if (!image || slot > SUSPEND_SLOT)
        return OriginalSave(slot, image);
    unsigned live_names = !from_file && STATE->names.magic == NAME_BLOCK_MAGIC;
    if (!supports_bank())
        return live_names ? 0 : OriginalSave(slot, image);

    /* The ending owns the previously committed *target file*. All other
     * native writers submit a live roster or a snapshot of that roster. */
    STATE->protected_sector = previous_name_sector(slot);
    unsigned owner = normalize_message_argument(image);
    /* Commit an empty name block for an unnamed file too. A recycled sector
     * must never reveal an old alias if its native header happens to repeat. */
    STATE->preserve_file_names = from_file && STATE->protected_sector < FLASH_SECTORS_PER_BANK;
    STATE->matching_names = live_names ? names_in_image(image) : 0;
    STATE->saving_message_owner = slot == SUSPEND_SLOT ? owner : 0;
    STATE->saving_image = image;
    u32 status = OriginalSave(slot, image);
    STATE->saving_image = 0;
    STATE->saving_message_owner = 0;
    if ((u32)image == LIVE_SAVE)
        restore_message_argument(image, owner);
    return status;
}

u32 LoadFar(u8 slot, u8 *image)
{
    return recruit_load(slot, image, (u32)__builtin_return_address(0));
}


u32 SaveFar(u8 slot, u8 *image)
{
    return recruit_save(slot, image, (u32)__builtin_return_address(0) == ENDING_FILE_RETURN);
}
