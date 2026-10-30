"""Expose the SH-4 event number for the interrupt priority actually delivered."""
def adapt_cpu(source):
    source=source.lstrip('\ufeff')
    anchor='    g_irq_handler(cpu);'
    if source.count(anchor)!=1:raise ValueError('Pinned IRQ delivery changed')
    source=source.replace(anchor,'    port_intevt = 0x200u + (15u-(unsigned)level)*0x20u;\n'+anchor)
    source=source.replace('case 0xFF000010: return cpu->mmucr;', 'case 0xFF000028: return port_intevt;\n        case 0xFF000010: return cpu->mmucr;')
    return '#include <stdint.h>\nstatic uint32_t port_intevt;\nuint32_t port_irq_event_code(void){return port_intevt;}\n'+source
