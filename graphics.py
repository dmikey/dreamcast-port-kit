"""Shared PVR2 material/UV preservation and runtime texture rendering adapters."""
from pathlib import Path

def adapt(core,output,include,renderer):
    (include/'hal').mkdir(exist_ok=True)
    header=(core/'include/hal/pvr2.h').read_text().replace('float r, g, b, a;    /* Base color (RGBA 0-1) */','float r, g, b, a;    /* Base color (RGBA 0-1) */\n    uint32_t pcw,tsp,tcw;')
    (include/'hal/pvr2.h').write_text(header)
    ta=(core/'src/hal/pvr2_ta.c').read_text().replace('    tl->vertices[tl->count++] = *v;','    PVR2RenderVertex out=*v;out.pcw=g_ta.pcw;out.tsp=g_ta.tsp;out.tcw=g_ta.tcw;\n    tl->vertices[tl->count++] = out;')
    ta=ta.replace('        v.u = 0; v.v = 0;','        c.u=data[4]&0xffff0000;v.u=c.f;c.u=data[4]<<16;v.v=c.f;')
    ta=ta.replace('        /* Two triangles, sharing the A-C diagonal. */','''        if(g_ta.vert_type==16) {
            for(int k=0;k<3;k++) {c.u=data[13+k]&0xffff0000;q[k].u=c.f;c.u=data[13+k]<<16;q[k].v=c.f;}
            q[3].u=q[0].u+q[2].u-q[1].u;q[3].v=q[0].v+q[2].v-q[1].v;
        }
        /* Two triangles, sharing the A-C diagonal. */''')
    ta=ta.replace('    case 5: /* Textured, float RGBA, 32-bit UV (64-byte) */','    case 6: /* Textured, float RGBA, 16-bit UV (64-byte) */\n    case 5: /* Textured, float RGBA, 32-bit UV (64-byte) */')
    marker='        /* Colors in second 32 bytes (data[8..11]) */'
    ta=ta.replace(marker,'        if(g_ta.vert_type==6){c.u=data[4]&0xffff0000;v.u=c.f;c.u=data[4]<<16;v.v=c.f;}\n'+marker)
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
    renderer=renderer.replace('glDepthFunc(GL_LEQUAL);','glDepthFunc(GL_GEQUAL);glClearDepthf(0.0f);')
    renderer=renderer.replace('clamp(aPos.z * 0.0001, 0.0, 1.0)','clamp(aPos.z / (1.0 + max(aPos.z,0.0)), 0.0, 1.0)')
    return renderer
