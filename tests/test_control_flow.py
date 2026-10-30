"""Execute a long cross-boundary loop while preserving nested call returns."""
from pathlib import Path
import tempfile,subprocess,unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import control_flow

class ControlFlowTests(unittest.TestCase):
    def test_cross_function_loop_has_bounded_stack_and_nested_calls_return(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'src').mkdir();(root/'include/game').mkdir(parents=True)
            (root/'include/game/game_functions.h').write_text('''
#ifndef GAME_FUNCTIONS_H
#define GAME_FUNCTIONS_H
#include <stdint.h>
typedef struct {uint32_t r[16],pc;} SH4CPU;
void func_8C010000(SH4CPU *cpu);
void func_8C010010(SH4CPU *cpu);
void func_8C010020(SH4CPU *cpu);
void sh4_call_indirect(SH4CPU *cpu);
#endif
''')
            (root/'src/game_code_000.c').write_text('''
#include "game/game_functions.h"
void func_8C010000(SH4CPU *cpu) {
    func_8C010020(cpu);
    cpu->r[0]++;
    if(cpu->r[0]<100000) { func_8C010010(cpu); return; }
}
void func_8C010010(SH4CPU *cpu) {func_8C010000(cpu); return;}
void func_8C010020(SH4CPU *cpu) {cpu->r[1]++;}
''')
            (root/'src/dispatch_table.c').write_text('''
#include "game/game_functions.h"
#include <assert.h>
typedef struct {uint32_t addr;void (*func)(SH4CPU *);} FuncEntry;
void sh4_call_indirect(SH4CPU *cpu) {assert(!"unexpected dispatch");}
void sh4_jump_indirect(SH4CPU *cpu) {
    sh4_call_indirect(cpu);
}
''')
            control_flow.lower(root,[])
            (root/'test.c').write_text('''
#include "game/game_functions.h"
#include <assert.h>
int main(void) {SH4CPU cpu={0};func_8C010000(&cpu);assert(cpu.r[0]==100000);assert(cpu.r[1]==100000);assert(sh4_tail_target==0);return 0;}
''')
            subprocess.run(['clang','-std=c11','-O0','-I',str(root/'include'),*map(str,(root/'src').glob('*.c')),str(root/'test.c'),'-o',str(root/'test')],check=True,capture_output=True)
            subprocess.run([str(root/'test')],check=True)
