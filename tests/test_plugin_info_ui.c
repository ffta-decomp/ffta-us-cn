#include "plugin_info_ui.h"
#include <assert.h>
#include <stdio.h>
static unsigned codes[32], positions[32][2], count;
static unsigned Width(void *context, uint32_t code)
{ (void)context; return code < 128 ? 6 : 12; }
static void Draw(void *context, uint32_t code, unsigned x, unsigned y)
{ (void)context; assert(count < 32); codes[count]=code;positions[count][0]=x;positions[count++][1]=y; }
int main(void)
{
 struct PluginInfoState state={0,0};
 unsigned char pixels[240*160];
 assert(PluginInfoInput(&state,2,64)==2 && state.selected==1);
 assert(PluginInfoInput(&state,2,128)==2 && state.selected==0);
 assert(PluginInfoInput(&state,2,2|128)==1 && state.selected==0);
 assert(PluginInfoInput(&state,0,128)==0);
 assert(PluginInfoText("a b\n汉化c",10,20,18,18,0,5,Width,Draw,0)==3);
 assert(count==6 && codes[1]==' ' && codes[3]==0x6c49);
 assert(positions[3][0]==10 && positions[3][1]==38);
 assert(positions[4][0]==10 && positions[4][1]==56);
 assert(positions[5][0]==22 && positions[5][1]==56);
 count=0;
 assert(PluginInfoText("a b\n汉化c",10,20,18,18,2,1,Width,Draw,0)==3);
 assert(count==2 && codes[0]==0x5316 && positions[0][1]==20);
 assert(PluginInfoText("a\n",0,0,18,18,0,0,Width,Draw,0)==2);
 assert(PluginInfoText("汉",0,0,11,18,0,0,Width,Draw,0)==0);
 PluginInfoFrame(pixels,1,2);
 assert(pixels[8*240+8]==0); /* Rounded corner remains transparent. */
 assert(pixels[8*240+12]==2 && pixels[50*240+100]==1);
 assert(pixels[51*240+16]==2 && pixels[27*240+16]==1);
 puts("Plugin Info UTF-8 wrapping, viewport, page input and rounded frames passed");
 return 0;
}
