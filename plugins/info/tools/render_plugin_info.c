/* Info plugin build-time renderer using the same layout core as host UI tests. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "plugin_info_ui.h"
struct HostGlyph { unsigned code, advance; unsigned char cell[128]; };
#include "plugin_info_render_data.h"
static unsigned char pixels[240 * 160];
static unsigned title_label;
static const struct HostGlyph *Glyph(unsigned code)
{
    unsigned i;
    if (title_label)
        for (i = 0; i < sizeof(host_label_glyphs) / sizeof(host_label_glyphs[0]); ++i)
            if (host_label_glyphs[i].code == code) return host_label_glyphs + i;
    for (i = 0; i < sizeof(host_glyphs) / sizeof(host_glyphs[0]); ++i)
        if (host_glyphs[i].code == code) return host_glyphs + i;
    fprintf(stderr, "Missing native glyph U+%04X\n", code);
    exit(1);
}
static unsigned Width(void *unused, unsigned code)
{
    (void)unused;
    return code == 32 ? 5 : Glyph(code)->advance;
}
static void Draw(void *unused, unsigned code, unsigned x, unsigned y)
{
    unsigned gx, gy;
    const struct HostGlyph *glyph;
    (void)unused;
    if (code == 32) return;
    glyph = Glyph(code);
    for (gy = 0; gy < 16; ++gy)
        for (gx = 0; gx < 16; ++gx) {
            unsigned shade = (glyph->cell[gx / 8 * 64 + gy * 4 + gx % 8 / 2] >>
                              (gx % 2 * 4)) & 15;
            if (shade != 3) continue;
            if (x + gx >= 240 || y + gy >= 160) {
                fprintf(stderr, "Glyph exceeds framebuffer\n"); exit(1);
            }
            pixels[(y + gy) * 240 + x + gx] = 2;
        }
}
static unsigned Text(const char *text, unsigned x, unsigned y, unsigned width,
                     unsigned first, unsigned visible)
{
    unsigned count = PluginInfoText(text, x, y, width, 18, first, visible,
                                    Width, Draw, NULL);
    if (!count) { fprintf(stderr, "Text cannot fit content width\n"); exit(1); }
    return count;
}
static void Save(const char *directory, const char *name)
{
    char path[4096];
    FILE *file;
    int length = snprintf(path, sizeof(path), "%s/%s.pixels", directory, name);
    if (length < 0 || (unsigned)length >= sizeof(path)) exit(1);
    file = fopen(path, "wb");
    if (!file || fwrite(pixels, 1, sizeof(pixels), file) != sizeof(pixels)) exit(1);
    if (fclose(file)) exit(1);
}
int main(int argc, char **argv)
{
    const unsigned count = sizeof(host_pages) / sizeof(host_pages[0]);
    unsigned page, first, n, y, x, first_record = 1;
    char name[64];
    if (argc != 2) return 2;
    printf("{\"views\":[");
    for (page = 0; page < count; ++page) {
        unsigned lines = Text(host_pages[page].content, 96, 48, 120, 0, 0);
        if (lines > 255 * 4) { fprintf(stderr, "Too many content lines\n"); return 1; }
        for (first = 0; first < lines; first += 4) {
            PluginInfoFrame(pixels, page, count);
            for (n = 0; n < count; ++n)
                if (Text(host_pages[n].name, 26, 24 + n * 24, 46, 0, 1) != 1) {
                    fprintf(stderr, "Plugin name exceeds sidebar width\n"); return 1;
                }
            Text(host_pages[page].name, 96, 22, 120, 0, 1);
            Text(host_pages[page].content, 96, 48, 120, first, 4);
            if (lines > 4)
                for (y = 0; y < 4; ++y)
                    for (x = 0; x < 7 - y * 2; ++x)
                        pixels[(122 + y) * 240 + 212 + y + x] = 2;
            Text("B: Close", 92, 142, 140, 0, 1);
            snprintf(name, sizeof(name), "info_view_%u_%u", page, first / 4);
            Save(argv[1], name);
            printf("%s{\"page\":%u,\"first_line\":%u,\"symbol\":\"%s\"}",
                   first_record ? "" : ",", page, first, name);
            first_record = 0;
        }
    }
    memset(pixels, 0, sizeof(pixels));
    title_label = 1;
    Text("Info", 0, 0, 64, 0, 1);
    Save(argv[1], "gPluginInfoLabel");
    puts("]}");
    return 0;
}
