/* Optional adapter for the pinned US-CN name editor. No new font cells.
 * The two native keyboard pages remain addressable. While pinyin is active,
 * page one is borrowed and is regenerated before returning to English. */
#include "optional_name_pinyin_ui.h"
#include <stddef.h>

extern const struct PinyinTable gOptionalPinyinTable;
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;

enum { ORIGINAL_WORK_SIZE = 0x334, EXTENDED_WORK_SIZE = 0x3a0 };
struct NativePinyinState {
    struct NamePinyinUi ui;
    u32 initialized;
    u8 active;
    u8 header_ready;
    u16 *header_backup;
};
_Static_assert(sizeof(struct NativePinyinState) <=
               EXTENDED_WORK_SIZE - ORIGINAL_WORK_SIZE, "name work tail");

#define CALL(address, result, arguments) ((result (*) arguments)(address | 1u))
#define EDGE (*(volatile u16 *)0x03000004)
static void Consume(unsigned sound)
{
    CALL(0x080023d0, void, (void *))((void *)0x03000000);
    CALL(0x08141540, void, (unsigned))(sound);
}

static void PutToken(u8 *destination, u16 token)
{
    destination[0] = (u8)(token >> 8);
    destination[1] = (u8)token;
}

static unsigned PageByte(unsigned x, unsigned y)
{
    /* Native text output: row-major 8x16 strips, 21 strips per line. */
    return (y / 16 * 21 + x / 8) * 64 + y % 16 * 4 + x % 8 / 2;
}

static unsigned HeaderByte(unsigned x, unsigned y)
{
    unsigned index = y < 16 ? (x / 32) * 256 : 512 + (x / 32) * 128;
    unsigned yy = y < 16 ? y : y - 16;
    return index + (yy / 8 * 4 + x % 32 / 8) * 32 + yy % 8 * 4 + x % 8 / 2;
}

static void HeaderPixel(u8 *graphics, unsigned x, unsigned y, unsigned value)
{
    unsigned index = HeaderByte(x, y);
    unsigned shift = (x & 1) * 4;
    graphics[index] = (u8)((graphics[index] & ~(15 << shift)) | (value << shift));
}

static void HeaderGlyph(u8 *graphics, int active)
{
    const u8 *glyph = (const u8 *)0x08433330 + 0x125 * 128;
    unsigned x, y;
    for (y = 0; y < 16; ++y)
        for (x = 0; x < 16; ++x) {
            unsigned value = glyph[(x / 8) * 64 + y * 4 + x % 8 / 2];
            value = (value >> ((x & 1) * 4)) & 15;
            if (value)
                HeaderPixel(graphics, 12 + x, y + 5,
                            active ? value + 3 : value == 3 ? 5 : 10);
        }
}

static void RestoreHeader(struct NativePinyinState *state)
{
    unsigned index;
    if (!state->header_backup)
        return;
    for (index = 0; index < 384; ++index)
        ((volatile u16 *)0x06016b00)[index] = state->header_backup[index];
    for (index = 0; index < 16; ++index)
        ((volatile u16 *)0x05000360)[index] = state->header_backup[384 + index];
    CALL(0x08022854, void, (void *))(state->header_backup);
    state->header_backup = NULL;
}

static void UploadHeader(u8 *editor)
{
    u8 *graphics = *(u8 **)(editor + 0x2fc) + 0x4200;
    unsigned x, y;
    struct NativePinyinState *state = (void *)(editor + ORIGINAL_WORK_SIZE);
    if (!state->header_backup) {
        /* The original name field ends at OBJ VRAM16A80. This opt-in editor
         * reserves 16B00..16E00 and inactive palette11, backing both up and
         * restoring them at the original task's close/destruction boundary. */
        state->header_backup = CALL(0x08022840, void *, (unsigned))(800);
        if (!state->header_backup)
            return;
        for (x = 0; x < 384; ++x)
            state->header_backup[x] = ((volatile u16 *)0x06016b00)[x];
        for (x = 0; x < 16; ++x) {
            state->header_backup[384 + x] = ((volatile u16 *)0x05000360)[x];
            /* Actual BG3 inactive-tab palette, not OBJ5's same indices. */
            ((volatile u16 *)0x05000360)[x] = ((volatile u16 *)0x05000160)[x];
        }
    }
    for (x = 0; x < 768; ++x)
        graphics[x] = 0;
    if (state->active) {
        /* Preserve every pixel of the original selected-tab frame. */
        CALL(0x08005318, void, (const void *, void *, unsigned, unsigned))(
            (const void *)0x083c5454, graphics, 0, 1);
    } else {
        /* Clone the original inactive 123 tab directly from live BG3 tiles.
         * Its 40x24 silhouette and the original palette remain unchanged. */
        for (y = 0; y < 24; ++y)
            for (x = 0; x < 40; ++x) {
                unsigned sx = x + 40, sy = y + 8;
                u16 tile = ((volatile const u16 *)0x06005000)[sy / 8 * 32 + sx / 8];
                unsigned tx = tile & 0x400 ? 7 - sx % 8 : sx % 8;
                unsigned ty = tile & 0x800 ? 7 - sy % 8 : sy % 8;
                unsigned value = ((volatile const u8 *)0x06008000)[
                    (tile & 1023) * 32 + ty * 4 + tx / 2];
                HeaderPixel(graphics, x, y, (value >> ((tx & 1) * 4)) & 15);
            }
    }
    /* Replace only the label inside the cloned frame. The original Aa/123
     * graphics, palettes, tilemap and original selected sprite are untouched. */
    for (y = 6; y < 18; ++y)
        for (x = state->active ? 5 : 10; x < 32; ++x)
            HeaderPixel(graphics, x, y, state->active ? 8 : 15);
    HeaderGlyph(graphics, state->active);
    if (editor[0x2f4] >= 3)
        return;
    void *surface = CALL(0x0812b4e0, void *, (u8 *))(editor);
    CALL(0x08000adc, void, (void *, const void *, void *, unsigned))(
        surface, graphics, (void *)0x06016b00, 192);
}

static void Upload(u8 *editor)
{
    /* The original callback resets its three upload slots each tick.
     * A name redraw consumes one slot; these two consume the remaining two. */
    if (editor[0x2f4] >= 3)
        return;
    void *surface = CALL(0x0812b4e0, void *, (u8 *))(editor);
    CALL(0x0812b44c, void, (void *, void *, void *, u8))(
        surface, *(void **)(editor + 0x2fc), (void *)0x0600a280,
        editor[0x2f6]);
    struct NativePinyinState *state = (void *)(editor + ORIGINAL_WORK_SIZE);
    if (!state->active && editor[0x2f4] < 3) {
        surface = CALL(0x0812b4e0, void *, (u8 *))(editor);
        CALL(0x0812b41c, void, (void *, void *, u8))(
            surface, (void *)0x06016300, editor[0x2f6]);
    }
    UploadHeader(editor);
}

static void Render(u8 *editor, struct NativePinyinState *state)
{
    u16 keys[60];
    u8 stream[132];
    u8 *keyboard = *(u8 **)(editor + 0x304) + 120;
    u8 *graphics = *(u8 **)(editor + 0x2fc) + 0x2100;
    u8 *scratch = *(u8 **)(editor + 0x2fc) + 0x4200;
    unsigned cell, position = 0;
    NamePinyinBuildPage(&gOptionalPinyinTable, &state->ui, keys);
    for (cell = 0; cell < 60; ++cell) {
        PutToken(keyboard + cell * 2, keys[cell]);
        PutToken(stream + position, keys[cell]);
        position += 2;
        if (cell % 10 == 9 && cell != 59) {
            PutToken(stream + position, 0x406e);
            position += 2;
        }
    }
    PutToken(stream + position, 0x4063);
    for (cell = 0; cell < 0x2100; ++cell)
        scratch[cell] = graphics[cell] = 0;
    CALL(0x080161d4, void, (void *, void *, const u8 *, unsigned,
                           unsigned, unsigned, unsigned))(
        editor + 8, scratch, stream, 21, 0, 0, 1);
    /* All admitted native glyphs have empty source rows 14/15. Compact six
     * rows to 14 pixels, leaving an independent 12-pixel composition strip.
     * The original committed-name panel at screen y=136 is untouched. */
    unsigned y, x;
    for (y = 0; y < 84; ++y)
        for (x = 0; x < 168; x += 8) {
            unsigned source = PageByte(x, y / 14 * 16 + y % 14);
            unsigned destination = PageByte(x, y);
            *(u32 *)(graphics + destination) = *(u32 *)(scratch + source);
        }
    PutToken(stream, 0x8103); /* Native > */
    PutToken(stream + 2, 0x4073);
    for (cell = 0; cell < state->ui.composition.length; ++cell)
        PutToken(stream + 4 + cell * 2,
                 (u16)(0x80ca + state->ui.composition.letters[cell] - 'a'));
    PutToken(stream + 4 + cell * 2, 0x4063);
    for (cell = 0; cell < 21 * 64; ++cell)
        scratch[cell] = 0;
    CALL(0x080161d4, void, (void *, void *, const u8 *, unsigned,
                           unsigned, unsigned, unsigned))(
        editor + 8, scratch, stream, 21, 0, 0, 1);
    for (y = 84; y < 96; ++y)
        for (x = 0; x < 168; x += 8)
            *(u32 *)(graphics + PageByte(x, y)) =
                *(u32 *)(scratch + PageByte(x, y - 84 + 4));
    editor[0x310] = state->ui.column;
    editor[0x311] = state->ui.row;
    Upload(editor);
}

static void HandlePinyin(u8 *editor, struct NativePinyinState *state, u16 buttons)
{
    struct NamePinyinUi *ui = &state->ui;
    int redraw = 0;
    enum NamePinyinMove direction;
    if (buttons & 0xf0) {
        direction = buttons & 0x40 ? NAME_PINYIN_MOVE_UP :
                    buttons & 0x80 ? NAME_PINYIN_MOVE_DOWN :
                    buttons & 0x20 ? NAME_PINYIN_MOVE_LEFT :
                                    NAME_PINYIN_MOVE_RIGHT;
        NamePinyinMoveCursor(&gOptionalPinyinTable, ui, direction);
        Consume(108);
    } else if (buttons & 1) {
        u16 token;
        struct PinyinComposition previous = ui->composition;
        u16 previous_page = ui->candidate_page;
        /* Keep the old native cursor until its original A path has consumed
         * the selected BE token, including its exact width/length rollback. */
        if (NamePinyinAccept(&gOptionalPinyinTable, ui, &token)) {
            EDGE = 1;
            CALL(0x0812aac8, void, (u8 *))(editor);
        } else {
            if (ui->composition.length != previous.length &&
                ui->candidate_count == 0) {
                u16 ignored[60];
                ui->composition = previous;
                ui->candidate_page = previous_page;
                NamePinyinBuildPage(&gOptionalPinyinTable, ui, ignored);
                Consume(104);
            } else {
                Consume(100);
            }
        }
        redraw = 1;
    } else if (buttons & 2) {
        if (NamePinyinBackspace(&gOptionalPinyinTable, ui)) {
            Consume(104);
            redraw = 1;
        } else {
            EDGE = 2;
            CALL(0x0812aac8, void, (u8 *))(editor);
        }
    } else if (NamePinyinHandleSelectButton(&gOptionalPinyinTable, ui, buttons)) {
        Consume(102);
        redraw = 1;
    }
    editor[0x310] = ui->column;
    editor[0x311] = ui->row;
    if (redraw)
        Render(editor, state);
}

u32 NativePinyinCallback(u32 argument, u16 *event, u8 *editor)
{
    struct NativePinyinState *state =
        (struct NativePinyinState *)(editor + ORIGINAL_WORK_SIZE);
    u16 buttons = EDGE;
    unsigned previous_event = *event;
    int editing = previous_event == 0x104;
    if (previous_event == 0x109 || previous_event == 1)
        RestoreHeader(state);
    if (*event == 0) {
        u8 *bytes = (u8 *)state;
        unsigned index;
        for (index = 0; index < sizeof(*state); ++index)
            bytes[index] = 0;
        state->initialized = 0x50494e59;
    }
    if (editing) {
        /* Let the original callback keep START/confirmation, native cursor
         * animation, and the ordinary English A/B paths. */
        EDGE &= (u16)~(state->active ? 0x3f7 : 0x300);
    }
    u32 result = CALL(0x0812a084, u32, (u32, u16 *, u8 *))(
        argument, event, editor);
    if (!state->header_ready && (previous_event == 0x103 || editing)) {
        UploadHeader(editor);
        state->header_ready = 1;
    }
    if (!editing || *event != 0x104)
        return result;
    if (state->active)
        HandlePinyin(editor, state, buttons);
    /* Original direction/A/B consumes the edge before native tab handling. */
    if ((buttons & 0x300) && !(buttons & 0xf3) &&
        !(state->active && (buttons & 4))) {
        unsigned page = state->active ? 2 : editor[0x2f6];
        unsigned previous_page = page;
        Consume(102);
        if (state->active) {
            CALL(0x0812b468, void, (u8 *, unsigned))(editor, 1);
            CALL(0x0812ad14, void, (u8 *, unsigned))(editor, 1);
        }
        page = buttons & 0x100 ? (page == 2 ? 0 : page + 1) :
                               (page == 0 ? 2 : page - 1);
        state->active = page == 2;
        editor[0x2f6] = page == 2 ? 1 : (u8)page;
        if (previous_page == 2 || page == 2)
            editor[0x310] = editor[0x311] = 0;
        if (state->active) {
            state->ui.row = state->ui.column = 0;
            Render(editor, state);
        } else {
            Upload(editor);
        }
    }
    return result;
}

/* The nearby Thumb bridges preserve the original caller's ABI. */
void NativePinyinCursor(u8 *editor)
{
    struct NativePinyinState *state = (void *)(editor + ORIGINAL_WORK_SIZE);
    if (!state->active) {
        CALL(0x0812a91c, void, (u8 *))(editor);
        return;
    }
    unsigned phase = (u8)(editor[0x327] + 6);
    editor[0x327] = (u8)phase;
    CALL(0x08001cf0, void, (const void *, int, int, unsigned,
                           unsigned, unsigned, unsigned, unsigned,
                           unsigned, unsigned, unsigned))(
        (const void *)0x0851ba52,
        editor[0x310] * 16 - ((phase & 127) >> 5),
        editor[0x311] * 14 + 36, 0, 0, 0, 0, 0, 0, 0, 0);
}

void NativePinyinTabs(u8 *native_tab_field)
{
    u8 *editor = native_tab_field - 0x2f6;
    struct NativePinyinState *state = (void *)(editor + ORIGINAL_WORK_SIZE);
    const u16 third[] = {4, 0x4000, 0x8000, 0x0358,
                           0x4000, 0x8020, 0x0360,
                           0x4010, 0x4000, 0x0368,
                           0x4010, 0x4020, 0x036c};
    u16 sprite[13];
    unsigned index;
    if (!state->active)
        CALL(0x08001f34, void, (const void *, int, int, unsigned,
                               unsigned, unsigned, unsigned, unsigned,
                               unsigned, unsigned, unsigned))(
            (const void *)0x083a82ec, ((const u8 *)0x083a8295)[editor[0x2f6]],
            8, 0, 0, 0, 0, 0, 0, 0, 0);
    if (!state->header_backup)
        return;
    for (index = 0; index < 13; ++index)
        sprite[index] = third[index];
    for (index = 3; index < 13; index += 3)
        sprite[index] |= state->active ? 0x5400 : 0xb400;
    CALL(0x08001f34, void, (const void *, int, int, unsigned,
                           unsigned, unsigned, unsigned, unsigned,
                           unsigned, unsigned, unsigned))(
        sprite, 72, state->active ? 9 : 8, 0, 0, 0, 0, 0, 0, 0, 0);
}

/* Compiler-generated copies stay freestanding and never borrow engine BSS. */
void __aeabi_memcpy(void *destination, const void *source, unsigned size)
{
    u8 *out = destination;
    const u8 *in = source;
    while (size--)
        *out++ = *in++;
}
