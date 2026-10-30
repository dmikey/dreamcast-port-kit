"""Guarded direct RAM translation; all MMU/device cases retain the original path."""
def adapt(cpu):
    marker='static uint32_t translate_addr_cpu(SH4CPU *cpu, uint32_t addr) {'
    if cpu.count(marker)!=1:raise ValueError('Expected exactly one address translator')
    return cpu.replace(marker,marker+'''
    /* RAM mirrors are direct only in P1/P2 or with translation disabled.
     * Never shortcut P0/P3 with MMU enabled, nor P4/UTLB/device accesses. */
    uint32_t direct_phys=addr & 0x1fffffffu;
    if(cpu && addr<0xe0000000u &&
       ((addr>=0x80000000u && addr<0xc0000000u) || !(cpu->mmucr&1)) &&
       direct_phys>=DC_RAM_BASE && direct_phys-DC_RAM_BASE<cpu->ram_size)
        return direct_phys;
''')
