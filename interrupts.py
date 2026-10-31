"""Expose the SH-4 event number for the interrupt priority actually delivered."""
def adapt_cpu(source):
    source=source.lstrip('\ufeff')
    # An unrouted VBlank is pending, not an asserted CPU interrupt. Delivering
    # it at an invented priority enters unregistered vectors during startup.
    start=source.index('static int vblank_irl_level(void) {')
    end=source.index('\n}',start)+2
    routing=source[start:end]
    routing=routing.replace('    if (!pend)\n        return 0;\n','')
    tail=routing.index('    if (!(pend & VBL_IN))')
    routing=routing[:tail]+'    return 0;\n}'
    routing=routing.replace('    const uint32_t VBL_IN = 1u << 3;\n','')
    # Holly IML6/4/2 drive encoded IRL9/11/13, with CPU priorities 6/4/2.
    # Encoded line numbers must not be compared directly with SR.IMASK.
    routing=routing.replace('return 13;','return 6;').replace('return 11;','return 4;').replace('return 9;','return 2;')
    source=source[:start]+routing+source[end:]
    anchor='    g_irq_handler(cpu);'
    if source.count(anchor)!=1:raise ValueError('Pinned IRQ delivery changed')
    source=source.replace(anchor,'    port_intevt = 0x200u + (15u-(unsigned)level)*0x20u;\n'+anchor)
    source=source.replace('case 0xFF000010: return cpu->mmucr;', 'case 0xFF000028: return port_intevt;\n        case 0xFF000010: return cpu->mmucr;')
    return '#include <stdint.h>\nstatic uint32_t port_intevt;\nuint32_t port_irq_event_code(void){return port_intevt;}\n'+source
