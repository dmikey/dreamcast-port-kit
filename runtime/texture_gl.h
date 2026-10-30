/* Runtime texture decode for the existing PVR2 renderer: direct-color and VQ.
 * Texture pixels come from the game's current VRAM, not exported substitutes. */
static unsigned port_spread(unsigned x) {unsigned v=0;for(unsigned b=0;b<10;b++)v|=((x>>b)&1)<<(b*2);return v;}
static unsigned port_twiddle(unsigned x,unsigned y,unsigned w,unsigned h) {
    unsigned m=w<h?w:h;return (x/m+y/m)*m*m+(port_spread(x%m)<<1)+port_spread(y%m);
}
static unsigned char port_texels[1024*1024*4];
#include <stdlib.h>
#include <string.h>
static struct {
    GLuint id;uint32_t tcw,tsp,frame,palette[256];
    unsigned char *source;unsigned length,palette_format;
} port_cache[128];
static unsigned port_texture_count,port_texture_frame,port_palette_format;
static uint32_t port_palette[1024];
static void port_begin_textures(void) {
    port_texture_frame++;
    port_palette_format=dc_hw_read32(sh4_get_hardware(),0x005f8108)&3;
    for(unsigned i=0;i<1024;i++)port_palette[i]=dc_hw_read32(sh4_get_hardware(),0x005f9000+i*4);
}
static GLuint port_texture(uint32_t tcw,uint32_t tsp) {
    int cached=-1;
    for(unsigned i=0;i<port_texture_count;i++)if(port_cache[i].tcw==tcw && port_cache[i].tsp==tsp){cached=i;break;}
    if(cached>=0 && port_cache[cached].frame==port_texture_frame)return port_cache[cached].id;
    unsigned w=8<<((tsp>>3)&7),h=8<<(tsp&7),fmt=(tcw>>27)&7;
    unsigned base=(tcw&0x1fffff)*8,linear=(tcw>>26)&1,vq=(tcw>>30)&1,mip=tcw>>31;
    int paletted=fmt==5 || fmt==6;
    if(paletted){linear=0;vq=0;}
    unsigned palette_format=port_palette_format;
    unsigned offset=0;
    if(mip) {if(vq){offset=1;for(unsigned s=2;s<w;s*=2)offset+=(s/2)*(s/2);}else{offset=6;for(unsigned s=2;s<w;s*=2)offset+=s*s*2;}}
    const unsigned char *vram=sh4_get_vram_ptr();
    unsigned length=vq?2048+offset+w*h/4:offset+(paletted?(fmt==5?w*h/2:w*h):w*h*2);
    unsigned bank=fmt==5?((tcw>>21)&63)*16:((tcw>>25)&3)*256;
    unsigned colors=fmt==5?16:256;
    if(cached>=0 && base+length<=0x800000 && port_cache[cached].length==length &&
       memcmp(port_cache[cached].source,vram+base,length)==0 &&
       (!paletted || (port_cache[cached].palette_format==palette_format && memcmp(port_cache[cached].palette,port_palette+bank,colors*4)==0))) {
        port_cache[cached].frame=port_texture_frame;return port_cache[cached].id;
    }
    if(cached<0) {
        if(port_texture_count<128)cached=port_texture_count++;
        else {cached=0;for(unsigned i=1;i<128;i++)if(port_cache[i].frame<port_cache[cached].frame)cached=i;}
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
            if(fmt==5) {unsigned packed=vram[(base+index/2)&0x7fffff];entry=((packed>>((index&1)*4))&15)+((tcw>>21)&63)*16;}
            else entry=vram[(base+index)&0x7fffff]+((tcw>>25)&3)*256;
            p=port_palette[entry];pf=palette_format;
        }
        if(pf==0){out[0]=((p>>10)&31)*255/31;out[1]=((p>>5)&31)*255/31;out[2]=(p&31)*255/31;out[3]=(p&0x8000)?255:0;}
        else if(pf==1){out[0]=((p>>11)&31)*255/31;out[1]=((p>>5)&63)*255/63;out[2]=(p&31)*255/31;out[3]=255;}
        else if(pf==2){out[0]=((p>>8)&15)*17;out[1]=((p>>4)&15)*17;out[2]=(p&15)*17;out[3]=((p>>12)&15)*17;}
        else if(pf==3 && paletted){out[0]=(p>>16)&255;out[1]=(p>>8)&255;out[2]=p&255;out[3]=p>>24;}
        else {out[0]=255;out[1]=0;out[2]=255;out[3]=255;}
    }
    if(!port_cache[cached].id)glGenTextures(1,&port_cache[cached].id);
    GLuint tex=port_cache[cached].id;glBindTexture(GL_TEXTURE_2D,tex);
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,(tsp&(1<<15))?GL_CLAMP_TO_EDGE:(tsp&(1<<17))?GL_MIRRORED_REPEAT:GL_REPEAT);
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,(tsp&(1<<16))?GL_CLAMP_TO_EDGE:(tsp&(1<<18))?GL_MIRRORED_REPEAT:GL_REPEAT);
    glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA,w,h,0,GL_RGBA,GL_UNSIGNED_BYTE,port_texels);
    free(port_cache[cached].source);port_cache[cached].source=malloc(length);
    if(!port_cache[cached].source)abort();
    unsigned first=length<0x800000-base?length:0x800000-base;
    memcpy(port_cache[cached].source,vram+base,first);
    if(first<length)memcpy(port_cache[cached].source+first,vram,length-first);
    port_cache[cached].length=length;port_cache[cached].tcw=tcw;port_cache[cached].tsp=tsp;port_cache[cached].frame=port_texture_frame;
    port_cache[cached].palette_format=palette_format;
    if(paletted)memcpy(port_cache[cached].palette,port_palette+bank,colors*4);
    return tex;
}
static void port_draw_materials(const PVR2TriList *list,int list_type) {
    for(int at=0;at<list->count;) {
        const PVR2RenderVertex *v=list->vertices+at;int end=at+3;
        while(end<list->count && list->vertices[end].tcw==v->tcw && list->vertices[end].tsp==v->tsp && list->vertices[end].pcw==v->pcw)end+=3;
        int textured=(v->pcw>>3)&1;
        glUniform1i(glGetUniformLocation(g_shader,"uTextured"),textured);
        glUniform1i(glGetUniformLocation(g_shader,"uShading"),(v->tsp>>6)&3);
        glUniform1i(glGetUniformLocation(g_shader,"uIgnoreAlpha"),(v->tsp>>19)&1);
        glUniform1i(glGetUniformLocation(g_shader,"uUseAlpha"),(v->tsp>>20)&1);
        glUniform1i(glGetUniformLocation(g_shader,"uPunch"),list_type==PVR2_LIST_PUNCHTHRU);
        if(textured){glActiveTexture(GL_TEXTURE0);glBindTexture(GL_TEXTURE_2D,port_texture(v->tcw,v->tsp));}
        glDrawArrays(GL_TRIANGLES,at,end-at);at=end;
    }
}
