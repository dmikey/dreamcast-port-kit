"""Profiled interrupt callback dispatch without borrowing another game's prologue."""
import os,subprocess,tempfile,unittest
from pathlib import Path
from interrupts import adapt_cpu
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(os.environ.get('DC_PORT_TEST_TOOLCHAIN'),'Set DC_PORT_TEST_TOOLCHAIN')
class InterruptVectorTests(unittest.TestCase):
 def test_delivered_priority_has_correct_intevt(self):
  core=Path(os.environ['DC_PORT_TEST_TOOLCHAIN']);source=adapt_cpu((core/'src/recompiler/sh4_cpu.c').read_text())
  self.assertIn('case 0xFF000028: return port_intevt;',source)
  # Execute the actual injected expression for all priorities used by Holly.
  statement=next(line.strip() for line in source.splitlines() if 'port_intevt = 0x200u' in line)
  code='#include <assert.h>\nunsigned port_intevt;unsigned event(int level){'+statement+'return port_intevt;}\nint main(void){assert(event(6)==0x320);assert(event(4)==0x360);assert(event(2)==0x3a0);}'
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'test.c').write_text(code);subprocess.run(['clang',str(p/'test.c'),'-o',str(p/'test')],check=True,capture_output=True);subprocess.run([str(p/'test')],check=True)
 def test_callback_uses_profile_table_and_preserves_exception_state(self):
  core=Path(os.environ['DC_PORT_TEST_TOOLCHAIN']);runner=(ROOT/'runtime/runner.c').read_text();body=runner[runner.index('static void irq('):runner.index('\nint main(void)')]
  code=r'''
#include "recompiler/sh4_cpu.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#define PORT_IRQ_VECTOR_TABLE 1
#define PORT_IRQ_VECTOR_TABLE_OFFSET 0x200
#define PORT_IRQ_EVENT_ADDRESS 0x8c223344
static uint32_t event,stored;
uint32_t port_irq_event_code(void){return event;}
uint32_t sh4_read32(SH4CPU *c,uint32_t at){assert(at==c->vbr+0x200+((event-0x200)>>3));return 0x8c123456;}
void sh4_write32(SH4CPU *c,uint32_t at,uint32_t value){(void)c;assert(at==PORT_IRQ_EVENT_ADDRESS);stored=value;}
void sh4_call_indirect(SH4CPU *c){assert(c->pc==0x8c123456);assert(c->r[4]==event);assert((c->sr&SR_IMASK)==SR_IMASK);assert(!(c->sr&SR_BL));assert(c->ssr==0x60000000&&c->spc==0x8c445566&&c->sgr==0x8c00fc00);}
'''+body+r'''
int main(void){for(event=0x320;event<=0x3a0;event+=0x40){SH4CPU c={0};c.sr=0x60000000;c.pc=0x8c445566;c.r[15]=0x8c00fc00;c.vbr=0x8c00e800;c.ssr=1;c.spc=2;c.sgr=3;irq(&c);assert(stored==event);assert(c.ssr==1&&c.spc==2&&c.sgr==3);}return 0;}
'''
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'test.c').write_text(code);subprocess.run(['clang','-I',str(core/'include'),str(p/'test.c'),'-o',str(p/'test')],check=True,capture_output=True);subprocess.run([str(p/'test')],check=True)
