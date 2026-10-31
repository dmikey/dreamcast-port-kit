/* Conservative, bounded cooperation for RAM-poll loops. No guest state or
 * memory access is skipped; the caller only yields host time between polls. */
#include <stdint.h>
#include <string.h>
typedef struct {
    SH4CPU cpu;uint32_t address;int valid;
} PortIdleState;
typedef struct {
    PortIdleState states[8];unsigned next;
    uint64_t writes;double quiet_since;uint32_t sequence;int initialized;
} PortIdleDetector;
static int port_idle_probe(PortIdleDetector *s,const SH4CPU *cpu,uint64_t writes,
                           uint32_t address,uint32_t sequence,double now,
                           double deadline,int in_irq){
    if(in_irq)return 0;
    if(!s->initialized || writes!=s->writes ||
       address<0x0c000000u || address-0x0c000000u>=cpu->ram_size){
        memset(s,0,sizeof *s);s->initialized=1;s->writes=writes;s->quiet_since=now;s->sequence=sequence;
        return 0;
    }
    if(sequence==s->sequence)return 0;s->sequence=sequence;
    int repeated=0;
    for(unsigned i=0;i<8;i++)if(s->states[i].valid && s->states[i].address==address &&
        !memcmp(&s->states[i].cpu,cpu,sizeof *cpu)){repeated=1;break;}
    PortIdleState *out=&s->states[s->next++&7];out->cpu=*cpu;out->address=address;out->valid=1;
    return repeated && now-s->quiet_since>=2.0 && deadline-now>2.0;
}
