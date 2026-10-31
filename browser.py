"""Browser build: same exact translated code, WebGL, and streamed local disc."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,subprocess,shutil,os,sys,html

def render_runtime_loader(kit,info):
    builds={'asyncify':{'loader':'game.js','suspension':'asyncify','wasmSHA256':info.get('wasmSHA256')},**info.get('variants',{})}
    return (kit/'runtime/web/runtime-loader.js').read_text().replace('/*PORT_RUNTIME_BUILDS*/{}',json.dumps(builds))

def publish_web_assets(kit,project,output):
    names=('index.html','player.html','workbench.js','projects.js','debug-bridge.js','browser.js','browser.css','browser-scheduler.js','runtime-bridge.js','runtime-worker.js','runtime-loader.js','vmu-format.js','vmu-storage.js','vmu-transport.js','vmu-ui.js','audio.js','audio-worklet.js')
    for name in names:shutil.copyfile(kit/'runtime/web'/name,output/name)
    info=json.loads((output/'build.json').read_text()) if (output/'build.json').exists() else {}
    (output/'runtime-loader.js').write_text(render_runtime_loader(kit,info))
    title=json.loads((project/'port.json').read_text()).get('disc',{}).get('title','Dreamcast game')
    page=output/'index.html'
    page.write_text(page.read_text().replace('>Dreamcast game</strong>','>'+html.escape(title)+'</strong>'))

def publish_bundle(output,stem='game'):
    # Publish the loader only after its content-addressed WASM is complete.
    # A running server must never pair an old loader with a partial new link.
    wasm_bytes=(output/(stem+'.next.wasm')).read_bytes()
    wasm_name='game-'+hashlib.sha256(wasm_bytes).hexdigest()[:16]+'.wasm'
    destination=output/wasm_name
    if not destination.exists() or destination.read_bytes()!=wasm_bytes:
        pending=output/(wasm_name+'.pending')
        pending.write_bytes(wasm_bytes);pending.replace(destination)
    loader=(output/(stem+'.next.js')).read_text().replace(stem+'.next.wasm',wasm_name)
    (output/(stem+'.publish.js')).write_text(loader)
    (output/(stem+'.publish.js')).replace(output/(stem+'.js'))
    if stem=='game':shutil.copyfile(output/(stem+'.next.wasm'),output/'game.wasm')
    return {'loader':stem+'.js','suspension':'asyncify' if stem=='game' else 'jspi','wasmSHA256':hashlib.sha256(wasm_bytes).hexdigest()}

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
    # Dedicated worker owns the GL context; the page owns DOM/input/audio.
    shutil.copyfile(kit/'runtime/browser_platform.c',output/'platform.c')
    hardware=(core/'src/hal/dc_hardware.c').read_text().replace('if (ch2_log <= 20)', 'if (ch2_log < 20)').replace('printf("[PVR] Soft reset\\n");','{static int reset_logs=0;if(reset_logs++<8)printf("[PVR] Soft reset\\n");}')
    hardware='#include <stdio.h>\n#include "browser_audio.h"\n'+hardware.lstrip('\ufeff')
    # One monotonic timestamp per hardware poll, without reducing device/IRQ checks.
    hardware=hardware.replace('static void aica_advance_timer_a(void) {','static void aica_advance_timer_a(uint64_t now_us) {')
    hardware=hardware.replace('    uint64_t now_us = platform_get_ticks_us();\n','')
    hardware=hardware.replace('void dc_aica_update(DCHardware *hw) {','void port_aica_update_at(DCHardware *hw,uint64_t now_us) {')
    hardware=hardware.replace('    aica_advance_timer_a();\n\n    uint64_t now = platform_get_ticks_ms();','    aica_advance_timer_a(now_us);\n\n    uint64_t now = now_us/1000;')
    import audio_clock
    hardware='#include "audio_clock.h"\n'+audio_clock.adapt(hardware)
    hardware+='\nvoid dc_aica_update(DCHardware *hw){port_aica_update_at(hw,platform_get_ticks_us());}\n'
    # This G2 implementation retires by poll count; its timestamp is unused.
    hardware=hardware.replace('void dc_g2_retire_finished(DCHardware *hw) {\n    if (!hw) return;\n    uint64_t now = platform_get_ticks_ms();','void dc_g2_retire_finished(DCHardware *hw) {\n    if (!hw) return;')

    hardware=hardware.replace('    uint32_t *ta = aica_reg(AICA_TIMER_A);','    port_audio_advance(g_aica_regs,sh4_get_aica_ram_ptr(),samples);\n    uint32_t *ta = aica_reg(AICA_TIMER_A);')
    hardware=hardware.replace('    g_aica_regs[off / 4] = val;', '    g_aica_regs[off / 4] = val;\n    port_aica_key_execute(&port_aica,g_aica_regs,off);')
    hardware=hardware.replace('    if (off == AICA_INTREQ)', '''    if(off==0x2814)return port_aica.voices[(g_aica_regs[0x280c/4]>>8)&63].position;
    if(off==0x2810) {
        PortAicaVoice *v=&port_aica.voices[(g_aica_regs[0x280c/4]>>8)&63];
        unsigned value=(unsigned)(v->active?v->envelope:1023) | ((unsigned)v->stage<<13) | (v->looped?0x8000:0);
        v->looped=0;return value;
    }
    if (off == AICA_INTREQ)''')
    hardware=hardware.replace('                        resp[2] = (uint32_t)ctrl->buttons', '                        {static unsigned last=~0u,changes;unsigned value=ctrl->buttons|((unsigned)ctrl->rtrig<<16)|((unsigned)ctrl->ltrig<<24);if(value!=last){if(changes<64){changes++;printf("[MAPLE-INPUT] buttons=%04X rt=%u lt=%u response=%08X\\n",ctrl->buttons,ctrl->rtrig,ctrl->ltrig,header_2);}last=value;}}\n                        resp[2] = (uint32_t)ctrl->buttons')
    import maple
    (output/'hardware.c').write_text(maple.adapt(hardware))
    bios=(core/'src/hal/dc_bios.c').read_text()
    bios=bios.replace('#define GDC_MAX_TRACKS 24','#include "browser_disc.h"\n#define GDC_MAX_TRACKS 24')
    begin=bios.index('    FILE *f = fopen(path, "rb");');end=bios.index('    g_tracks[g_track_count].start_lba',begin)
    sizes=[Path(t['path']).stat().st_size for t in lock['tracks']]
    replacement='    const long sizes[]={'+','.join(map(str,sizes))+'};\n    long size=sizes[g_track_count];\n'
    bios=bios[:begin]+replacement+bios[end:]
    bios=bios.replace('            if (fseek(g_tracks[t].f, off, SEEK_SET) == 0)\n                fread(sector, 1, GDC_RAW_SECTOR, g_tracks[t].f);','            port_disc_read(t,off,sector);')
    (output/'bios.c').write_text(bios)
    import memory_access
    cpu=memory_access.adapt_reads(memory_access.adapt((local/'cpu.c').read_text()))
    cpu='#include <emscripten.h>\n#include "browser_clock.h"\n#include "browser_yield.h"\n'+cpu
    import scheduler
    cpu=scheduler.idle_state(cpu)
    cpu=cpu.replace('void sh4_poll_irq(SH4CPU *cpu) {','void sh4_poll_irq(SH4CPU *cpu) {'+scheduler.poll_entry())
    # Browser disc reads already take wall time. Virtual-drive credit must not
    # deliver queued VBlanks in a burst and advance the gameplay timer.
    cpu=cpu.replace('void sh4_poll_irq(SH4CPU *cpu) {','void port_aica_update_at(DCHardware*,uint64_t);\nvoid sh4_poll_irq(SH4CPU *cpu) {')
    cpu=cpu.replace('dc_aica_update(g_hardware);','port_aica_update_at(g_hardware,(uint64_t)(now*1000.0));')
    cpu=cpu.replace('void sh4_credit_elapsed_ms(uint32_t ms) {', 'void sh4_credit_elapsed_ms(uint32_t ms) {(void)ms;return;')
    begin=cpu.index('          uint64_t now = platform_get_ticks_ms();',cpu.index('if (vpolls > 0)'))
    end=cpu.index('          }\n          }',begin)+len('          }')
    cpu=cpu[:begin]+scheduler.clock_poll()+cpu[end:]
    (output/'cpu.c').write_text(cpu)
    (output/'fault.c').write_text('void sh4_dump_native_stack(const char *tag) {(void)tag;}\nvoid sh4_install_crash_handler(void) {}\n')
    sources=sorted((generated/'src').glob('*.c'))+[local/'unresolved.c',output/'cpu.c',core/'src/recompiler/sh4_task.c',kit/'runtime/runner.c',kit/'runtime/vmu.c',output/'fault.c']
    sources += [p for p in (core/'src/hal').glob('*.c') if p.name not in ('pvr2_render.c','pvr2_ta.c','dc_bios.c','dc_hardware.c')]+[output/'renderer.c',output/'platform.c',output/'bios.c',output/'ta.c',output/'hardware.c']
    optimized=bool(getattr(args,'optimize',False)) and not args.abi
    optimization=['-O3','-flto=thin'] if optimized else ['-O2']
    simd=bool(getattr(args,'simd',False))
    if simd:optimization+=['-msimd128']
    link_optimization=optimization+([] if not optimized else ['-Wl,--thinlto-jobs=3','-Wl,--thinlto-cache-dir='+str(output/'thinlto-cache')])
    flags=[*optimization,'-fno-strict-aliasing','-fwrapv','-std=c11','-include','time.h','-DHAS_OPENGL','-Wno-unused-value','-Wno-parentheses-equality','-sOFFSCREENCANVAS_SUPPORT=1','-I',str(include),'-I',str(local/'include'),'-I',str(generated/'include'),'-I',str(core/'include'),'-I',str(kit/'runtime')]
    if args.abi:flags+=['-DDCRECOMP_ABI_CHECK']
    objects=output/('obj-simd' if simd else 'obj');objects.mkdir(exist_ok=True)
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
    assertions=bool(args.abi or getattr(args,'assertions',False))
    variants={}
    for suspension in (('asyncify','jspi') if getattr(args,'jspi',False) else ('asyncify',)):
        stem='game' if suspension=='asyncify' else 'game-jspi'
        suspension_flags=['-sJSPI=1'] if suspension=='jspi' else ['-sASYNCIFY=1','-sASYNCIFY_STACK_SIZE=4194304']
        result=subprocess.run([sys.executable,str(emcc),*map(str,compiled),*link_optimization,'-g2','-sENVIRONMENT=worker','-sOFFSCREENCANVAS_SUPPORT=1','-sMIN_SAFARI_VERSION=170000','-sMIN_WEBGL_VERSION=2','-sMAX_WEBGL_VERSION=2',*suspension_flags,'-sSTACK_SIZE=16777216','-sINITIAL_MEMORY=134217728','-sALLOW_MEMORY_GROWTH=1','-sMAXIMUM_MEMORY=1073741824','-sASSERTIONS='+('2' if assertions else '0'),'-sSTACK_OVERFLOW_CHECK='+('2' if assertions else '0'),'--embed-file',str(exe)+'@/game.bin','-o',str(output/(stem+'.next.js'))],capture_output=True,text=True)
        (output/(stem+'-link.log')).write_text(result.stdout+result.stderr)
        if result.returncode:raise error('WebAssembly '+suspension+' link: '+result.stderr[-2500:])
        bundle=publish_bundle(output,stem)
        if suspension=='jspi':variants['jspi']=bundle
    write_json(output/'build.json',{'target':'browser-webgl2','suspension':'asyncify','variants':variants,'features':{'vmu':2,'ramReadFastPath':1,'idleCooperation':1,'discCacheSlots':16,'wasmSIMD':int(simd),'immutableTextures':1,'vertexStreamSlots':3,'highPerformanceGPURequested':1},'execution':'dedicated-worker-offscreen','optimization':'O2-debug' if args.abi else 'O3-thinlto' if optimized else 'O2','playable':False,'abiChecks':bool(args.abi),'assertions':assertions,'scheduler':'message-channel-8ms','sourceSetSHA256':json.loads((project/'port.json').read_text())['sourceSetSHA256'],'wasmSHA256':hashlib.sha256((output/'game.wasm').read_bytes()).hexdigest()})
    publish_web_assets(kit,project,output)
    print('Browser build ready. Run serve-browser; gameplay remains unverified.')
