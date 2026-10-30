"""Add the portable A1 VMU device to the pinned Maple DMA implementation."""
def adapt(source):
    source=source.lstrip('\ufeff')
    start=source.index('void dc_maple_dma(');end=source.index('MapleController* dc_maple_get_controller',start)
    dma=source[start:end]
    anchor='if (!has_device || (reci & 0x1F) != 0) {'
    if dma.count(anchor)!=1:raise ValueError('Pinned Maple device dispatch changed')
    dma=dma.replace('uint32_t addr = mdstar & 0x1FFFFFFF;', 'uint32_t addr = mdstar & 0x1FFFFFFF;\n    uint32_t ram_mask=sh4_get_ram_mask();')
    dma=dma.replace('0x01FFFFFF','ram_mask')
    # Control patterns occupy one word, unlike START descriptors.
    dma=dma.replace('addr += 8 + plen * 4;', 'addr += maple_op==0 ? 8 + plen * 4 : 4;')
    # A bogus response address must never overwrite RAM zero / BIOS vectors.
    dma=dma.replace('if (maple_op == 0) {', 'if (maple_op == 0) {\n            if(header_2<0x0c000000u||header_2>=0x10000000u||(header_2&ram_mask)+1024>ram_mask+1)return;')
    dma=dma.replace('uint32_t src_addr = reci;', 'uint32_t src_addr = reci;\n            if(port==0 && (reci&0x3f)==0x20 && port_vmu_connected())src_addr|=1;')
    dma=dma.replace(anchor,'''if(has_device && port==0 && (reci&0x3f)==1) {
                unsigned words=frame_header>>24;
                if(words>plen-1)resp[0]=0xfc | (dst_addr<<8) | (reci<<16);
                else port_vmu_dma(frame_header,p_data+1,words,resp);
            } else '''+anchor)
    # Reply recipient is the request sender; reply sender is the selected device.
    dma=dma.replace('(src_addr << 8) | (dst_addr << 16)','(dst_addr << 8) | (src_addr << 16)')
    return '#include "vmu.h"\n'+source[:start]+dma+source[end:]
