/* Same-ROM mGBA naming acceptance driver. Inputs are real keypad presses.
 * A secondary-context fixture changes only the existing editor mode halfword;
 * it is explicitly not proof of reaching that menu through the story. */
#include <mgba/core/core.h>
#include <mgba/core/log.h>
#include <mgba/core/serialize.h>
#include <mgba-util/vfs.h>
#include <assert.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static struct mCore *core;
static uint32_t editor;
static color_t pixels[240 * 160];

static void quiet(struct mLogger *logger, int category, enum mLogLevel level,
                  const char *format, va_list args)
{
    (void)logger; (void)category; (void)level; (void)format; (void)args;
}

static unsigned byte(unsigned offset)
{
    return core->busRead8(core, editor + offset);
}

static void frames(unsigned count, unsigned keys)
{
    core->setKeys(core, keys);
    while (count--)
        core->runFrame(core);
}

static void key(unsigned keys)
{
    frames(2, keys);
    frames(10, 0);
}

static void first_row(void)
{
    unsigned tries = 0;
    while (byte(0x311) != 0) {
        assert(++tries < 15);
        key(0x40);
    }
}

static void column(unsigned target)
{
    unsigned tries = 0;
    while (byte(0x310) != target) {
        assert(++tries < 15);
        key(0x10);
    }
}

static void row(unsigned target)
{
    unsigned tries = 0;
    while (byte(0x311) != target) {
        assert(++tries < 15);
        key(0x80);
    }
}

static void spell(const char *letters)
{
    while (*letters) {
        unsigned letter = (unsigned)(*letters++ - 'a');
        assert(letter < 26);
        first_row();
        column(letter % 10);
        row(letter / 10);
        key(1);
    }
}

static void capture(const char *directory, const char *label)
{
    char path[4096];
    frames(30, 0);
    snprintf(path, sizeof(path), "%s/%s.ppm", directory, label);
    FILE *out = fopen(path, "wb");
    assert(out);
    fprintf(out, "P6\n240 160\n255\n");
    for (unsigned index = 0; index < 240 * 160; ++index) {
        uint32_t color = pixels[index];
        fputc(color & 255, out);
        fputc((color >> 8) & 255, out);
        fputc((color >> 16) & 255, out);
    }
    fclose(out);
    snprintf(path, sizeof(path), "%s/%s.video-memory", directory, label);
    out = fopen(path, "wb"); assert(out);
    const uint32_t bases[] = {0x04000000, 0x05000000, 0x06000000, 0x07000000};
    const unsigned sizes[] = {0x100, 0x400, 0x18000, 0x400};
    for (unsigned block = 0; block < 4; ++block)
        for (unsigned i = 0; i < sizes[block]; ++i)
            fputc(core->busRead8(core, bases[block] + i), out);
    fclose(out);
    snprintf(path, sizeof(path), "%s/%s.ewram", directory, label);
    out = fopen(path, "wb"); assert(out);
    for (unsigned index = 0; index < 0x40000; ++index)
        fputc(core->busRead8(core, 0x02000000 + index), out);
    fclose(out);
    snprintf(path, sizeof(path), "%s/%s.state", directory, label);
    struct VFile *state = VFileOpen(path, O_CREAT | O_TRUNC | O_RDWR);
    assert(state && mCoreSaveStateNamed(core, state, 0));
    state->close(state);
    printf("{\"capture\":\"%s\",\"editor\":\"%08x\",\"name_length\":%u,"
           "\"composition\":\"", label, editor, byte(0x326));
    for (unsigned i = 0; i < byte(0x33b); ++i)
        putchar((int)byte(0x334 + i));
    printf("\",\"page\":%u,\"candidate_count\":%u}\n",
           core->busRead16(core, editor + 0x37a), byte(0x37c));
}

int main(int argc, char **argv)
{
    if (argc != 5) {
        fprintf(stderr, "usage: probe_native_pinyin ROM SAME_ROM_STATE ACTIONS EXTERNAL_OUTPUT_DIR\n");
        return 2;
    }
    struct mLogger logger = {.log = quiet}; mLogSetDefaultLogger(&logger);
    core = mCoreFind(argv[1]); assert(core && core->init(core));
    mCoreInitConfig(core, "fftaNativePinyinProbe");
    core->setVideoBuffer(core, pixels, 240);
    assert(mCoreLoadFile(core, argv[1]));
    struct VFile *save = VFileMemChunk(NULL, 0);
    assert(save && core->loadSave(core, save));
    core->reset(core);
    struct VFile *state = VFileOpen(argv[2], O_RDONLY);
    assert(state && mCoreLoadStateNamed(core, state, 0)); state->close(state);
    for (uint32_t address = 0x02000380; address < 0x02040000; address += 4)
        if (core->busRead32(core, address) == 0x50494e59) {
            assert(!editor);
            editor = address - 0x380;
        }
    assert(editor);
    FILE *actions = fopen(argv[3], "r"); assert(actions);
    char line[512], command[64], argument[256];
    while (fgets(line, sizeof(line), actions)) {
        if (line[0] == '#' || sscanf(line, "%63s %255s", command, argument) < 1)
            continue;
        if (!strcmp(command, "key")) {
            key((unsigned)strtoul(argument, NULL, 16));
        } else if (!strcmp(command, "spell")) {
            spell(argument);
        } else if (!strcmp(command, "candidate")) {
            unsigned index = (unsigned)strtoul(argument, NULL, 10);
            assert(index < byte(0x37c));
            first_row(); column(index % 10); row(3 + index / 10); key(1);
        } else if (!strcmp(command, "clear")) {
            unsigned tries = 0;
            do { key(2); assert(++tries < 25); }
            while (byte(0x326) || byte(0x33b));
        } else if (!strcmp(command, "expect-spelling")) {
            unsigned length = !strcmp(argument, "-") ? 0 : (unsigned)strlen(argument);
            assert(byte(0x33b) == length);
            for (unsigned i = 0; i < length; ++i)
                assert(byte(0x334 + i) == (unsigned char)argument[i]);
        } else if (!strcmp(command, "expect-name")) {
            unsigned length = (unsigned)strlen(argument) / 4;
            assert(byte(0x326) == length);
            for (unsigned i = 0; i < length; ++i) {
                unsigned token; assert(sscanf(argument + i * 4, "%4x", &token) == 1);
                assert(byte(0x312 + i * 2) == token >> 8);
                assert(byte(0x313 + i * 2) == (token & 255));
            }
        } else if (!strcmp(command, "secondary-context-fixture")) {
            core->busWrite16(core, editor + 6, 0);
            puts("{\"fixture\":\"secondary editor mode; not natural story entry\"}");
        } else if (!strcmp(command, "expect-global")) {
            uint32_t address = core->busRead16(core, editor + 6) ? 0x02001f1c : 0x020021a0;
            for (unsigned i = 0; i < strlen(argument) / 4; ++i) {
                unsigned token; assert(sscanf(argument + i * 4, "%4x", &token) == 1);
                assert(core->busRead16(core, address + i * 2) == ((token >> 8) | (token << 8)) % 65536);
            }
        } else if (!strcmp(command, "capture")) {
            capture(argv[4], argument);
        } else if (!strcmp(command, "wait")) {
            frames((unsigned)strtoul(argument, NULL, 10), 0);
        } else {
            fprintf(stderr, "unknown action: %s", line); return 3;
        }
    }
    fclose(actions); core->deinit(core); return 0;
}
