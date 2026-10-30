/* WebGL2 worker platform. The page owns DOM/input/audio; no SDL or GL proxy. */
#include "platform/platform.h"
#include "recompiler/sh4_cpu.h"
#include <emscripten.h>
#include <emscripten/html5.h>
#include <GLES3/gl3.h>
#include <stdio.h>
#include "frame_timing.h"
static EMSCRIPTEN_WEBGL_CONTEXT_HANDLE context;
int platform_init(int width,int height,const char *title) {
    (void)title;EmscriptenWebGLContextAttributes a;
    emscripten_webgl_init_context_attributes(&a);
    a.majorVersion=2;a.minorVersion=0;a.alpha=0;a.depth=1;a.stencil=1;
    a.antialias=0;a.preserveDrawingBuffer=0;
    a.explicitSwapControl=0;a.proxyContextToMainThread=EMSCRIPTEN_WEBGL_CONTEXT_PROXY_DISALLOW;
    emscripten_set_canvas_element_size("#canvas",width,height);
    context=emscripten_webgl_create_context("#canvas",&a);
    if(context<=0||emscripten_webgl_make_context_current(context)!=EMSCRIPTEN_RESULT_SUCCESS){fprintf(stderr,"[PLATFORM] Worker WebGL 2 context failed\n");return -1;}
    printf("[PLATFORM] Dedicated worker WebGL 2 initialized: %dx%d\n",width,height);return 0;
}
void platform_shutdown(void){if(context)emscripten_webgl_destroy_context(context);}
bool platform_poll_events(DCHardware *hw){(void)hw;return true;}
EM_JS(void,port_save_vram,(const void *ptr),{const bytes=HEAPU8.slice(ptr,ptr+0x800000).buffer;postMessage({kind:'vram',bytes},[bytes]);});
EMSCRIPTEN_KEEPALIVE void port_vram_capture(void){port_save_vram(sh4_get_vram_ptr());}
static int capture_frame;static unsigned presentation_count;
EMSCRIPTEN_KEEPALIVE unsigned port_frame_count(void){return presentation_count;}
EMSCRIPTEN_KEEPALIVE void port_frame_capture(void){capture_frame=1;}
EM_JS(void,port_save_frame,(void),{
 const w=Module.canvas.width,h=Module.canvas.height,pixels=new Uint8Array(w*h*4);
 GLctx.readPixels(0,0,w,h,GLctx.RGBA,GLctx.UNSIGNED_BYTE,pixels);
 const flipped=new Uint8ClampedArray(pixels.length),stride=w*4;
 for(let y=0;y<h;y++)flipped.set(pixels.subarray(y*stride,(y+1)*stride),(h-1-y)*stride);
 const canvas=new OffscreenCanvas(w,h);canvas.getContext('2d').putImageData(new ImageData(flipped,w,h),0,0);
 canvas.convertToBlob({type:'image/png'}).then(blob=>blob.arrayBuffer()).then(bytes=>postMessage({kind:'frame',bytes},[bytes]));
});
void platform_swap_buffers(void){presentation_count++;if(capture_frame){capture_frame=0;port_save_frame();}glFlush();
 static PortFrameTiming timing;
 if(port_frame_timing(&timing,emscripten_get_now()))printf("[PACING] fps=%.2f p95_ms=%.2f p99_ms=%.2f max_ms=%.2f over20ms=%u\n",timing.fps,timing.p95,timing.p99,timing.maximum,timing.slow);
}
void platform_set_title(const char *title){(void)title;}
uint64_t platform_get_ticks_ms(void){return (uint64_t)emscripten_get_now();}
uint64_t platform_get_ticks_us(void){return (uint64_t)(emscripten_get_now()*1000.0);}
void platform_sleep_ms(uint32_t ms){emscripten_sleep(ms);}
