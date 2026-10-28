/* CN tab extension of the pinned decompiled renderer. */
typedef unsigned char u8;
typedef signed char s8;
typedef unsigned int u32;
extern const u8 SceneBackground[];
extern const u8 SceneOverlayA[];
extern const u8 SceneOverlayB[];
extern const u8 SceneOverlayC[];
extern const u8 SceneMarker[];
extern const u8 SceneMarkerPositions[];
extern void SpriteActive(const void *,u32,u32,u32,u32,u32,u32,u32,u32,u32,u32);
extern void SpriteBank(const void *,u32,u32,u32,u32,u32,u32,u32,u32,u32,u32);
extern void NativeNameTabs(u8 *);
extern void RenderEncodedSprites(u8 *,u32,u32);
void RenderFullSceneTextAndMarker(u8 *context) asm("CoreRegion_0012A440");
void RenderFullSceneTextAndMarker(u8 *context)
{
    SpriteActive(SceneBackground,80,128,0,0,0,0,0,0,0,0);
    RenderEncodedSprites(context,92,136);
    SpriteActive(*(void **)(context+664),240,154,0,0,1,0,0,576,0,0);
    SpriteActive(SceneOverlayA,192,16,0,0,0,0,0,0,0,0);
    SpriteActive(SceneOverlayB,192,32,0,0,0,0,0,0,0,0);
    SpriteBank(SceneOverlayC,192,48,0,0,0,0,0,0,0,0);
    NativeNameTabs(context+758);
}
asm(".set SceneBackground,0x083a8298\n.set SceneOverlayA,0x083a82ac\n.set SceneOverlayB,0x083a82ba\n.set SceneOverlayC,0x083a82c8\n.set SceneMarker,0x083a82ec\n.set SceneMarkerPositions,0x083a8295\n.thumb_set SpriteActive,0x08001f35\n.thumb_set SpriteBank,0x08001cf1\n.thumb_set RenderEncodedSprites,0x0812addd\n");

asm(".thumb_set NativeNameTabs,0x083b42e5\n");
