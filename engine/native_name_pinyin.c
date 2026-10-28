/* Optional adapter for the pinned US-CN name editor. No new font cells.
 * Pinyin replaces native keyboard page zero. The original second page and
 * both native tab renderers/resources are retained; there is no extra tab. */
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

static void Upload(u8 *editor)
{
    /* The original callback resets its three upload slots each tick. Use one
     * for the keyboard and one for its original selected-tab resource. */
    if (editor[0x2f4] >= 3)
        return;
    void *surface = CALL(0x0812b4e0, void *, (u8 *))(editor);
    CALL(0x0812b44c, void, (void *, void *, void *, u8))(
        surface, *(void **)(editor + 0x2fc), (void *)0x0600a280,
        editor[0x2f6]);
    if (editor[0x2f4] < 3) {
        surface = CALL(0x0812b4e0, void *, (u8 *))(editor);
        CALL(0x0812b41c, void, (void *, void *, u8))(
            surface, (void *)0x06016300, editor[0x2f6]);
    }
}

static void Render(u8 *editor, struct NativePinyinState *state, int upload)
{
    u16 keys[60];
    u8 stream[132];
    u8 *keyboard = *(u8 **)(editor + 0x304);
    u8 *graphics = *(u8 **)(editor + 0x2fc);
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
    if (upload)
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
        Render(editor, state, 1);
}

u32 NativePinyinCallback(u32 argument, u16 *event, u8 *editor)
{
    struct NativePinyinState *state =
        (struct NativePinyinState *)(editor + ORIGINAL_WORK_SIZE);
    u16 buttons = EDGE;
    unsigned previous_event = *event;
    int editing = previous_event == 0x104;
    if (*event == 0) {
        u8 *bytes = (u8 *)state;
        unsigned index;
        for (index = 0; index < sizeof(*state); ++index)
            bytes[index] = 0;
        state->initialized = 0x50494e59;
        state->active = 1;
    }
    if (previous_event == 0x102) {
        /* Both native page caches are now initialized. Replace page zero
         * before the original open path copies it to VRAM. Its display and
         * tab setup remain entirely native; no extra upload slot is used. */
        editor[0x2f6] = 0;
        state->active = 1;
        Render(editor, state, 0);
    }
    if (editing) {
        state->active = editor[0x2f6] == 0;
        /* Keep native START/confirmation and second-page A/B handling. */
        EDGE &= (u16)~(state->active ? 0x3f7 : 0x300);
    }
    u32 result = CALL(0x0812a084, u32, (u32, u16 *, u8 *))(
        argument, event, editor);
    if (!editing || *event != 0x104)
        return result;
    if (state->active)
        HandlePinyin(editor, state, buttons);
    /* Original direction/A/B consumes the edge before native tab handling. */
    if ((buttons & 0x300) && !(buttons & 0xf3) &&
        !(state->active && (buttons & 4))) {
        Consume(102);
        editor[0x2f6] ^= 1;
        state->active = editor[0x2f6] == 0;
        editor[0x310] = editor[0x311] = 0;
        if (state->active) {
            state->ui.row = state->ui.column = 0;
            Render(editor, state, 1);
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

/* Compiler-generated copies stay freestanding and never borrow engine BSS. */
void __aeabi_memcpy(void *destination, const void *source, unsigned size)
{
    u8 *out = destination;
    const u8 *in = source;
    while (size--)
        *out++ = *in++;
}
