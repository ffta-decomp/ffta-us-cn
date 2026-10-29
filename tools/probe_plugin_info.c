/* Explicit cold-boot UI replay. ROM, actions and output directory stay external. */
#include <mgba/core/core.h>
#include <mgba/core/log.h>
#include <mgba-util/vfs.h>
#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static color_t pixels[240 * 160];
static void Quiet(struct mLogger *logger, int category, enum mLogLevel level,
                  const char *format, va_list args)
{ (void)logger; (void)category; (void)level; (void)format; (void)args; }
int main(int argc, char **argv)
{
 if (argc != 4) { fprintf(stderr,"usage: probe_plugin_info ROM ACTIONS OUTPUT_DIR\n");return 2; }
 struct mLogger logger={.log=Quiet};mLogSetDefaultLogger(&logger);
 struct mCore *core=mCoreFind(argv[1]);assert(core && core->init(core));
 mCoreInitConfig(core,"fftaPluginInfoProbe");core->setVideoBuffer(core,pixels,240);
 assert(mCoreLoadFile(core,argv[1]));
 struct VFile *save=VFileMemChunk(NULL,0);assert(save && core->loadSave(core,save));
 core->reset(core);
 FILE *actions=fopen(argv[2],"r");assert(actions);
 unsigned frames,keys,total=0;char label[128];
 while(fscanf(actions,"%u %x %127s",&frames,&keys,label)==3) {
  assert(frames<=30000 && keys<1024);core->setKeys(core,keys);
  for(unsigned i=0;i<frames;++i)core->runFrame(core);
  total+=frames;
  if(strcmp(label,"-")) {
   for(char *p=label;*p;++p)assert((*p>='a' && *p<='z') || (*p>='0' && *p<='9') || *p=='-');
   char path[4096];assert(snprintf(path,sizeof(path),"%s/%s.ppm",argv[3],label)<(int)sizeof(path));
   FILE *file=fopen(path,"wb");assert(file);fputs("P6\n240 160\n255\n",file);
   for(unsigned p=0;p<240*160;++p){uint32_t v=pixels[p];unsigned char rgb[]={v&255,(v>>8)&255,(v>>16)&255};assert(fwrite(rgb,1,3,file)==3);}fclose(file);
   uint32_t root=core->busRead32(core,0x0200f3b0);
   printf("{\"label\":\"%s\",\"frame\":%u,\"root\":%u",label,total,root);
   if(root>=0x02000000 && root+0x89a8<=0x02040000)
    printf(",\"choice\":%u,\"color_submenu\":%u,\"info_active\":%u,\"info_page\":%u,\"info_scroll\":%u",
     core->busRead8(core,root+0x8962),core->busRead8(core,root+0x8993),
     core->busRead8(core,root+0x899c),core->busRead8(core,root+0x899d),core->busRead8(core,root+0x899e));
   printf(",\"display_control\":%u,\"blend_control\":%u,\"blend_alpha\":%u,\"color_mode\":%u,\"palette_blue\":%u,\"palette_white\":%u",
    core->busRead16(core,0x03000940),core->busRead16(core,0x0300098a),core->busRead16(core,0x0300098c),
    core->busRead8(core,0x02002fc2)&3,core->busRead16(core,0x050003ec),core->busRead16(core,0x050003e8));
   puts("}");fflush(stdout);
  }
 }
 assert(feof(actions));fclose(actions);core->deinit(core);return 0;
}
