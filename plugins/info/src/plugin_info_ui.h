/* Info plugin catalogue UI. New behavior; no decomp matching credit. */
#ifndef PLUGIN_INFO_UI_H
#define PLUGIN_INFO_UI_H
#include <stddef.h>
#include <stdint.h>
struct PluginInfoPage { const char *name; const char *content; };
struct PluginInfoState { unsigned selected; unsigned scroll; };
/* Return 1 to close, 2 if the selected page changed, otherwise 0. */
unsigned PluginInfoInput(struct PluginInfoState *, unsigned count, unsigned keys);
/* Glyph callback receives one Unicode scalar and its pixel position. */
typedef void (*PluginInfoGlyph)(void *, uint32_t, unsigned, unsigned);
typedef unsigned (*PluginInfoWidth)(void *, uint32_t);
/* Explicit newline and automatic width wrapping share the same layout path.
 * Returns the line count, including lines outside the visible viewport. */
unsigned PluginInfoText(const char *, unsigned x, unsigned y, unsigned width,
                        unsigned line_height, unsigned first_line,
                        unsigned visible_lines, PluginInfoWidth,
                        PluginInfoGlyph, void *);
/* 240x160 indexed framebuffer: 0 transparent, 1 blue, 2 white. */
void PluginInfoFrame(uint8_t *pixels, unsigned selected, unsigned count);
#endif
