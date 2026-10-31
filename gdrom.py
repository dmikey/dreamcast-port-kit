"""Density-aware BIOS TOC responses for imported data tracks."""

def adapt(source):
    begin=source.index('        /* A TOC the game can parse:')
    end=source.index('    default:',begin)
    source=source[:begin]+'''        /* GD-ROM has separate low/high-density TOCs. Entries 99 and 100
         * contain track numbers, while entry 101 contains the lead-out FAD.
         * Imported data tracks omit audio; high-density data starts at track 3.
         */
        if (param) {
            unsigned area=sh4_read32(cpu,param);
            uint32_t out=sh4_read32(cpu,param+4);
            if (out) {
                unsigned first=0,last=0;uint32_t leadout=0;
                for (unsigned i=0;i<102;i++) sh4_write32(cpu,out+i*4,0xffffffffu);
                for (int i=0;i<g_track_count;i++) {
                    unsigned high=g_tracks[i].start_lba>=45000;
                    if (high!=(area!=0)) continue;
                    unsigned number=high?3:1;
                    if (last>=number) number=last+1;
                    if (number>99) return -1;
                    if (!first) first=number;
                    last=number;
                    sh4_write32(cpu,out+(number-1)*4,0x41000000u|(g_tracks[i].start_lba+150));
                    leadout=g_tracks[i].start_lba+g_tracks[i].sectors+150;
                }
                if (!first) return -1;
                sh4_write32(cpu,out+99*4,0x41000000u|(first<<16));
                sh4_write32(cpu,out+100*4,0x41000000u|(last<<16));
                sh4_write32(cpu,out+101*4,0x41000000u|leadout);
            }
        }
        return 0;
'''+source[end:]
    source=source.replace('static uint32_t g_gdc_next_id = 1;',
        'static uint32_t g_gdc_transfer_bytes;\nstatic uint32_t g_gdc_next_id = 1;')
    source=source.replace('        int r = gdc_read_sectors(cpu, lba, count, dest);',
        '        int r = gdc_read_sectors(cpu, lba, count, dest);\n        if (!r) g_gdc_transfer_bytes=count*GDC_SECTOR_SIZE;')
    source=source.replace('        gdc_exec(cpu, cpu->r[4], cpu->r[5]);',
        '        g_gdc_transfer_bytes=0;\n        gdc_exec(cpu, cpu->r[4], cpu->r[5]);')
    anchor='        return 2;   /* COMPLETED */'
    if source.count(anchor)!=1:raise ValueError('Pinned GD-ROM completion changed')
    source=source.replace(anchor,
        '        if (cpu->r[5]) sh4_write32(cpu,cpu->r[5]+8,g_gdc_transfer_bytes);\n'+anchor)
    return source
