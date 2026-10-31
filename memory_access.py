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

def adapt_reads(cpu):
    marker='uint32_t sh4_read32(SH4CPU *cpu, uint32_t addr) {'
    end='\nfloat sh4_read_float(SH4CPU *cpu, uint32_t addr) {'
    if cpu.count(marker)!=1 or cpu.count(end)!=1:raise ValueError('Expected one 32-bit read implementation')
    cpu=cpu.replace(marker,'static __attribute__((noinline)) uint32_t port_read32_slow(SH4CPU *cpu, uint32_t addr) {')
    wrapper='''
/* Small enough to inline at translated loads. Every poll/heartbeat access
 * still enters the complete original read path, including IRQ side effects.
 * MMU translations, devices and control registers always use that path. */
uint32_t sh4_read32(SH4CPU *cpu,uint32_t addr) {
    uint32_t phys=addr&0x1fffffffu;
    if(cpu && cpu==g_cpu_ref && addr<0xe0000000u &&
       ((addr>=0x80000000u && addr<0xc0000000u) || !(cpu->mmucr&1)) &&
       phys>=DC_RAM_BASE && phys-DC_RAM_BASE<cpu->ram_size &&
       ((g_read_seq+1)&0xffu)){
        ++g_read_seq;
        return *(uint32_t*)(cpu->ram+(phys&cpu->ram_mask));
    }
    return port_read32_slow(cpu,addr);
}
'''
    return cpu.replace(end,wrapper+end)
