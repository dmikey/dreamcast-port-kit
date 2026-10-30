#!/usr/bin/env python3
"""Execute translated SH-4 delay-slot cases as native C, including alternate entries."""
from pathlib import Path
import importlib.util
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
import os
CORE = Path(os.environ.get('DC_PORT_TEST_TOOLCHAIN', ROOT / '.local/dcrecomp')).resolve()
module = None
if (CORE / 'tools/static_recompile.py').exists():
    spec = importlib.util.spec_from_file_location('recompiler', CORE / 'tools/static_recompile.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
BASE = 0x8c010000


@unittest.skipIf(module is None, 'Bootstrap the pinned toolchain or set DC_PORT_TEST_TOOLCHAIN')
class DelaySlotTests(unittest.TestCase):
    def execute(self, opcodes, checks, helpers='', entry_hint=True):
        raw = struct.pack('<' + 'H' * len(opcodes), *opcodes)
        compiler = module.SH4Recompiler(raw, BASE)
        compiler.entry_hints = {BASE + 2} if entry_hint else set()
        compiler.mid_entries = {BASE: [BASE + 2]}
        info = {'end': BASE + len(raw)}
        compiler.functions = {BASE: info}
        translated = compiler.recompile_function(BASE, info)
        source = ('#include "recompiler/sh4_cpu.h"\n#include <assert.h>\n'
                  'static int calls; static unsigned target;\n'
                  'void sh4_call_indirect(SH4CPU *cpu) { calls++; target=cpu->pc; }\n'
                  + helpers + '\n' + translated + '\nint main(void) { SH4CPU cpu={0};\n'
                  + checks + '\nreturn 0;}\n')
        with tempfile.TemporaryDirectory(prefix='ct-delay-') as temp:
            path = Path(temp)
            (path / 'case.c').write_text(source)
            subprocess.run(['clang', '-std=c11', '-I', str(CORE / 'include'), str(path / 'case.c'),
                            '-o', str(path / 'case')], check=True, capture_output=True)
            subprocess.run([str(path / 'case')], check=True)

    def test_indirect_call_not_dropped_and_delay_runs_once(self):
        self.execute([0x420b, 0x7101, 0x7102, 0x000b, 0x0009], '''
cpu.r[2]=0x1234; func_8C010000(&cpu);
assert(calls==1 && target==0x1234 && cpu.r[1]==3 && cpu.pr==0x8c010004);
cpu.r[1]=0; func_8C010002(&cpu); assert(calls==1 && cpu.r[1]==3);
''')

    def test_indirect_call_latches_target_before_delay(self):
        self.execute([0x420b, 0x7201, 0x0009, 0x000b, 0x0009], '''
cpu.r[2]=0x1234; func_8C010000(&cpu);
assert(calls==1 && target==0x1234 && cpu.r[2]==0x1235);
''')

    def test_direct_call_not_dropped(self):
        self.execute([0xb00e, 0x7101, 0x7102, 0x000b, 0x0009], '''
func_8C010000(&cpu); assert(calls==1 && cpu.r[1]==3 && cpu.pr==0x8c010004);
''', 'void func_8C010020(SH4CPU *cpu) { calls++; assert(cpu->r[1]==1); }')

    def test_conditional_branch_uses_t_before_delay(self):
        # BT/S +4; CMP/EQ #0,R0 in its slot sets T, but must not change branch decision.
        self.execute([0x8d02, 0x8800, 0x7101, 0x0009, 0x000b, 0x0009], '''
cpu.sr=0; func_8C010000(&cpu); assert(cpu.r[1]==1);
cpu.r[1]=0; cpu.sr=SR_T; func_8C010000(&cpu); assert(cpu.r[1]==0);
''')

    def test_internal_loop_into_delay_slot_does_not_repeat_prior_branch(self):
        self.execute([0xa004,0x7101,0x4210,0x8bfc,0x000b,0x0009,0x000b,0x0009], '''
cpu.r[2]=2;func_8C010002(&cpu);assert(cpu.r[1]==2 && cpu.r[2]==0);
''',entry_hint=False)

    def boundary_case(self, words, checks, helpers):
        compiler=module.SH4Recompiler(struct.pack('<'+'H'*len(words),*words),BASE)
        compiler.entry_hints=set();compiler.mid_entries={}
        code=compiler.recompile_function(BASE,{'end':BASE+2},next_func_addr=BASE+2)
        source='#include "recompiler/sh4_cpu.h"\n#include <assert.h>\n'+helpers+'\n'+code+'\nint main(void){SH4CPU cpu={0};'+checks+'return 0;}\n'
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);(path/'test.c').write_text(source)
            subprocess.run(['clang','-std=c11','-I',str(CORE/'include'),str(path/'test.c'),'-o',str(path/'test')],check=True,capture_output=True)
            subprocess.run([str(path/'test')],check=True)

    def test_bra_executes_delay_across_function_boundary(self):
        self.boundary_case([0xa002,0x7101,0x0009,0x0009,0x000b,0x0009],
            'func_8C010000(&cpu);assert(cpu.r[1]==1 && cpu.r[2]==1 && cpu.r[3]==0);',
            'void func_8C010008(SH4CPU *cpu){cpu->r[2]++;}\nvoid func_8C010004(SH4CPU *cpu){cpu->r[3]++;}')

    def test_bsr_continues_after_cross_boundary_delay_once(self):
        self.boundary_case([0xb002,0x7101,0x0009,0x0009,0x000b,0x0009],
            'func_8C010000(&cpu);assert(cpu.r[1]==1 && cpu.r[2]==1 && cpu.r[3]==1);',
            'void func_8C010008(SH4CPU *cpu){assert(cpu->r[1]==1 && cpu->pr==0x8c010004);cpu->r[2]++;}\nvoid func_8C010004(SH4CPU *cpu){assert(cpu->r[2]==1);cpu->r[3]++;}')

    def test_conditional_boundary_delay_uses_original_t(self):
        self.boundary_case([0x8d02,0x8800,0x0009,0x0009,0x000b,0x0009],
            'func_8C010000(&cpu);assert(cpu.r[2]==0 && cpu.r[3]==1);cpu.sr=SR_T;func_8C010000(&cpu);assert(cpu.r[2]==1 && cpu.r[3]==1);',
            'void func_8C010008(SH4CPU *cpu){cpu->r[2]++;}\nvoid func_8C010004(SH4CPU *cpu){cpu->r[3]++;}')

    def test_untaken_conditional_at_fragment_end_falls_through(self):
        self.boundary_case([0x8902,0x0009,0x0009,0x0009,0x000b,0x0009],
            'func_8C010000(&cpu);assert(cpu.r[2]==0 && cpu.r[3]==1);cpu.sr=SR_T;func_8C010000(&cpu);assert(cpu.r[2]==1 && cpu.r[3]==1);',
            'void func_8C010008(SH4CPU *cpu){cpu->r[2]++;}\nvoid func_8C010002(SH4CPU *cpu){cpu->r[3]++;}')

    def test_inline_branch_table_entries_are_discovered_and_execute(self):
        self.inline_table_case(False)
        self.inline_table_case(True)

    def inline_table_case(self,register9):
        words=[0xc901,0x4008,0x0023,0x0009,0xa002,0x0009,0xa003,0x0009,0xe101,0x000b,0x0009,0xe102,0x000b,0x0009]
        if register9:words[:3]=[0x0009,0x4908,0x0923]
        compiler=module.SH4Recompiler(struct.pack('<14H',*words),BASE)
        compiler.find_functions()
        self.assertTrue({BASE+8,BASE+12}<=compiler.mid_entry_addrs)
        code=compiler.recompile_function(BASE,compiler.functions[BASE])
        source='#include "recompiler/sh4_cpu.h"\n#include <assert.h>\nvoid sh4_jump_indirect(SH4CPU *);void func_8C010008(SH4CPU *);void func_8C01000C(SH4CPU *);\n'+code+            '\nvoid sh4_jump_indirect(SH4CPU *c) {if(c->pc==0x8c010008)func_8C010008(c);else if(c->pc==0x8c01000c)func_8C01000C(c);else assert(0);}' +            '\nint main(void){SH4CPU c={0};func_8C010000(&c);assert(c.r[1]==1);c.r[0]=1;func_8C010000(&c);assert(c.r[1]==2);return 0;}\n'
        if register9:source=source.replace('c.r[0]=1','c.r[9]=1')
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);(path/'test.c').write_text(source)
            subprocess.run(['clang','-std=c11','-I',str(CORE/'include'),str(path/'test.c'),'-o',str(path/'test')],check=True,capture_output=True)
            subprocess.run([str(path/'test')],check=True)


if __name__ == '__main__':
    unittest.main()
