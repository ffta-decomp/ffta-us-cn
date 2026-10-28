/* Direct execution of the original serial poll in mGBA, not a GP/link-session
 * test. All 256 counter values, both flag paths, both phases and changed/stable
 * input states are checked. No ROM or game resources are embedded here. */
#include <mgba/core/core.h>
#include <mgba/core/log.h>
#include <mgba/internal/arm/arm.h>
#include <mgba/internal/arm/isa-inlines.h>
#include <mgba-util/vfs.h>
#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static color_t pixels[240 * 160];
static void quiet(struct mLogger *logger, int category, enum mLogLevel level,
                  const char *format, va_list args)
{
    (void)logger; (void)category; (void)level; (void)format; (void)args;
}

int main(int argc, char **argv)
{
    if (argc != 3) {
        fprintf(stderr, "usage: probe_link_timeout ROM MAX_COUNTER(70|254)\n");
        return 2;
    }
    unsigned maximum = (unsigned)strtoul(argv[2], NULL, 10);
    assert(maximum == 70 || maximum == 254);
    struct mLogger logger = {.log = quiet}; mLogSetDefaultLogger(&logger);
    struct mCore *core = mCoreFind(argv[1]); assert(core && core->init(core));
    mCoreInitConfig(core, "fftaLinkCounterProbe");
    core->setVideoBuffer(core, pixels, 240);
    assert(mCoreLoadFile(core, argv[1]));
    struct VFile *save = VFileMemChunk(NULL, 0);
    assert(save && core->loadSave(core, save));
    core->reset(core);
    unsigned cases = 0;
    for (unsigned flags = 0; flags <= 8; flags += 8)
    for (unsigned phase = 0; phase < 2; ++phase)
    for (unsigned changed = 0; changed < 2; ++changed)
    for (unsigned count = 0; count < 256; ++count) {
        core->busWrite16(core, 0x04000208, 0); /* Disable interrupt master. */
        core->busWrite16(core, 0x04000134, 0x8000);
        unsigned status = core->busRead16(core, 0x04000134) & (flags ? 2 : 5);
        unsigned previous = status ^ changed;
        core->busWrite8(core, 0x030028a0, flags);
        core->busWrite8(core, 0x03002b44, phase);
        core->busWrite8(core, 0x03002884, previous);
        core->busWrite8(core, 0x03002b60, count);
        struct ARMCore *cpu = core->cpu;
        cpu->halted = 0; cpu->cpsr.i = 1; cpu->cpsr.t = 1;
        cpu->executionMode = MODE_THUMB;
        cpu->gprs[4] = 0x44556677; cpu->gprs[5] = 0x55667788;
        cpu->gprs[ARM_SP] = 0x03007d00;
        cpu->gprs[ARM_LR] = 0x08010001;
        cpu->gprs[ARM_PC] = 0x08004d68; ThumbWritePC(cpu);
        unsigned steps = 0;
        while ((uint32_t)cpu->gprs[ARM_PC] - 2 != 0x08010000 && steps < 200) {
            core->step(core); ++steps;
        }
        assert(steps < 200);
        unsigned success = count <= maximum;
        assert((unsigned)cpu->gprs[0] == success);
        assert(core->busRead8(core, 0x03002b60) ==
               (success ? (changed ? 0 : (count + 1) & 255) : count));
        assert(core->busRead8(core, 0x03002b44) == (success ? phase ^ 1 : phase));
        assert(core->busRead8(core, 0x03002884) == (success ? status : previous));
        assert(cpu->gprs[4] == 0x44556677 && cpu->gprs[5] == 0x55667788);
        assert(cpu->gprs[ARM_SP] == 0x03007d00);
        ++cases;
    }
    printf("{\"cases\":%u,\"maximum\":%u,\"actual_original_function_execution\":true,"
           "\"gp_multiplayer_test\":false}\n", cases, maximum);
    core->deinit(core);
    return 0;
}
