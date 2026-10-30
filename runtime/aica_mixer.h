/* AICA direct stereo mixer, GPL-2.0-or-later.
 * Register layout, Yamaha ADPCM constants and envelope timing reference:
 * flyinghead/flycast core/hw/aica/sgc_if.cpp (reicast contributors).
 * No game data. DSP effects, filter and LFO modulation remain unsupported.
 */
#ifndef PORT_AICA_MIXER_H
#define PORT_AICA_MIXER_H
#include <stdint.h>
#include <string.h>
#include <math.h>

typedef struct {
    uint32_t position, fraction, noise;
    int active, stage, previous, quant, loop_previous, loop_quant, loop_saved, looped;
    double envelope;
} PortAicaVoice;
typedef struct {
    PortAicaVoice voices[64];
    float attenuation[1024];
    double attack[64], decay[64];
    uint64_t frames, nonzero_frames, keyons, clipped;
    unsigned formats;
    int initialized;
} PortAicaMixer;

static int port_aica_clamp(int x,int lo,int hi) {return x<lo?lo:x>hi?hi:x;}
static void port_aica_init(PortAicaMixer *m) {
    static const double attack_ms[64]={-1,-1,8100,6900,6000,4800,4000,3400,3000,2400,2000,1700,1500,1200,1000,860,760,600,500,430,380,300,250,220,190,150,130,110,95,76,63,55,47,38,31,27,24,19,15,13,12,9.4,7.9,6.8,6,4.7,3.8,3.4,3,2.4,2,1.8,1.6,1.3,1.1,.93,.85,.65,.53,.44,.4,.35,0,0};
    static const double decay_ms[64]={-1,-1,118200,101300,88600,70900,59100,50700,44300,35500,29600,25300,22200,17700,14800,12700,11100,8900,7400,6300,5500,4400,3700,2800,2200,1800,1600,1400,1100,920,790,690,550,460,390,340,270,230,200,170,140,110,98,85,68,57,49,43,34,28,25,22,18,14,12,11,8.5,7.1,6.1,5.4,4.3,3.6,3.1};
    memset(m,0,sizeof *m);
    for(int i=0;i<1024;i++)m->attenuation[i]=i>=255?0:(float)pow(2.,-i/16.);
    for(int i=0;i<64;i++) {
        m->attack[i]=attack_ms[i]<0?0:attack_ms[i]==0?1:1-pow(1./640.,1./(attack_ms[i]*44.1));
        m->decay[i]=decay_ms[i]<0?0:1024./(decay_ms[i]*44.1);
    }
    for(int i=0;i<64;i++)m->voices[i].stage=3;
    m->initialized=1;
}
static unsigned port_aica_rate(uint32_t *r,unsigned rate) {
    unsigned krs=(r[5]>>10)&15;int oct=(r[6]>>11)&15;if(oct&8)oct-=16;
    int n=(int)rate*2;
    if(krs!=15)n+=(r[6]>>9)&1,n+=((int)krs+oct)>0?((int)krs+oct)*2:0;
    return (unsigned)port_aica_clamp(n,0,63);
}
static int port_aica_adpcm(unsigned nibble,int *previous,int *quant) {
    static const int scale[8]={230,230,230,230,307,409,512,614};
    int delta=(*quant*(2*(int)(nibble&7)+1))/8;
    delta=port_aica_clamp(delta,0,32767);
    *previous=port_aica_clamp(*previous+((nibble&8)?-delta:delta),-32768,32767);
    *quant=port_aica_clamp((*quant*scale[nibble&7])/256,127,24576);
    return *previous;
}
static uint8_t port_aica_byte(const uint8_t *ram,unsigned address) {return ram[address&0x1fffff];}
static int port_aica_decode(PortAicaVoice *v,uint32_t *r,const uint8_t *ram,unsigned position,int commit) {
    unsigned format=(r[0]>>7)&3,sa=((r[0]&127)<<16)|(r[1]&65535);
    if(r[0]&1024) {if(commit)v->noise=v->noise*1664525u+1013904223u;return (int16_t)(v->noise>>16);}
    if(format==0) {sa&=~1u;unsigned at=sa+position*2;return (int16_t)(port_aica_byte(ram,at)|(port_aica_byte(ram,at+1)<<8));}
    if(format==1)return (int8_t)port_aica_byte(ram,sa+position)*256;
    int previous=v->previous,quant=v->quant;
    if(position==(r[2]&65535)) {
        if(!v->loop_saved) {if(commit){v->loop_saved=1;v->loop_previous=previous;v->loop_quant=quant;}}
        else if(format==2) {previous=v->loop_previous;quant=v->loop_quant;}
    }
    unsigned nibble=(port_aica_byte(ram,sa+position/2)>>((position&1)*4))&15;
    int sample=port_aica_adpcm(nibble,&previous,&quant);
    if(commit){v->previous=previous;v->quant=quant;}
    return sample;
}
static void port_aica_key_execute(PortAicaMixer *m,uint32_t *regs,unsigned off) {
    if(!m->initialized)port_aica_init(m);
    if(off>=0x2000||(off&127)||!(regs[off/4]&0x8000))return;
    regs[off/4]&=~0x8000u;
    for(int i=0;i<64;i++) {
        uint32_t *r=regs+i*32;PortAicaVoice *v=&m->voices[i];
        if(r[0]&0x4000) {
            if(v->active&&v->stage!=3)continue;
            memset(v,0,sizeof *v);v->active=1;v->envelope=640;v->quant=127;v->noise=(unsigned)i+1;
            m->keyons++;m->formats|=1u<<((r[0]>>7)&3);
        } else if(v->active)v->stage=3;
    }
}
static unsigned port_aica_next(PortAicaVoice *v,uint32_t *r) {
    unsigned next=v->position+1,lea=r[3]&65535,lsa=r[2]&65535;
    if(((r[0]>>7)&3)==3)lea=(lea+3)&~3u;
    if((r[5]&0x4000)&&next>=lsa&&v->stage==0)v->stage=1;
    if(next>=lea) {
        if(lsa>lea){if(next>=lsa)v->active=0;}
        else {v->looped=1;if(r[0]&512)next=lsa;else v->active=0;}
    }
    return next;
}
static void port_aica_render(PortAicaMixer *m,uint32_t *regs,const uint8_t *ram,float *stereo,unsigned frames) {
    if(!m->initialized)port_aica_init(m);
    memset(stereo,0,frames*2*sizeof *stereo);
    if(!ram)return;
    for(int i=0;i<64;i++) {
        PortAicaVoice *v=&m->voices[i];if(!v->active)continue;
        uint32_t *r=regs+i*32;
        unsigned send=(r[9]>>8)&15,pan=r[9]&31,tl=(r[10]&64)?0:(r[10]>>8)&255;
        unsigned full=tl+(send?((15-send)*8):255),p=pan&15;
        unsigned side=full+(p==15?255:p*8);
        float left=m->attenuation[port_aica_clamp((pan&16)?full:side,0,1023)];
        float right=m->attenuation[port_aica_clamp((pan&16)?side:full,0,1023)];
        unsigned step=1024|(r[6]&1023),oct=(r[6]>>11)&15;
        step=oct&8?step>>(16-oct):step<<oct;
        unsigned ar=port_aica_rate(r,r[4]&31),d1=port_aica_rate(r,(r[4]>>6)&31),d2=port_aica_rate(r,(r[4]>>11)&31),rr=port_aica_rate(r,r[5]&31);
        for(unsigned f=0;f<frames&&v->active;f++) {
            if(v->stage==0) {v->envelope-=v->envelope*m->attack[ar];if(v->envelope<1){v->envelope=0;if(!(r[5]&0x4000))v->stage=1;}}
            else {v->envelope+=m->decay[v->stage==1?d1:v->stage==2?d2:rr];if(v->stage==1&&v->envelope>=((r[5]>>5)&31)*32)v->stage=2;if(v->envelope>=1023){v->active=0;break;}}
            /* Decoder state describes the sample BEFORE current position. */
            int a=port_aica_decode(v,r,ram,v->position,0);
            PortAicaVoice peek=*v;port_aica_decode(&peek,r,ram,v->position,1);
            unsigned next=port_aica_next(&peek,r);
            int b=peek.active?port_aica_decode(&peek,r,ram,next,0):a;
            float sample=(a+(b-a)*(v->fraction/1024.f))/32768.f;
            if(!(r[10]&64))sample*=m->attenuation[port_aica_clamp((int)(v->envelope/4),0,1023)];
            stereo[f*2]+=sample*left;stereo[f*2+1]+=sample*right;
            v->fraction+=step;
            while(v->fraction>=1024&&v->active) {
                port_aica_decode(v,r,ram,v->position,1);v->position=port_aica_next(v,r);v->fraction-=1024;
            }
        }
    }
    unsigned vol=regs[0x2800/4]&15;float gain=vol?(float)pow(2.,((int)vol-15)/2.):0;
    if(regs[0x2800/4]&256)gain*=.25f; /* 18-bit DAC range */
    for(unsigned f=0;f<frames;f++) {
        float a=stereo[2*f]*gain,b=stereo[2*f+1]*gain;
        if(regs[0x2800/4]&0x8000)a=b=(a+b)*.5f;
        if(a||b)m->nonzero_frames++;
        if(fabsf(a)>1||fabsf(b)>1)m->clipped++;
        stereo[2*f]=fmaxf(-1,fminf(1,a));stereo[2*f+1]=fmaxf(-1,fminf(1,b));
    }
    m->frames+=frames;
}
#endif
