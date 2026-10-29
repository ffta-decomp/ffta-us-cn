#include "plugin_info_ui.h"

unsigned PluginInfoInput(struct PluginInfoState *state, unsigned count,
                         unsigned keys)
{
    unsigned previous = state->selected;
    if (keys & 2) return 1; /* B */
    if (!count) return 0;
    if (keys & (64 | 32 | 512)) { /* Up, Left, L */
        state->selected = previous ? previous - 1 : count - 1;
    } else if (keys & (128 | 16 | 256)) { /* Down, Right, R */
        state->selected = previous + 1 < count ? previous + 1 : 0;
    }
    if (state->selected != previous) { state->scroll = 0; return 2; }
    return 0;
}

/* Build-time catalogue validation guarantees well-formed UTF-8. */
static uint32_t Next(const unsigned char **text)
{
    const unsigned char *p = *text;
    uint32_t value = *p++;
    unsigned remaining = 0;
    if (value >= 0xf0) { value &= 7; remaining = 3; }
    else if (value >= 0xe0) { value &= 15; remaining = 2; }
    else if (value >= 0xc0) { value &= 31; remaining = 1; }
    while (remaining--) value = (value << 6) | (*p++ & 63);
    *text = p;
    return value;
}

unsigned PluginInfoText(const char *text, unsigned x, unsigned y, unsigned width,
                        unsigned line_height, unsigned first_line,
                        unsigned visible_lines, PluginInfoWidth measure,
                        PluginInfoGlyph draw, void *context)
{
    const unsigned char *p = (const unsigned char *)text;
    unsigned line = 0, column = 0;
    while (*p) {
        uint32_t code = Next(&p);
        unsigned advance;
        if (code == '\n') { ++line; column = 0; continue; }
        advance = measure(context, code);
        if (advance > width) return 0; /* Reject impossible glyphs. */
        if (column + advance > width) { ++line; column = 0; }
        if (line >= first_line && line - first_line < visible_lines)
            draw(context, code, x + column, y + (line - first_line) * line_height);
        column += advance;
    }
    return line + 1;
}

static void Box(uint8_t *pixels, unsigned left, unsigned top,
                unsigned right, unsigned bottom)
{
    unsigned x, y;
    for (y = top; y <= bottom; ++y)
        for (x = left; x <= right; ++x) {
            unsigned dx = x < left + 3 ? left + 3 - x :
                          x > right - 3 ? x - (right - 3) : 0;
            unsigned dy = y < top + 3 ? top + 3 - y :
                          y > bottom - 3 ? y - (bottom - 3) : 0;
            if (dx + dy > 4) continue;
            pixels[y * 240 + x] = (x <= left + 1 || x >= right - 1 ||
                y <= top + 1 || y >= bottom - 1 || dx + dy >= 3) ? 2 : 1;
        }
}

void PluginInfoFrame(uint8_t *pixels, unsigned selected, unsigned count)
{
    unsigned i, row, x;
    for (i = 0; i < 240 * 160; ++i) pixels[i] = 0;
    for (i = 138 * 240; i < 160 * 240; ++i) pixels[i] = 1;
    Box(pixels, 8, 8, 79, 133);
    Box(pixels, 84, 8, 231, 133);
    if (selected >= count) return;
    row = 27 + selected * 24;
    if (row + 6 >= 143) return;
    for (i = 0; i < 7; ++i)
        for (x = 0; x <= (i <= 3 ? i : 6 - i); ++x)
            pixels[(row + i) * 240 + 16 + x] = 2;
}
