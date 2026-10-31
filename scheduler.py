"""Browser hardware-clock diagnostics, separate from rendered-frame counts."""
def clock_poll():
    return '''          {
              static double epoch,max_late;static unsigned raised,late,discarded;
              double clock_now=emscripten_get_now(),lateness=port_vblank_due?clock_now-port_vblank_due:0;
              if(port_vblank_ready(clock_now)){
                  raised++;if(lateness>1)late++;if(lateness>max_late)max_late=lateness;
                  if(lateness>1000.0/30.0)discarded++;
                  dc_pvr_wait_vblank(g_hardware);
              }
              if(!epoch)epoch=clock_now;
              if(clock_now-epoch>=5000){
                  printf("[CLOCK] vblank_hz=%.2f raised=%u late1ms=%u max_late_ms=%.2f debt_resets=%u\\n",raised*1000.0/(clock_now-epoch),raised,late,max_late,discarded);
                  epoch=clock_now;raised=late=discarded=0;max_late=0;
              }
          }'''

def idle_state(cpu):
    """Observe writes and the physical address only at an existing RAM IRQ poll."""
    marker='#include "recompiler/sh4_cpu.h"'
    if cpu.count(marker)!=1:raise ValueError('Expected CPU include')
    cpu=cpu.replace(marker,marker+'\n#include "idle_wait.h"\nstatic uint64_t port_write_stamp;\nstatic uint32_t port_polled_addr,port_polled_seq;\nstatic uint32_t g_read_seq;')
    for width,ctype in ((8,'uint8_t'),(16,'uint16_t'),(32,'uint32_t')):
        marker=f'void sh4_write{width}(SH4CPU *cpu, uint32_t addr, {ctype} val) {{'
        if cpu.count(marker)!=1:raise ValueError('Expected one writer: '+marker)
        cpu=cpu.replace(marker,marker+'\n    if(!g_in_irq)++port_write_stamp;')
    marker='if ((g_read_seq & 0xFF) == 0) sh4_poll_irq(cpu);'
    if cpu.count(marker)!=1:raise ValueError('Expected original 32-bit IRQ poll')
    return cpu.replace(marker,'if ((g_read_seq & 0xFF) == 0) {port_polled_addr=phys;port_polled_seq=g_read_seq;sh4_poll_irq(cpu);}')

def poll_entry():
    return '''
    static double yielded,waited,reported,last_poll,max_run,max_yield,max_idle;static unsigned yields,idle_yields,idle_tick;
    static PortIdleDetector idle;
    double now=emscripten_get_now();int can_idle=0;
    if(last_poll && now-last_poll>max_run)max_run=now-last_poll;
    if((++idle_tick&31)==0 && port_polled_seq==g_read_seq)can_idle=port_idle_probe(&idle,cpu,port_write_stamp,port_polled_addr,port_polled_seq,now,port_vblank_due,g_in_irq);
    if(can_idle || now-yielded>8){
        double before=now;
        if(can_idle){port_browser_idle_yield();idle_yields++;}else port_browser_yield();
        yielded=emscripten_get_now();now=yielded;waited+=yielded-before;yields++;
        double delay=yielded-before;
        if(can_idle){if(delay>max_idle)max_idle=delay;}else if(delay>max_yield)max_yield=delay;
        if(yielded-reported>5000){
            printf("[PERF] %u CPU yields (%u idle), %.0fms waiting / %.0fms elapsed\\n",yields,idle_yields,waited,yielded-reported);
            printf("[EXEC] poll_gap_max_ms=%.2f task_wait_max_ms=%.2f idle_wait_max_ms=%.2f\\n",max_run,max_yield,max_idle);
            reported=yielded;waited=0;yields=idle_yields=0;
            max_run=max_yield=max_idle=0;
        }
    }
    last_poll=now;
'''
