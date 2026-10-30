/* Browser adapter for the reusable AICA direct mixer. */
#include "aica_mixer.h"
#include <emscripten.h>
static PortAicaMixer port_aica;
EM_JS(void,port_audio_submit,(const float *data,unsigned frames),{
    if(Module.portAudioPush)Module.portAudioPush(HEAPF32.slice(data>>2,(data>>2)+frames*2));
});
static void port_audio_advance(uint32_t *regs,const uint8_t *ram,unsigned frames) {
    static float block[512*2];static unsigned filled;static uint64_t dropped;
    /* A blocked browser cannot play historical sound; bound catch-up work. */
    if(frames>11025){dropped+=frames-11025;frames=11025;}
    while(frames) {unsigned n=frames>512-filled?512-filled:frames;port_aica_render(&port_aica,regs,ram,block+filled*2,n);filled+=n;frames-=n;if(filled==512){port_audio_submit(block,512);filled=0;}}
    static uint64_t reported;
    if(port_aica.frames-reported>=44100*5) {
        reported=port_aica.frames;
        unsigned active=0;for(int i=0;i<64;i++)active+=port_aica.voices[i].active;
        printf("[AUDIO] frames=%llu nonzero=%llu keyons=%llu active=%u formats=%X clipped=%llu dropped=%llu master=%X\n",(unsigned long long)port_aica.frames,(unsigned long long)port_aica.nonzero_frames,(unsigned long long)port_aica.keyons,active,port_aica.formats,(unsigned long long)port_aica.clipped,(unsigned long long)dropped,regs[0x2800/4]&15);
    }
}
