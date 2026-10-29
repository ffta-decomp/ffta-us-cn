/* Direct native glyph-loader acceptance in an isolated emulator instance.
 * This is a function test, separate from rendered UI or hardware acceptance. */
#include <mgba/core/core.h>
#include <mgba/core/log.h>
#include <mgba-util/vfs.h>
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static color_t pixels[240 * 160];
static void Quiet(struct mLogger *logger, int category, enum mLogLevel level,
                  const char *format, va_list args)
{ (void)logger; (void)category; (void)level; (void)format; (void)args; }
static void Register(struct mCore *core, const char *name, uint32_t value)
{ assert(core->writeRegister(core, name, &value)); }
int main(int argc, char **argv)
{
    if(argc != 3) { fprintf(stderr,"usage: probe_font_extensions ROM GLYPH_COUNT\n"); return 2; }
    unsigned count=(unsigned)strtoul(argv[2],NULL,10);
    assert(count>=3175 && count<0x8000);
    struct mLogger logger={.log=Quiet};mLogSetDefaultLogger(&logger);
    struct mCore *core=mCoreFind(argv[1]);assert(core && core->init(core));
    mCoreInitConfig(core,"fftaFontExtensionProbe");core->setVideoBuffer(core,pixels,240);
    assert(mCoreLoadFile(core,argv[1]));
    struct VFile *save=VFileMemChunk(NULL,0);assert(save && core->loadSave(core,save));
    core->reset(core);
    /* Let the native startup install its IWRAM copy routine before calling it. */
    for(unsigned frame=0;frame<600;++frame)core->runFrame(core);
    uint32_t font=core->busRead32(core,0x08013474),widths=core->busRead32(core,0x08013480);
    assert(widths==core->busRead32(core,0x08013a7c));
    core->busWrite8(core,0x020020e3,0); /* Native variable-width mode. */
    for(unsigned index=0;index<count;++index) {
        Register(core,"cpsr",0xff);Register(core,"sp",0x0203df00);
        Register(core,"lr",0x03007f01);Register(core,"r0",0x0203e000);
        Register(core,"r1",index);Register(core,"pc",0x0801344c);
        uint32_t pc=0,value=0;unsigned steps=0;
        while(steps++<10000) {
            assert(core->readRegister(core,"pc",&pc));
            if(pc>=0x03007f00 && pc<0x03007f08)break;
            core->step(core);
        }
        assert(steps<10000 && pc>=0x03007f00 && pc<0x03007f08);
        assert(core->readRegister(core,"r0",&value));
        assert(value==core->busRead8(core,widths+index));
        for(unsigned byte=0;byte<128;++byte) {
            unsigned actual=core->busRead8(core,0x0203e000+byte);
            unsigned expected=core->busRead8(core,font+index*128+byte);
            if(actual!=expected) {
                fprintf(stderr,"glyph %u byte %u: actual %u expected %u font %08x width %u steps %u\n",index,byte,actual,expected,font,value,steps);
                core->deinit(core);return 1;
            }
        }
    }
    printf("{\"native_loader_glyphs_checked\":%u,\"appended_glyphs_checked\":%u,\"glyph_bytes_and_widths_match\":true}\n",count,count-3175);
    core->deinit(core);return 0;
}
