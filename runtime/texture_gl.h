/* Runtime texture decode for the existing PVR2 renderer: direct-color and VQ.
 * Texture pixels come from the game's current VRAM, not exported substitutes. */
static unsigned port_spread(unsigned x) {x&=0x3ff;x=(x|(x<<8))&0x00ff00ff;x=(x|(x<<4))&0x0f0f0f0f;x=(x|(x<<2))&0x33333333;return (x|(x<<1))&0x55555555;}
static unsigned port_twiddle(unsigned x,unsigned y,unsigned w,unsigned h) {
    unsigned m=w<h?w:h;return (x/m+y/m)*m*m+(port_spread(x%m)<<1)+port_spread(y%m);
}
static unsigned char port_texels[1024*1024*4];
#include <stdlib.h>
#include <string.h>
static struct {
    GLuint id;uint32_t tcw,tsp,frame,palette[256];
    uint64_t used;unsigned image_bytes,storage_w,storage_h;int valid;
    unsigned char *source;unsigned length,palette_format;
} port_cache[512];
#define PORT_TEXTURE_GPU_BUDGET (64u*1024*1024)
#define PORT_TEXTURE_SOURCE_BUDGET (16u*1024*1024)
static unsigned port_texture_gpu_bytes,port_texture_source_bytes;
static uint64_t port_texture_serial,port_texture_uploads;
static void port_evict_texture(unsigned slot,int delete_id) {
    if(port_cache[slot].valid){port_texture_gpu_bytes-=port_cache[slot].image_bytes;port_texture_source_bytes-=port_cache[slot].length;}
    free(port_cache[slot].source);port_cache[slot].source=NULL;port_cache[slot].valid=0;
    if(delete_id && port_cache[slot].id){glDeleteTextures(1,&port_cache[slot].id);port_cache[slot].id=0;}
}
static unsigned port_texture_count,port_texture_frame,port_palette_format;
static uint32_t port_palette[1024];
static void port_begin_textures(void) {
    port_texture_frame++;
    port_palette_format=dc_hw_read32(sh4_get_hardware(),0x005f8108)&3;
    for(unsigned i=0;i<1024;i++)port_palette[i]=dc_hw_read32(sh4_get_hardware(),0x005f9000+i*4);
}
static GLuint port_texture(uint32_t tcw,uint32_t tsp) {
    /* Blend, shading and alpha flags do not change texture pixels or wrapping. */
    tsp&=0x0007803f;
    int cached=-1;
    for(unsigned i=0;i<port_texture_count;i++)if(port_cache[i].valid && port_cache[i].tcw==tcw && port_cache[i].tsp==tsp){cached=i;break;}
    if(cached>=0)port_cache[cached].used=++port_texture_serial;
    if(cached>=0 && port_cache[cached].frame==port_texture_frame)return port_cache[cached].id;
    unsigned w=8<<((tsp>>3)&7),h=8<<(tsp&7),fmt=(tcw>>27)&7;
    unsigned base=((tcw&0x1fffff)*8)&0x7fffff,linear=(tcw>>26)&1,vq=(tcw>>30)&1,mip=tcw>>31;
    int paletted=fmt==5 || fmt==6;
    if(paletted){linear=0;vq=0;}
    unsigned palette_format=port_palette_format;
    if(linear && !vq)mip=0;
    if(mip)h=w;
    unsigned offset=0;
    if(mip) {if(vq){offset=1;for(unsigned s=2;s<w;s*=2)offset+=(s/2)*(s/2);}else{unsigned pixels=4;for(unsigned s=2;s<w;s*=2)pixels+=s*s;offset=paletted?(fmt==5?pixels/2:pixels):pixels*2;}}
    const unsigned char *vram=sh4_get_vram_ptr();
    unsigned length=vq?2048+offset+w*h/4:offset+(paletted?(fmt==5?w*h/2:w*h):w*h*2);
    unsigned bank=fmt==5?((tcw>>21)&63)*16:((tcw>>25)&3)*256;
    unsigned colors=fmt==5?16:256;
    unsigned first=length<0x800000-base?length:0x800000-base;
    if(cached>=0 && port_cache[cached].length==length &&
       memcmp(port_cache[cached].source,vram+base,first)==0 &&
       (first==length || memcmp(port_cache[cached].source+first,vram,length-first)==0) &&
       (!paletted || (port_cache[cached].palette_format==palette_format && memcmp(port_cache[cached].palette,port_palette+bank,colors*4)==0))) {
        port_cache[cached].frame=port_texture_frame;return port_cache[cached].id;
    }
    if(cached<0) {
        for(unsigned i=0;i<port_texture_count;i++)if(!port_cache[i].valid){cached=i;break;}
        if(cached<0 && port_texture_count<512)cached=port_texture_count++;
        if(cached<0){cached=0;for(unsigned i=1;i<port_texture_count;i++)if(port_cache[i].used<port_cache[cached].used)cached=i;}
    }
    port_evict_texture(cached,0);
    unsigned image_bytes=w*h*4;
    while(port_texture_gpu_bytes+image_bytes>PORT_TEXTURE_GPU_BUDGET || port_texture_source_bytes+length>PORT_TEXTURE_SOURCE_BUDGET){
        int oldest=-1;
        for(unsigned i=0;i<port_texture_count;i++)if((int)i!=cached && port_cache[i].valid && (oldest<0 || port_cache[i].used<port_cache[oldest].used))oldest=i;
        if(oldest<0)abort();port_evict_texture(oldest,1);
    }
    for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++) {
        unsigned pixel;
        if(vq) {unsigned i=offset+port_twiddle(x/2,y/2,w/2,h/2);unsigned code=vram[(base+2048+i)&0x7fffff];pixel=code*4+((x&1)*2)+(y&1);}
        else pixel=linear?y*w+x:port_twiddle(x,y,w,h);
        unsigned address=(base+(vq?0:offset)+pixel*2)&0x7fffff;
        unsigned p=vram[address]|(vram[(address+1)&0x7fffff]<<8);
        unsigned char *out=port_texels+(y*w+x)*4;
        unsigned pf=fmt;
        if(paletted) {
            unsigned index=port_twiddle(x,y,w,h);
            unsigned entry;
            if(fmt==5) {unsigned packed=vram[(base+offset+index/2)&0x7fffff];entry=((packed>>((index&1)*4))&15)+((tcw>>21)&63)*16;}
            else entry=vram[(base+offset+index)&0x7fffff]+((tcw>>25)&3)*256;
            p=port_palette[entry];pf=palette_format;
        }
        if(pf==0){out[0]=((p>>10)&31)*255/31;out[1]=((p>>5)&31)*255/31;out[2]=(p&31)*255/31;out[3]=(p&0x8000)?255:0;}
        else if(pf==1){out[0]=((p>>11)&31)*255/31;out[1]=((p>>5)&63)*255/63;out[2]=(p&31)*255/31;out[3]=255;}
        else if(pf==2){out[0]=((p>>8)&15)*17;out[1]=((p>>4)&15)*17;out[2]=(p&15)*17;out[3]=((p>>12)&15)*17;}
        else if(pf==3 && paletted){out[0]=(p>>16)&255;out[1]=(p>>8)&255;out[2]=p&255;out[3]=p>>24;}
        else {out[0]=255;out[1]=0;out[2]=255;out[3]=255;}
    }
    if(port_cache[cached].id && (port_cache[cached].storage_w!=w || port_cache[cached].storage_h!=h)){
        glDeleteTextures(1,&port_cache[cached].id);port_cache[cached].id=0;
    }
    int allocate=!port_cache[cached].id;
    if(allocate)glGenTextures(1,&port_cache[cached].id);
    GLuint tex=port_cache[cached].id;glBindTexture(GL_TEXTURE_2D,tex);
    if(allocate){glTexStorage2D(GL_TEXTURE_2D,1,GL_RGBA8,w,h);port_cache[cached].storage_w=w;port_cache[cached].storage_h=h;}
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,(tsp&(1<<16))?GL_CLAMP_TO_EDGE:(tsp&(1<<18))?GL_MIRRORED_REPEAT:GL_REPEAT);
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,(tsp&(1<<15))?GL_CLAMP_TO_EDGE:(tsp&(1<<17))?GL_MIRRORED_REPEAT:GL_REPEAT);
    glTexSubImage2D(GL_TEXTURE_2D,0,0,0,w,h,GL_RGBA,GL_UNSIGNED_BYTE,port_texels);
    port_cache[cached].source=malloc(length);
    if(!port_cache[cached].source)abort();
    memcpy(port_cache[cached].source,vram+base,first);
    if(first<length)memcpy(port_cache[cached].source+first,vram,length-first);
    port_cache[cached].valid=1;port_cache[cached].used=++port_texture_serial;port_cache[cached].image_bytes=image_bytes;
    port_texture_gpu_bytes+=image_bytes;port_texture_source_bytes+=length;port_texture_uploads++;
    port_cache[cached].length=length;port_cache[cached].tcw=tcw;port_cache[cached].tsp=tsp;port_cache[cached].frame=port_texture_frame;
    port_cache[cached].palette_format=palette_format;
    if(paletted)memcpy(port_cache[cached].palette,port_palette+bank,colors*4);
    return tex;
}
static uint64_t port_draw_calls;
static int port_same_material(const PVR2RenderVertex *a,const PVR2RenderVertex *b) {
    unsigned textured=a->pcw&8;
    if(textured!=(b->pcw&8) || ((a->isp^b->isp)&0xfc000000u))return 0;
    /* Only shader/blend flags matter without a texture. Unused address/size
     * bits often differ between otherwise identical adjacent triangles. */
    unsigned mask=0xfc1800c0u | (textured?0x0007803fu:0);
    return !((a->tsp^b->tsp)&mask) && (!textured || a->tcw==b->tcw);
}
static void port_draw_materials(const PVR2TriList *list,int list_type) {
    static GLuint shader;static GLint locations[5];
    if(shader!=g_shader){
        const char *names[]={"uTextured","uShading","uIgnoreAlpha","uUseAlpha","uPunch"};
        for(int i=0;i<5;i++)locations[i]=glGetUniformLocation(g_shader,names[i]);shader=g_shader;
    }
    /* Other presenters/list setup can change GL state; invalidate per list. */
    int uniforms[5]={-1,-1,-1,-1,-1},last_depth=-1,last_write=-1,last_cull=-1;
    unsigned last_blend=~0u;GLuint last_texture=0;
    glActiveTexture(GL_TEXTURE0);

    for(int at=0;at<list->count;) {
        const PVR2RenderVertex *v=list->vertices+at;int end=at+3;
        while(end<list->count && port_same_material(v,list->vertices+end))end+=3;
        static const GLenum depth_modes[]={GL_NEVER,GL_LESS,GL_EQUAL,GL_LEQUAL,GL_GREATER,GL_NOTEQUAL,GL_GEQUAL,GL_ALWAYS};
        /* PVR signed-area culling for the expanded triangle-list winding.
         * Flycast gldraw.cpp documents modes 2/3 as negative/positive. */
        int cull=(v->isp>>27)&3;
        if(cull!=last_cull){if(cull<2)glDisable(GL_CULL_FACE);else{glEnable(GL_CULL_FACE);glCullFace(cull==2?GL_FRONT:GL_BACK);}last_cull=cull;}
        int depth=(v->isp>>29)&7,write=!(list_type==PVR2_LIST_TRANS || (v->isp&(1u<<26)));
        if(depth!=last_depth){glDepthFunc(depth_modes[depth]);last_depth=depth;}
        if(write!=last_write){glDepthMask(write?GL_TRUE:GL_FALSE);last_write=write;}
        { /* Blend instructions also apply to opaque lighting passes. */
            static const GLenum src_modes[]={GL_ZERO,GL_ONE,GL_DST_COLOR,GL_ONE_MINUS_DST_COLOR,GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA,GL_DST_ALPHA,GL_ONE_MINUS_DST_ALPHA};
            static const GLenum dst_modes[]={GL_ZERO,GL_ONE,GL_SRC_COLOR,GL_ONE_MINUS_SRC_COLOR,GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA,GL_DST_ALPHA,GL_ONE_MINUS_DST_ALPHA};
            unsigned blend=v->tsp>>26;
            if(blend!=last_blend){glBlendFunc(src_modes[v->tsp>>29],dst_modes[(v->tsp>>26)&7]);last_blend=blend;}
        }
        int textured=(v->pcw>>3)&1;
        int values[]={textured,(v->tsp>>6)&3,(v->tsp>>19)&1,(v->tsp>>20)&1,list_type==PVR2_LIST_PUNCHTHRU};
        for(int i=0;i<5;i++)if(values[i]!=uniforms[i]){glUniform1i(locations[i],values[i]);uniforms[i]=values[i];}
        if(textured){GLuint texture=port_texture(v->tcw,v->tsp);if(texture!=last_texture){glActiveTexture(GL_TEXTURE0);glBindTexture(GL_TEXTURE_2D,texture);last_texture=texture;}}
        glDrawArrays(GL_TRIANGLES,at,end-at);port_draw_calls++;at=end;
    }
}
