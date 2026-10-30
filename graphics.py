"""Shared PVR2 material/UV preservation and runtime texture rendering adapters."""
from pathlib import Path

def adapt(core,output,include,renderer):
    (include/'hal').mkdir(exist_ok=True)
    header=(core/'include/hal/pvr2.h').read_text().replace('float r, g, b, a;    /* Base color (RGBA 0-1) */','float r, g, b, a;    /* Base color (RGBA 0-1) */\n    uint32_t pcw,tsp,tcw,isp;')
    (include/'hal/pvr2.h').write_text(header)
    ta=(core/'src/hal/pvr2_ta.c').read_text().replace('    tl->vertices[tl->count++] = *v;','    PVR2RenderVertex out=*v;out.pcw=g_ta.pcw;out.tsp=g_ta.tsp;out.tcw=g_ta.tcw;out.isp=g_ta.isp;\n    tl->vertices[tl->count++] = out;')
    ta=ta.replace('        v.u = 0; v.v = 0;','        c.u=data[4]&0xffff0000;v.u=c.f;c.u=data[4]<<16;v.v=c.f;')
    ta=ta.replace('        /* Two triangles, sharing the A-C diagonal. */','''        if(g_ta.vert_type==16) {
            for(int k=0;k<3;k++) {c.u=data[13+k]&0xffff0000;q[k].u=c.f;c.u=data[13+k]<<16;q[k].v=c.f;}
            q[3].u=q[0].u+q[2].u-q[1].u;q[3].v=q[0].v+q[2].v-q[1].v;
        }
        /* Two triangles, sharing the A-C diagonal. */''')
    ta=ta.replace('    case 5: /* Textured, float RGBA, 32-bit UV (64-byte) */','    case 6: /* Textured, float RGBA, 16-bit UV (64-byte) */\n    case 5: /* Textured, float RGBA, 32-bit UV (64-byte) */')
    marker='        /* Colors in second 32 bytes (data[8..11]) */'
    ta=ta.replace(marker,'        if(g_ta.vert_type==6){c.u=data[4]&0xffff0000;v.u=c.f;c.u=data[4]<<16;v.v=c.f;}\n'+marker)
    # The first material of two-volume vertices has the same textured layout.
    ta=ta.replace('    case 3: /* Textured, packed', '    case 11: /* First volume */\n    case 3: /* Textured, packed')
    ta=ta.replace('    case 4: /* Textured, packed', '    case 12: /* First volume */\n    case 4: /* Textured, packed')
    ta=ta.replace('    case 7: /* Textured, intensity', '    case 13: /* First volume */\n    case 7: /* Textured, intensity')
    ta=ta.replace('    case 8: /* Textured, intensity', '    case 14: /* First volume */\n    case 8: /* Textured, intensity')
    ta=ta.replace('    case 0: /* Non-textured, packed', '    case 9: /* First volume */\n    case 0: /* Non-textured, packed')
    ta=ta.replace('unpack_color(data[6], &v.r, &v.g, &v.b, &v.a);', 'unpack_color(data[g_ta.vert_type==9?4:6], &v.r, &v.g, &v.b, &v.a);')
    ta=ta.replace('    case 2: /* Non-textured, intensity', '    case 10: /* First volume */\n    case 2: /* Non-textured, intensity')
    ta=ta.replace('        c.u = data[6]; {', '        c.u = data[g_ta.vert_type==10?4:6]; {')
    ta=ta.replace('    case 15: case 16:    /* Sprite */', '    case 17: /* Modifier volume */\n    case 15: case 16:    /* Sprite */')
    ta=ta.replace('    PVR2RenderVertex v = {0};', '    if(g_ta.vert_type==17)return; /* Consume complete packet; shadow stencil pending. */\n    PVR2RenderVertex v = {0};')
    ta=ta.replace('if (col_type == 2 || col_type == 3)', 'if (col_type == 2)') # Color type 3 reuses the previous face color.
    (output/'ta.c').write_text(ta)
    renderer=renderer.replace('    "out vec4 vColor;\\n"','    "out vec4 vColor;\\nout vec2 vUV;\\n"')
    renderer=renderer.replace('    "    vColor = aColor;\\n"','    "    vColor = aColor; vUV = aUV;\\n"')
    renderer=renderer.replace('    "in vec4 vColor;\\n"','    "in vec4 vColor;\\nin vec2 vUV;\\nuniform sampler2D uTexture;\\nuniform int uTextured,uShading,uIgnoreAlpha,uUseAlpha,uPunch;\\n"')
    renderer=renderer.replace('    "    FragColor = vColor;\\n"','''    "    vec4 base=vColor; if(uUseAlpha==0)base.a=1.0; vec4 result=base;\\n"
    "    if(uTextured!=0){vec4 t=texture(uTexture,vUV);if(uIgnoreAlpha!=0)t.a=1.0;\\n"
    "    if(uShading==0)result=t;else if(uShading==1)result=vec4(t.rgb*base.rgb,t.a);else if(uShading==2)result=vec4(mix(base.rgb,t.rgb,t.a),base.a);else result=t*base;}\\n"
    "    if(uPunch!=0 && result.a<0.5)discard;FragColor=result;\\n"''')
    renderer=renderer.replace('#include \"recompiler/sh4_cpu.h\"','#include \"recompiler/sh4_cpu.h\"\n#include \"hal/dc_hardware.h\"')
    renderer=renderer.replace('void pvr2_render_frame(void) {','#include "texture_gl.h"\n\nvoid pvr2_render_frame(void) {\n    port_begin_textures();')
    renderer=renderer.replace('glDrawArrays(GL_TRIANGLES, 0, list->count);','port_draw_materials(list,draw_order[i]);')
    renderer=renderer.replace('void pvr2_render_frame(void) {','void pvr2_render_frame(void) {\n    glEnable(GL_DEPTH_TEST); /* Framebuffer scanout disables it. */')
    renderer=renderer.replace('glDepthFunc(GL_LEQUAL);','glDepthFunc(GL_GEQUAL);glClearDepthf(0.0f);')
    renderer=renderer.replace('clamp(aPos.z * 0.0001, 0.0, 1.0)','clamp(aPos.z / (1.0 + max(aPos.z,0.0)), 0.0, 1.0)')
    renderer=renderer.replace('#include "texture_gl.h"', '#include "texture_gl.h"\n#include <emscripten.h>\nstatic int port_capture_samples;\nEMSCRIPTEN_KEEPALIVE void port_render_capture(void){port_capture_samples=128;}')
    renderer=renderer.replace('port_draw_materials(list,draw_order[i]);', '''{
            uint32_t last_tcw=~0u,last_pcw=~0u,last_tsp=~0u;
            for(int n=0;n<list->count && port_capture_samples>0;n+=3){
                const PVR2RenderVertex *v=list->vertices+n;
                if(v->tcw==last_tcw && v->pcw==last_pcw && v->tsp==last_tsp)continue;
                last_tcw=v->tcw;last_pcw=v->pcw;last_tsp=v->tsp;port_capture_samples--;
                printf("[MATERIAL] list=%d pcw=%08X isp=%08X tsp=%08X tcw=%08X z=%.6f uv=%.3f,%.3f rgba=%.3f,%.3f,%.3f,%.3f\\n",draw_order[i],v->pcw,v->isp,v->tsp,v->tcw,v->z,v->u,v->v,v->r,v->g,v->b,v->a);
            }
            port_draw_materials(list,draw_order[i]);
        }''')
    renderer=renderer.replace('#include "texture_gl.h"', '#include "transparency.h"\n#include "texture_gl.h"')
    renderer=renderer.replace('        /* Upload vertex data */', '        if(draw_order[i]==PVR2_LIST_TRANS && !(dc_hw_read32(sh4_get_hardware(),0x005f8098)&1))port_sort_transparent(list);\n        /* Upload vertex data */')
    renderer=renderer.replace('#include "transparency.h"', '#include "platform/platform.h"\n#include "transparency.h"')
    renderer=renderer.replace('    port_begin_textures();', '    uint64_t port_render_started=platform_get_ticks_us();\n    port_begin_textures();')
    renderer=renderer.replace('    glUseProgram(0);\n}', '    glUseProgram(0);\n    static uint64_t total_us,max_us,reported,uploads;static unsigned frames;\n    uint64_t now=platform_get_ticks_us(),elapsed=now-port_render_started;\n    total_us+=elapsed;if(elapsed>max_us)max_us=elapsed;frames++;\n    if(now-reported>=5000000){printf("[RENDER] frames=%u submit_avg_us=%llu submit_max_us=%llu window_us=%llu tex_uploads=%llu tex_gpu_bytes=%u\\n",frames,(unsigned long long)(total_us/frames),(unsigned long long)max_us,(unsigned long long)(now-reported),(unsigned long long)(port_texture_uploads-uploads),port_texture_gpu_bytes);uploads=port_texture_uploads;reported=now;total_us=max_us=0;frames=0;}\n}')
    return renderer
