"""Browser build: same exact translated code, WebGL, and streamed local disc."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,subprocess,shutil,os,sys

def adapt_platform(source):
    source=source.replace('#include <SDL_opengl.h>','#include <GLES3/gl3.h>\n#include <emscripten.h>')
    source=source.replace('SDL_GL_CONTEXT_MINOR_VERSION, 3','SDL_GL_CONTEXT_MINOR_VERSION, 0').replace('SDL_GL_CONTEXT_PROFILE_CORE','SDL_GL_CONTEXT_PROFILE_ES')
    source=source.replace('case SDL_KEYUP: {','case SDL_KEYUP: { break; /* Browser JS owns combined keyboard/gamepad input. */')
    source=source.replace('SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_GAMECONTROLLER','SDL_INIT_VIDEO | SDL_INIT_GAMECONTROLLER') # Web Audio owns sound; SDL audio must not gate video startup.
    clock='    static Uint64 freq;\n    if (!freq) freq = SDL_GetPerformanceFrequency();\n    return (uint64_t)((SDL_GetPerformanceCounter() * 1000000) / freq);'
    if clock not in source:raise ValueError('Pinned SDL microsecond clock adapter no longer matches')
    return source.replace(clock,'    return (uint64_t)(emscripten_get_now() * 1000.0);')

def build(args,kit,error,verify,write_json):
    import native
    os.environ['PATH']=str(Path(sys.executable).parent)+os.pathsep+os.environ.get('PATH','')
    os.environ['EMSDK_PYTHON']=sys.executable
    # Reuse all source/profile integrity checks and shared project definitions.
    args.graphics=False
    native.build(args,kit,error,verify,write_json)
    project=Path(args.project).resolve();core=Path(args.toolchain).resolve()
    sdk=Path(args.emsdk).resolve();emcc=sdk/'upstream/emscripten/emcc.py'
    if not emcc.exists():raise error('Install and activate Emscripten first')
    output=project/'.local/browser';output.mkdir(exist_ok=True)
    include=output/'include';include.mkdir(exist_ok=True)
    local=project/'.local/native';generated=project/'.local/generated'
    lock=json.loads((project/'.local/source-lock.json').read_text())
    header=(local/'include/project.h').read_text()
    lines=header.splitlines()
    lines=[line for line in lines if not line.startswith('#define PORT_TRACK_PATHS') and not line.startswith('#define PORT_EXECUTABLE')]
    lines+=['#define PORT_EXECUTABLE "/game.bin"','#define PORT_TRACK_PATHS {'+','.join(json.dumps('/disc/'+str(i)) for i in range(len(lock['tracks'])))+'}']
    (include/'project.h').write_text('\n'.join(lines)+'\n')
    renderer=(core/'src/hal/pvr2_render.c').read_text().replace('#include <GL/glew.h>','#include <GLES3/gl3.h>')
    begin=renderer.index('    /* Initialize GLEW */');end=renderer.index('    printf("[PVR2] OpenGL',begin)
    renderer=renderer[:begin]+renderer[end:]
    renderer=renderer.replace('#version 330 core\\n','#version 300 es\\nprecision highp float;\\n')
    import graphics
    renderer=graphics.adapt(core,output,include,renderer)
    renderer='#include <emscripten/html5.h>\n'+renderer
    renderer=renderer.replace('void pvr2_render_frame(void) {', 'void pvr2_render_frame(void) {\n    int canvas_width,canvas_height;emscripten_get_canvas_element_size("#canvas",&canvas_width,&canvas_height);glViewport(0,0,canvas_width,canvas_height);')
    (output/'renderer.c').write_text(renderer)
    # SDL's nanosecond counter * 1,000,000 can overflow before division.
    # Use the browser's monotonic millisecond clock directly, including long sessions.
    layer=adapt_platform((core/'src/platform/platform_sdl2.c').read_text())
    # The CPU budget yields regularly; yielding again at every hardware poll
    # adds browser timer delays and slows the emulated game's clock.
    (output/'platform.c').write_text(layer)
    hardware=(core/'src/hal/dc_hardware.c').read_text().replace('if (ch2_log <= 20)', 'if (ch2_log < 20)').replace('printf("[PVR] Soft reset\\n");','{static int reset_logs=0;if(reset_logs++<8)printf("[PVR] Soft reset\\n");}')
    hardware='#include <stdio.h>\n#include "browser_audio.h"\n'+hardware.lstrip('\ufeff')
    hardware=hardware.replace('    uint32_t *ta = aica_reg(AICA_TIMER_A);','    port_audio_advance(g_aica_regs,sh4_get_aica_ram_ptr(),samples);\n    uint32_t *ta = aica_reg(AICA_TIMER_A);')
    hardware=hardware.replace('    g_aica_regs[off / 4] = val;', '    g_aica_regs[off / 4] = val;\n    port_aica_key_execute(&port_aica,g_aica_regs,off);')
    hardware=hardware.replace('    if (off == AICA_INTREQ)', '''    if(off==0x2814)return port_aica.voices[(g_aica_regs[0x280c/4]>>8)&63].position;
    if(off==0x2810) {
        PortAicaVoice *v=&port_aica.voices[(g_aica_regs[0x280c/4]>>8)&63];
        unsigned value=(unsigned)(v->active?v->envelope:1023) | ((unsigned)v->stage<<13) | (v->looped?0x8000:0);
        v->looped=0;return value;
    }
    if (off == AICA_INTREQ)''')
    (output/'hardware.c').write_text(hardware)
    bios=(core/'src/hal/dc_bios.c').read_text()
    bios=bios.replace('#define GDC_MAX_TRACKS 24','#include "browser_disc.h"\n#define GDC_MAX_TRACKS 24')
    begin=bios.index('    FILE *f = fopen(path, "rb");');end=bios.index('    g_tracks[g_track_count].start_lba',begin)
    sizes=[Path(t['path']).stat().st_size for t in lock['tracks']]
    replacement='    const long sizes[]={'+','.join(map(str,sizes))+'};\n    long size=sizes[g_track_count];\n'
    bios=bios[:begin]+replacement+bios[end:]
    bios=bios.replace('            if (fseek(g_tracks[t].f, off, SEEK_SET) == 0)\n                fread(sector, 1, GDC_RAW_SECTOR, g_tracks[t].f);','            port_disc_read(t,off,sector);')
    (output/'bios.c').write_text(bios)
    cpu=(local/'cpu.c').read_text()
    cpu='#include <emscripten.h>\n#include "browser_clock.h"\n'+cpu
    cpu=cpu.replace('void sh4_poll_irq(SH4CPU *cpu) {', 'void sh4_poll_irq(SH4CPU *cpu) {\n    static double yielded,waited,reported;static unsigned yields;double now=emscripten_get_now();if(now-yielded>8){double before=now;emscripten_sleep(0);yielded=emscripten_get_now();waited+=yielded-before;yields++;if(yielded-reported>5000){printf("[PERF] %u CPU yields, %.0fms waiting / %.0fms elapsed\\n",yields,waited,yielded-reported);reported=yielded;waited=0;yields=0;}}')
    # Browser disc reads already take wall time. Virtual-drive credit must not
    # deliver queued VBlanks in a burst and advance the gameplay timer.
    cpu=cpu.replace('void sh4_credit_elapsed_ms(uint32_t ms) {', 'void sh4_credit_elapsed_ms(uint32_t ms) {(void)ms;return;')
    begin=cpu.index('          uint64_t now = platform_get_ticks_ms();',cpu.index('if (vpolls > 0)'))
    end=cpu.index('          }\n          }',begin)+len('          }')
    cpu=cpu[:begin]+'''          if(port_vblank_ready(emscripten_get_now()))dc_pvr_wait_vblank(g_hardware);'''+cpu[end:]
    (output/'cpu.c').write_text(cpu)
    (output/'fault.c').write_text('void sh4_dump_native_stack(const char *tag) {(void)tag;}\nvoid sh4_install_crash_handler(void) {}\n')
    sources=sorted((generated/'src').glob('*.c'))+[local/'unresolved.c',output/'cpu.c',core/'src/recompiler/sh4_task.c',kit/'runtime/runner.c',output/'fault.c']
    sources += [p for p in (core/'src/hal').glob('*.c') if p.name not in ('pvr2_render.c','pvr2_ta.c','dc_bios.c','dc_hardware.c')]+[output/'renderer.c',output/'platform.c',output/'bios.c',output/'ta.c',output/'hardware.c']
    flags=['-O2','-fno-strict-aliasing','-fwrapv','-std=c11','-include','time.h','-DHAS_SDL2','-DHAS_OPENGL','-Wno-unused-value','-Wno-parentheses-equality','-sUSE_SDL=2','-I',str(include),'-I',str(local/'include'),'-I',str(generated/'include'),'-I',str(core/'include'),'-I',str(kit/'runtime')]
    if args.abi:flags+=['-DDCRECOMP_ABI_CHECK']
    objects=output/'obj';objects.mkdir(exist_ok=True)
    headers=b''.join(p.read_bytes() for parent in [include,local/'include',generated/'include',core/'include',kit/'runtime'] for p in sorted(parent.rglob('*.h')))
    def compile_one(src):
        obj=objects/(hashlib.sha256(str(src).encode()).hexdigest()[:10]+'_'+src.stem+'.o');stamp=obj.with_suffix('.sha')
        digest=hashlib.sha256(src.read_bytes()+headers+str(flags).encode()).hexdigest()
        if not obj.exists() or not stamp.exists() or stamp.read_text()!=digest:
            result=subprocess.run([sys.executable,str(emcc),*flags,'-c',str(src),'-o',str(obj)],capture_output=True,text=True)
            obj.with_suffix('.log').write_text(result.stdout+result.stderr)
            if result.returncode:raise error(src.name+': '+result.stderr[-2500:])
            stamp.write_text(digest)
        return obj
    with ThreadPoolExecutor(max_workers=3) as pool:compiled=list(pool.map(compile_one,sources))
    _,exe=verify(project)
    result=subprocess.run([sys.executable,str(emcc),*map(str,compiled),'-O2','-g2','-sUSE_SDL=2','-sMIN_WEBGL_VERSION=2','-sMAX_WEBGL_VERSION=2','-sASYNCIFY=1','-sASYNCIFY_STACK_SIZE=4194304','-sSTACK_SIZE=16777216','-sINITIAL_MEMORY=134217728','-sALLOW_MEMORY_GROWTH=1','-sMAXIMUM_MEMORY=1073741824','-sASSERTIONS=1','--embed-file',str(exe)+'@/game.bin','-o',str(output/'game.js')],capture_output=True,text=True)
    (output/'link.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise error('WebAssembly link: '+result.stderr[-2500:])
    for name in ('index.html','browser.js','browser.css','audio.js','audio-worklet.js'):shutil.copyfile(kit/'runtime/web'/name,output/name)
    write_json(output/'build.json',{'target':'browser-webgl2','playable':False,'sourceSetSHA256':json.loads((project/'port.json').read_text())['sourceSetSHA256'],'wasmSHA256':hashlib.sha256((output/'game.wasm').read_bytes()).hexdigest()})
    print('Browser build ready. Run serve-browser; gameplay remains unverified.')
