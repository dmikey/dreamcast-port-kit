/* WebGL2 worker platform. The page owns DOM/input/audio; no SDL or GL proxy. */
#include "platform/platform.h"
#include <emscripten.h>
#include <emscripten/html5.h>
#include <GLES3/gl3.h>
#include <stdio.h>
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
void platform_swap_buffers(void){glFlush();}
void platform_set_title(const char *title){(void)title;}
uint64_t platform_get_ticks_ms(void){return (uint64_t)emscripten_get_now();}
uint64_t platform_get_ticks_us(void){return (uint64_t)(emscripten_get_now()*1000.0);}
void platform_sleep_ms(uint32_t ms){emscripten_sleep(ms);}
