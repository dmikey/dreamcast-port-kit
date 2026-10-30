/* Dreamcast port-kit native bring-up harness. GPL-2.0 with dcrecomp runtime. */
#include "project.h"
#include "vmu.h"
#include "recompiler/sh4_cpu.h"
#include "hal/dc_hardware.h"
#include "hal/dc_bios.h"
#include "hal/pvr2.h"
#include "platform/platform.h"
#include "game/game_functions.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static SH4CPU cpu;
#ifdef __EMSCRIPTEN__
#include <emscripten.h>
EMSCRIPTEN_KEEPALIVE void port_button(unsigned bit,int pressed) {
    MapleController *c=dc_maple_get_controller(sh4_get_hardware(),0);
    if(c) {if(pressed)c->buttons &= ~bit;else c->buttons |= bit;}
}
EMSCRIPTEN_KEEPALIVE void port_axes(int left,int right,int x,int y) {
    MapleController *c=dc_maple_get_controller(sh4_get_hardware(),0);
    if(c) {c->ltrig=left;c->rtrig=right;c->joyx=x;c->joyy=y;}
}
EMSCRIPTEN_KEEPALIVE unsigned port_input(unsigned bits,int left,int right,int x,int y) {
    MapleController *c=dc_maple_get_controller(sh4_get_hardware(),0);
    if(c){c->buttons=(~bits)&0xffff;c->ltrig=left;c->rtrig=right;c->joyx=x;c->joyy=y;}
    return c?((~c->buttons)&0xffff):0;
}
#endif

void port_runtime_trace(void) {
    fprintf(stderr,"[CPU] pc=%08X pr=%08X sr=%08X sp=%08X\n",cpu.pc,cpu.pr,cpu.sr,cpu.r[15]);
    for(int i=0;i<16;i++) fprintf(stderr,"r%d=%08X%c",i,cpu.r[i],i==15?'\n':' ');
}

uint32_t port_irq_event_code(void);
static void irq(SH4CPU *c) {
#if PORT_IRQ_VECTOR_TABLE
    uint32_t event=port_irq_event_code();
    if(event<0x200||event>0xfe0||(event&31)){fprintf(stderr,"[IRQ] Invalid event %08X\n",event);abort();}
    uint32_t target=sh4_read32(c,c->vbr+PORT_IRQ_VECTOR_TABLE_OFFSET+((event-0x200)>>3));
    if(!target){fprintf(stderr,"[IRQ] No registered callback for event %08X\n",event);abort();}
    uint32_t old_ssr=c->ssr,old_spc=c->spc,old_sgr=c->sgr;
    c->ssr=c->sr;c->spc=c->pc;c->sgr=c->r[15];
    sh4_write32(c,PORT_IRQ_EVENT_ADDRESS,event);c->r[4]=event;
    c->sr=(c->sr&~SR_BL)|SR_IMASK;c->pc=target;
    sh4_call_indirect(c);
    c->ssr=old_ssr;c->spc=old_spc;c->sgr=old_sgr;
#else
    const int pushes[] = PORT_IRQ_PUSHES;
    for(unsigned i=0;i<sizeof pushes/sizeof pushes[0];i++) {
        c->r[15]-=4; sh4_write32(c,c->r[15],c->r[pushes[i]]);
    }
    PORT_IRQ_ENTRY(c);
#endif
}

int main(void) {
    setvbuf(stdout,NULL,_IONBF,0);
    sh4_init_ex(&cpu,PORT_RAM_BYTES);
    DCHardware *hw=dc_hw_init();
    if(!hw) return 1;
    sh4_set_hardware(hw); sh4_set_cpu_ref(&cpu);
    dc_pvr_init(hw); dc_maple_init(hw); dc_aica_init(hw); dc_gdrom_init(hw);
    FILE *f=fopen(PORT_EXECUTABLE,"rb");
    if(!f) {perror(PORT_EXECUTABLE);return 2;}
    fseek(f,0,SEEK_END);long size=ftell(f);rewind(f);
    unsigned offset=PORT_LOAD_ADDRESS&cpu.ram_mask;
    if(size<0 || offset+(unsigned)size>cpu.ram_size) return 3;
    size_t copied=fread(cpu.ram+offset,1,size,f);fclose(f);
    if(copied!=(size_t)size) return 4;
    printf("[PORT] exact executable loaded: %zu bytes\n",copied);
    if(PORT_SEGA_PATTERN) for(unsigned at=0xc000;at<0xf400;at+=4) {
        unsigned sega=0x41474553;memcpy(cpu.ram+at,&sega,4);
    }
    cpu.pc=PORT_RUNTIME_ENTRY;cpu.r[15]=PORT_STACK_POINTER;cpu.vbr=PORT_VECTOR_BASE;
    cpu.r[2]=0x8c000000;cpu.sr=0x700000f0;cpu.fpscr=0x00040001;cpu.pr=0;
    sh4_bios_install_vectors(&cpu);
    const char *tracks[]=PORT_TRACK_PATHS;
    const unsigned lbas[]=PORT_TRACK_LBAS;
    for(unsigned i=0;i<sizeof lbas/sizeof lbas[0];i++) sh4_bios_set_gdrom_track(tracks[i],lbas[i]);
    port_vmu_init();
    sh4_set_irq_handler(irq);
    if(platform_init(640,480,PORT_TITLE)!=0) return 5;
    pvr2_ta_init();
    if(pvr2_render_init(640,480)!=0) return 6;
    printf("[PORT] entering title code at %08X; gameplay unverified\n",cpu.pc);
    PORT_ENTRY(&cpu);
    printf("[PORT] entry returned; gameplay unverified\n");
    pvr2_render_destroy();pvr2_ta_destroy();platform_shutdown();dc_hw_destroy(hw);sh4_destroy(&cpu);
    return 0;
}
