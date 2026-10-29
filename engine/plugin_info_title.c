/* Optional title callback, selected through a complete source replacement.
 * Original labels, color-mode submenu and game transitions retain native APIs.
 * No native instructions or resource pointers are patched at runtime. */
#include <stdint.h>
#include "plugin_info_assets.h"
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
#define CALL(address, result, arguments) ((result (*) arguments)((address) | 1u))
#define ROOT (*(u8 **)0x0200f3b0)
#define KEYS ((volatile u16 *)0x03000000)
struct InfoState { u8 active, page, scroll, loaded; u16 display_control, blend_control, blend_alpha, reserved; };
_Static_assert(sizeof(struct InfoState) == 12, "title-owned tail");

static void Sound(unsigned cue)
{
    CALL(0x08141540, void, (unsigned))(cue);
}
static void Copy(const u16 *source, u16 *destination, unsigned halfwords)
{
    CALL(0x0814186c, void, (const void *, void *, unsigned))(
        source, destination, halfwords);
}
static void Palette(void)
{
    const u16 *palette = CALL(0x080cbabc, const u16 *, (unsigned))(0);
    /* Reuse native menu palette zero, including the selected color mode.
     * Graphics use its blue index 6 and white frame/text index 4. */
    Copy(palette, (u16 *)0x03003c40, 16);
}
static void Sprite(unsigned x, unsigned y, unsigned tile, unsigned wide, unsigned semi, unsigned palette)
{
    unsigned bank = *(u8 *)0x03000028;
    volatile u32 *counts = (volatile u32 *)0x03000020;
    u32 *begin;
    u32 *out;
    unsigned index;
    if (bank > 1) return;
    index = counts[bank];
    if (index >= 128) return;
    begin = (u32 *)(0x03000030 + bank * 1024);
    out = begin + index * 2;
    out[0] = (y & 255) | (wide ? 0x4000 : 0) | (semi ? 0x0400 : 0) |
             (((x & 511) | 0x8000) << 16);
    out[1] = tile | (palette << 12); /* OBJ priority zero. */
    counts[bank] = index + 1;
}
static void DrawNative(const void *asset, unsigned x, unsigned y, unsigned color)
{
    CALL(0x08001f34, void,
         (const void *, int, int, unsigned, unsigned, unsigned, unsigned,
          unsigned, unsigned, unsigned, unsigned))(
        asset, x, y, 0, 0, 0, 0, 0, 0, 0, color);
}
static void Label(struct InfoState *info)
{
    if (info->loaded != 1) {
        Copy(gPluginInfoLabel, (u16 *)0x06013000, 512);
        info->loaded = 1;
    }
    Palette();
    Sprite(154, 110, 384, 1, 0, ROOT[0x8962] == 3 ? 3 : 1);
    Sprite(186, 110, 400, 1, 0, ROOT[0x8962] == 3 ? 3 : 1);
}
static void Details(struct InfoState *info, unsigned accept_input)
{
    unsigned row, column, index;
    if (accept_input && (KEYS[1] & 2)) { /* B closes without activating another item. */
        *(volatile u16 *)0x03000940 = info->display_control;
        *(volatile u16 *)0x0300098a = info->blend_control;
        *(volatile u16 *)0x0300098c = info->blend_alpha;
        info->active = 0;
        info->loaded = 0;
        Sound(105);
        return;
    }
    if (accept_input && (KEYS[2] & (64 | 32 | 512))) {
        info->page = info->page ? info->page - 1 : PLUGIN_INFO_PAGE_COUNT - 1;
        info->scroll = 0; info->loaded = 0; Sound(109);
    } else if (accept_input && (KEYS[2] & (128 | 16 | 256))) {
        info->page = info->page + 1 < PLUGIN_INFO_PAGE_COUNT ? info->page + 1 : 0;
        info->scroll = 0; info->loaded = 0; Sound(109);
    } else if (accept_input && (KEYS[1] & 1)) {
        unsigned count = gPluginInfoPages[info->page].view_count;
        info->scroll = info->scroll + 1 < count ? info->scroll + 1 : 0;
        info->loaded = 0;
    }
    index = info->page;
    if (info->loaded != 2) {
        Copy(gPluginInfoPages[index].views[info->scroll], (u16 *)0x06013000, 10240);
        info->loaded = 2;
    }
    Palette();
    for (row = 0; row < 5; ++row)
        for (column = 0; column < 8; ++column)
            Sprite(column * 32, row * 32, 384 + (row * 8 + column) * 16, 0, 1, 15);
}
void PluginInfoTitleUpdate(u8 *caller)
{
    u8 *root = ROOT;
    struct InfoState *info = (struct InfoState *)(root + 0x899c);
    unsigned selected = root[0x8962], i, tick, x, y;
    if (info->active) {
        Details(info, 1);
        if (info->active) return;
        /* Continue drawing the primary menu on the closing frame. */
    } else if (root[0x8993]) {
        CALL(0x08136a10, void, (u8 *))(caller); /* Native color-mode submenu. */
        info->loaded = 0;
        return;
    } else {
        if ((KEYS[2] & (16 | 32)) && selected >= 2) {
            selected = selected == 2 ? 3 : 2; Sound(109);
        } else if (KEYS[2] & 128) {
            selected = selected >= 2 ? 0 : selected + 1; Sound(109);
        } else if (KEYS[2] & 64) {
            selected = selected == 0 ? 2 : selected == 3 ? 1 : selected - 1;
            Sound(109);
        }
        root[0x8962] = selected;
        if (KEYS[1] & (1 | 8)) {
            if (selected == 3) {
                info->active = 1; info->page = 0; info->scroll = 0;
                info->loaded = 0;
                info->display_control = *(volatile u16 *)0x03000940;
                info->blend_control = *(volatile u16 *)0x0300098a;
                info->blend_alpha = *(volatile u16 *)0x0300098c;
                *(volatile u16 *)0x03000940 = info->display_control & 0x1fff;
                /* Native alpha registers: 12/16 panel, 4/16 background.
                 * Only explicitly semi-transparent Info OBJs are first targets. */
                *(volatile u16 *)0x0300098a = 0x3f40;
                *(volatile u16 *)0x0300098c = 0x040c;
                Sound(100); Details(info, 0); return;
            }
            /* The native routine owns all original confirmation behavior.
             * Prevent it from applying the navigation edge a second time. */
            u16 repeated = KEYS[2];
            KEYS[2] = 0;
            CALL(0x08136a10, void, (u8 *))(caller);
            KEYS[2] = repeated;
            info->loaded = 0;
            Label(info);
            return;
        }
    }
    DrawNative((void *)0x083a8c9e, 28, 72, selected == 0 ? 3 : 1);
    DrawNative((void *)0x083a8cac, 20, 88, selected == 1 ? 3 : 1);
    DrawNative((void *)0x083a8cc0, 12, 112, selected == 2 ? 3 : 1);
    Label(info);
    tick = root[0x8994] + 1;
    if (tick >= 30) tick = 0;
    root[0x8994] = tick;
    if (selected < 3) {
        const u16 *positions = (const u16 *)0x083a8c6c;
        x = positions[selected * 2]; y = positions[selected * 2 + 1];
    } else { x = 138; y = 112; }
    /* Five-frame native cursor bob, without a division runtime dependency. */
    i = 0;
    while (tick >= 5) { tick -= 5; ++i; }
    DrawNative((void *)0x083a8cfe, x + i, y, 4);
}
