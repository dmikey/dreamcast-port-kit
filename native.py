"""Native build/run stages shared by all exact-hash title profiles."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import shlex
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time


def build(args, kit, error, verify, write_json):
    project, core = Path(args.project).resolve(), Path(args.toolchain).resolve()
    manifest, exe = verify(project)
    profile = None
    for p in (kit / 'profiles').glob('*.json'):
        candidate = json.loads(p.read_text())
        if candidate['id'] == manifest['profileId']: profile = candidate
    if profile is None and (project / 'title-profile.json').exists():
        profile = json.loads((project / 'title-profile.json').read_text())
    required = ['loadAddress','runtimeEntry','irqEntry','irqPushRegisters','stackPointer','vectorBase','ramBytes']
    missing=[k for k in required if not profile or profile.get(k) is None]
    if missing:
        raise error('Native bring-up requires verified title-profile fields: ' + ', '.join(missing))
    if profile['executableSHA1'] != manifest['executable']['sha1']:
        raise error('Title profile is for a different executable')
    generated = project / '.local/generated'
    provenance = json.loads((generated / 'provenance.json').read_text())
    if provenance.get('sourceSetSHA256')!=manifest.get('sourceSetSHA256'):
        raise error('Source disc changed after translation; regenerate to bind the current input')
    current_diff=subprocess.run(['git','-C',str(core),'diff','--binary'],check=True,capture_output=True).stdout
    if hashlib.sha256(current_diff).hexdigest()!=provenance['localPatchSHA256']:
        raise error('Toolchain changed after translation; regenerate with the reviewed patch set')
    for name, expected in provenance['sourceHashes'].items():
        if hashlib.sha256((generated / 'src' / name).read_bytes()).hexdigest() != expected:
            raise error('Generated source changed after translation; regenerate it with the reviewed patches')
    native = project / '.local/native';native.mkdir(exist_ok=True)
    header = generated / 'include/game/game_functions.h'
    body = '\n'.join(p.read_text() for p in (generated / 'src').glob('game_code_*.c'))
    defined = set(re.findall(r'void (func_[0-9A-F]{8})\(SH4CPU \*cpu\)\s*\{',body))
    refs = set(re.findall(r'\b(func_[0-9A-F]{8})\b',body))
    absent = sorted(refs-defined)
    declarations = ''.join(f'void {name}(SH4CPU *cpu);\n' for name in absent)
    # Keep generated source immutable: declarations injected through an overlay header.
    overlay = native / 'include/game';overlay.mkdir(parents=True,exist_ok=True)
    original = header.read_text();at=original.rfind('#endif')
    (overlay / 'game_functions.h').write_text(original[:at]+declarations+original[at:])
    source = '#include "game/game_functions.h"\n#include <stdio.h>\n#include <stdlib.h>\n'
    for name in absent:
        source += f'void {name}(SH4CPU *c) {{fprintf(stderr,"[UNIMPLEMENTED] {name} pr=%08X\\n",c->pr);abort();}}\n'
    (native / 'unresolved.c').write_text(source)
    write_json(native / 'unresolved.json',absent)
    lock=json.loads((project / '.local/source-lock.json').read_text())
    tracks=lock['tracks']
    if any(t['sectorBytes']!=2352 or t['offset'] for t in tracks):
        raise error('Native BIOS reader currently requires raw 2352-byte tracks with zero byte offset; the disc inspector supports additional formats')
    pushes=profile['irqPushRegisters']
    if not pushes or any(type(i)!=int or i<0 or i>15 for i in pushes):
        raise error('IRQ push register list must contain explicit register numbers 0..15')
    address=lambda key:int(profile[key],0)
    for key in ['loadAddress','runtimeEntry','irqEntry','stackPointer','vectorBase']:
        if not 0<=address(key)<=0xffffffff or address(key)%2: raise error('Invalid address in title profile: '+key)
    defines={'PORT_TITLE':json.dumps(profile['title']), 'PORT_EXECUTABLE':json.dumps(str(exe)),
        'PORT_RAM_BYTES':str(profile['ramBytes']), 'PORT_LOAD_ADDRESS':profile['loadAddress'],
        'PORT_RUNTIME_ENTRY':profile['runtimeEntry'],'PORT_ENTRY':f"func_{address('runtimeEntry'):08X}",
        'PORT_IRQ_ENTRY':f"func_{address('irqEntry'):08X}",'PORT_STACK_POINTER':profile['stackPointer'],
        'PORT_VECTOR_BASE':profile['vectorBase'],'PORT_SEGA_PATTERN':str(int(profile.get('biosSegaPattern',False))),
        'PORT_IRQ_PUSHES':'{'+','.join(map(str,pushes))+'}',
        'PORT_TRACK_PATHS':'{'+','.join(json.dumps(t['path']) for t in tracks)+'}',
        'PORT_TRACK_LBAS':'{'+','.join(str(t['lba']) for t in tracks)+'}'}
    (native / 'include/project.h').write_text(''.join(f'#define {k} {v}\n' for k,v in defines.items()))
    cpu=(core/'src/recompiler/sh4_cpu.c').read_text().replace(
        'void sh4_dump_native_stack(const char *tag) { (void)tag; }','/* provided by the port-kit POSIX diagnostic module */')
    (native / 'cpu.c').write_text(cpu)
    sources=sorted((generated/'src').glob('*.c'))+[native/'unresolved.c',native/'cpu.c',
        core/'src/recompiler/sh4_task.c',kit/'runtime/runner.c',kit/'runtime/posix.c']
    sources+=list((core/'src/hal').glob('*.c'))+[core/'src/platform/platform_sdl2.c']
    cc=shutil.which('clang') or shutil.which('cc')
    if not cc: raise error('A C11 compiler is required for native bring-up')
    flags=['-std=c11','-O0','-g','-include','time.h','-Wno-unused-value','-Wno-parentheses-equality',
           '-I',str(native/'include'),'-I',str(generated/'include'),'-I',str(core/'include')]
    graphic_links=[]
    if getattr(args,'graphics',False):
        config=shutil.which('sdl2-config')
        if not config and Path('/opt/homebrew/opt/sdl2/bin/sdl2-config').exists():
            config='/opt/homebrew/opt/sdl2/bin/sdl2-config'
        if not config: raise error('Graphics build requires SDL2 development files and sdl2-config')
        flags+=['-DHAS_SDL2','-DHAS_OPENGL']+shlex.split(subprocess.check_output([config,'--cflags'],text=True))
        graphic_links+=shlex.split(subprocess.check_output([config,'--libs'],text=True))
        if platform.system()=='Darwin':
            # macOS supplies OpenGL 4.1 directly; no GLEW initialization is needed.
            renderer=(core/'src/hal/pvr2_render.c').read_text().replace('#include <GL/glew.h>','#include <OpenGL/gl3.h>')
            begin=renderer.index('    /* Initialize GLEW */');end=renderer.index('    printf("[PVR2] OpenGL',begin)
            renderer=renderer[:begin]+renderer[end:]
            renderer=renderer.replace('#version 330 core','#version 410 core')
            (native/'renderer.c').write_text(renderer)
            layer=(core/'src/platform/platform_sdl2.c').read_text().replace('SDL_GL_CONTEXT_MAJOR_VERSION, 3','SDL_GL_CONTEXT_MAJOR_VERSION, 4').replace('SDL_GL_CONTEXT_MINOR_VERSION, 3','SDL_GL_CONTEXT_MINOR_VERSION, 1')
            (native/'platform.c').write_text(layer)
            sources=[native/'renderer.c' if p.name=='pvr2_render.c' else native/'platform.c' if p.name=='platform_sdl2.c' else p for p in sources]
            graphic_links+=['-framework','OpenGL']
        else:
            graphic_links+=['-lGLEW','-lGL']
    if args.abi: flags+=['-DDCRECOMP_ABI_CHECK']
    objdir=native/'obj';objdir.mkdir(exist_ok=True)
    headers=b''.join(p.read_bytes() for parent in [native/'include',generated/'include',core/'include'] for p in sorted(parent.rglob('*.h')))
    def compile_one(src):
        obj=objdir/(hashlib.sha256(str(src).encode()).hexdigest()[:10]+'_'+src.stem+'.o')
        stamp=obj.with_suffix('.sha')
        sha=hashlib.sha256(src.read_bytes()+headers+str(flags).encode()).hexdigest()
        if not obj.exists() or not stamp.exists() or stamp.read_text()!=sha:
            proc=subprocess.run([cc,*flags,'-c',str(src),'-o',str(obj)],capture_output=True,text=True)
            (obj.with_suffix('.log')).write_text(proc.stdout+proc.stderr)
            if proc.returncode: raise error(f'{src.name} compile failed: '+proc.stderr[:2000])
            stamp.write_text(sha)
        return obj
    with ThreadPoolExecutor(max_workers=4) as pool: objects=list(pool.map(compile_one,sources))
    linker=['-Wl,-stack_size,0x4000000'] if platform.system()=='Darwin' else []
    subprocess.run([cc,*map(str,objects),'-lm',*graphic_links,*linker,'-o',str(native/'game-headless')],check=True)
    write_json(native/'build.json',{'compiler':subprocess.run([cc,'--version'],capture_output=True,text=True).stdout.splitlines()[0],
       'executableSHA256':manifest['executable']['sha256'],'binarySHA256':hashlib.sha256((native/'game-headless').read_bytes()).hexdigest(),
       'target':'native-graphics' if getattr(args,'graphics',False) else 'native-headless','unresolvedTraps':len(absent),'titleProfile':profile,
       'toolchainProvenance':provenance,'playable':False})
    manifest['evidence']['compiled']=True;manifest['state']='compiled-unverified'
    write_json(project/'port.json',manifest)
    print('Native diagnostic runtime built; this does not prove a playable game.')


def run(args, error, verify, write_json):
    project=Path(args.project).resolve();manifest,_=verify(project)
    native=project/'.local/native';binary=native/'game-headless'
    receipt=json.loads((native/'build.json').read_text())
    if receipt['toolchainProvenance'].get('sourceSetSHA256')!=manifest.get('sourceSetSHA256'):
        raise error('Source set changed after the runtime build')
    source_lock=json.loads((project/'.local/source-lock.json').read_text())
    for track in source_lock['tracks']:
        h=hashlib.sha256()
        with Path(track['path']).open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
        if h.hexdigest()!=track['sha256']:raise error('Source track changed; re-import before running')
    if hashlib.sha256(binary.read_bytes()).hexdigest()!=receipt['binarySHA256']:
        raise error('Built runtime changed; rebuild before running')
    if not 0<args.seconds<=60: raise error('Use a bounded bring-up run between 1 and 60 seconds')
    capture=getattr(args,'capture_frame',None)
    env=os.environ.copy();frame=native/'frame.ppm'
    if capture is not None:
        if receipt['target']!='native-graphics': raise error('Frame capture requires a --graphics build')
        if capture<1: raise error('Capture frame must be positive')
        if frame.exists():frame.unlink()
        env['DCRECOMP_SCREENSHOT']=str(frame);env['DCRECOMP_SCREENSHOT_FRAME']=str(capture)
    log=native/'run.log';start=time.monotonic();timed_out=False
    with log.open('w') as output:
        process=subprocess.Popen([str(binary)],cwd=project,stdout=output,stderr=subprocess.STDOUT,env=env)
        try: code=process.wait(timeout=args.seconds)
        except subprocess.TimeoutExpired:
            timed_out=True;process.terminate()
            try:code=process.wait(timeout=3)
            except subprocess.TimeoutExpired:process.kill();code=process.wait()
    text=log.read_text()
    result={'elapsedSeconds':round(time.monotonic()-start,3),'exitCode':code,'boundedStop':timed_out,
       'exactExecutableLoaded':'[PORT] exact executable loaded:' in text,
       'titleCodeEntered':'[PORT] entering title code at' in text,
       'geometryPacketsObserved':'first frame with geometry:' in text,
       'unresolvedExecution':'[DISPATCH] unresolved' in text or '[UNIMPLEMENTED]' in text,
       'graphicsEnabled':receipt['target']=='native-graphics','frameCaptured':capture is not None and frame.exists(),
       'bootedToMenu':False,'playable':False,'browserPlayable':False,
       'logSHA256':hashlib.sha256(log.read_bytes()).hexdigest()}
    write_json(native/'run-result.json',result)
    print(json.dumps(result,indent=2))
    return 2 if result['unresolvedExecution'] or (code and not timed_out) else 0
