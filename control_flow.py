"""Lower translated inter-function jumps to a bounded-stack trampoline.

Normal SH-4 subroutine calls retain nested C calls. Only emitted terminal jumps
and fall-throughs enter the trampoline, preserving call/return continuations.
"""
from pathlib import Path
import re

def lower(generated,aliases):
    directory=Path(generated)/'src';names=[]
    for p in directory.glob('game_code_*.c'):
        text=p.read_text()
        entries=re.findall(r'^void (func_[0-9A-F]{8})\(SH4CPU \*cpu\)',text,re.M)
        names+=entries
        text=re.sub(r'^void (func_[0-9A-F]{8})\(SH4CPU \*cpu\)',r'void raw_\1(SH4CPU *cpu)',text,flags=re.M)
        text=re.sub(r'func_([0-9A-F]{8})\(cpu\); return;',r'sh4_tail_target = 0x\1u; return;',text)
        text=re.sub(r'func_([0-9A-F]{8})\(cpu\); /\* fall-through \*/',r'sh4_tail_target = 0x\1u; return; /* fall-through */',text)
        text+='\n'+''.join(f'void {name}(SH4CPU *cpu) {{ uint32_t before=cpu->r[8];raw_{name}(cpu); sh4_drain_tailcalls(cpu);sh4_trace_pointer(cpu,0x{name[5:]}u,before); }}\n' for name in entries)
        p.write_text(text)
    header=Path(generated)/'include/game/game_functions.h'
    text=header.read_text();at=text.rfind('#endif')
    text=text[:at]+'extern uint32_t sh4_tail_target;\nvoid sh4_drain_tailcalls(SH4CPU *cpu);\nvoid sh4_trace_pointer(SH4CPU *cpu,uint32_t address,uint32_t before);\n'+''.join(f'void raw_{name}(SH4CPU *cpu);\n' for name in names)+text[at:]
    header.write_text(text)
    path=directory/'dispatch_table.c';text=path.read_text()
    text=text.replace('void sh4_jump_indirect(SH4CPU *cpu) {\n    sh4_call_indirect(cpu);','void sh4_jump_indirect(SH4CPU *cpu) {\n    sh4_tail_target = cpu->pc;')
    text+='\n#include <stdio.h>\nvoid sh4_trace_pointer(SH4CPU *cpu,uint32_t address,uint32_t before) {\n#ifdef DCRECOMP_ABI_CHECK\nstatic int logs; if(before>=0x0c010000 && before<0x8c180000 && cpu->r[8]<0x10000 && logs++<60)fprintf(stderr,\"[REGISTER] %08X r8 %08X -> %08X sp=%08X\\n\",address,before,cpu->r[8],cpu->r[15]);\n#endif\n}\nuint32_t sh4_tail_target;\nstatic const FuncEntry raw_table[]={\n'
    text+=''.join(f'{{0x{name[5:]}u,raw_{name}}},\n' for name in sorted(names))+'};\n'
    text+='''void sh4_drain_tailcalls(SH4CPU *cpu) {
while(sh4_tail_target) {
    uint32_t address=sh4_tail_target;sh4_tail_target=0;
    uint32_t phys=address&0x1fffffff,lookup=phys|0x80000000;
'''
    for a in aliases:
        start,end,delta=(int(a[k],0) for k in ('start','end','delta'))
        text+=f'    if(phys>=0x{start:X}u && phys<0x{end:X}u) lookup=(phys+0x{delta:X}u)|0x80000000u;\n'
    text+='''    unsigned lo=0,hi=sizeof raw_table/sizeof raw_table[0];
    while(lo<hi) {unsigned m=lo+(hi-lo)/2;if(raw_table[m].addr<lookup)lo=m+1;else hi=m;}
    if(lo<sizeof raw_table/sizeof raw_table[0] && raw_table[lo].addr==lookup)raw_table[lo].func(cpu);
    else {cpu->pc=address;sh4_call_indirect(cpu);}
}
}
'''
    path.write_text(text)
