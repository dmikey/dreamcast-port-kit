"""Independent, deliberately limited SH-4 oracle for generated RAM-only fixtures.

Not a full SH-4 interpreter or a commercial-game validation result. Unsupported
opcodes fail; hardware operations are excluded by construction, never replayed.
"""
import argparse,importlib.util,json,random,struct,subprocess,tempfile
from pathlib import Path
BASE=0x8c010000
RAM=0x0c100000
MASK=0xffffffff
COVERAGE=['mov immediate/register','add immediate/register','cmp/eq','tst','mov.l RAM load/store','bt/bf','bra + delay slot','rts + delay slot']
class ValidationMismatch(RuntimeError):pass

def signed(value,bits):return value-(1<<bits) if value&(1<<(bits-1)) else value

def reference(words,registers,sr,memory):
 r=list(registers);mem=list(memory);writes=[];pc=0;steps=0
 def ordinary(op):
  nonlocal sr
  n=(op>>8)&15;m=(op>>4)&15
  if op==9:return
  if op&0xf000==0xe000:r[n]=signed(op&255,8)&MASK
  elif op&0xf000==0x7000:r[n]=(r[n]+signed(op&255,8))&MASK
  elif op&0xf00f==0x6003:r[n]=r[m]
  elif op&0xf00f==0x300c:r[n]=(r[n]+r[m])&MASK
  elif op&0xf00f==0x3000:sr=(sr&~1)|int(r[n]==r[m])
  elif op&0xf00f==0x2008:sr=(sr&~1)|int((r[n]&r[m])==0)
  elif op&0xf000==0x1000:
   address=r[n]+(op&15)*4
   if address&3 or not RAM<=address<RAM+64:raise ValueError('outside isolated RAM')
   mem[(address-RAM)//4]=r[m];writes.append([address,r[m]])
  elif op&0xf000==0x5000:
   address=r[m]+(op&15)*4
   if address&3 or not RAM<=address<RAM+64:raise ValueError('outside isolated RAM')
   r[n]=mem[(address-RAM)//4]
  else:raise ValueError(f'unsupported oracle opcode {op:04x}')
 while steps<200:
  op=words[pc];steps+=1
  if op==0xb:
   ordinary(words[pc+1]);steps+=1;break
  if op&0xff00 in (0x8900,0x8b00):
   take=bool(sr&1)==(op&0xff00==0x8900)
   pc=pc+2+signed(op&255,8) if take else pc+1
  elif op&0xf000==0xa000:
   ordinary(words[pc+1]);steps+=1;pc=pc+2+signed(op&0xfff,12)
  else:ordinary(op);pc+=1
 else:raise ValueError('oracle step budget')
 return {'registers':r,'sr':sr,'pr':0x8c070000,'memory':mem,'writes':writes},steps

def programs_for(seed,count):
 rng=random.Random(seed);programs=[];regs=[0,1,2,3,5,6,7,8,9,10,11,12,13,14]
 for _ in range(count):
  words=[]
  for _ in range(24):
   n=rng.choice(regs);m=rng.choice(regs);kind=rng.randrange(8)
   if kind==0:op=0xe000|(n<<8)|rng.randrange(256)
   elif kind==1:op=0x7000|(n<<8)|rng.randrange(256)
   elif kind==2:op=0x6003|(n<<8)|(m<<4)
   elif kind==3:op=0x300c|(n<<8)|(m<<4)
   elif kind==4:op=0x3000|(n<<8)|(m<<4)
   elif kind==5:op=0x2008|(n<<8)|(m<<4)
   elif kind==6:op=0x1400|(m<<4)|rng.randrange(16)
   else:op=0x5040|(n<<8)|rng.randrange(16)
   words.append(op)
  words += [0x3010,0x8901,0xe001,0x7003,0x2018,0x8b01,0xe2ff,0x7204,0xa001,0x7301,0xe300,0x000b,0x0009]
  programs.append(words)
 return programs

def validate(toolchain,programs=16,cases=64,seed=1,mutate=None):
 core=Path(toolchain).resolve();spec=importlib.util.spec_from_file_location('translator',core/'tools/static_recompile.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 streams=programs_for(seed,programs);functions=[]
 for i,words in enumerate(streams):
  compiler=module.SH4Recompiler(struct.pack('<'+'H'*len(words),*words),BASE)
  compiler.entry_hints=set();compiler.mid_entries={}
  code=compiler.recompile_function(BASE,{'end':BASE+2*len(words)})
  code=code.replace('func_8C010000',f'fixture_{i}')
  if mutate:code=mutate(code)
  functions.append(code)
 source='''#include "recompiler/sh4_cpu.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static uint32_t memory[16],writes[256][2];static unsigned count;
uint32_t sh4_read32(SH4CPU *c,uint32_t a){if(a<0x0c100000||a>=0x0c100040||(a&3))abort();return memory[(a-0x0c100000)/4];}
void sh4_write32(SH4CPU *c,uint32_t a,uint32_t v){if(a<0x0c100000||a>=0x0c100040||(a&3)||count>=256)abort();memory[(a-0x0c100000)/4]=v;writes[count][0]=a;writes[count++][1]=v;}
'''+ '\n'.join(functions)+ '\nstatic void (*fixtures[])(SH4CPU*)={'+','.join(f'fixture_{i}' for i in range(programs))+'};\n'+'''
int main(void){unsigned program;while(scanf("%u",&program)==1){SH4CPU cpu={0};for(int i=0;i<16;i++)if(scanf("%u",&cpu.r[i])!=1)return 2;if(scanf("%u",&cpu.sr)!=1)return 2;for(int i=0;i<16;i++)if(scanf("%u",&memory[i])!=1)return 2;cpu.pr=0x8c070000;count=0;fixtures[program](&cpu);printf("{\\"registers\\":[");for(int i=0;i<16;i++)printf("%s%u",i?",":"",cpu.r[i]);printf("],\\"sr\\":%u,\\"pr\\":%u,\\"memory\\":[",cpu.sr,cpu.pr);for(int i=0;i<16;i++)printf("%s%u",i?",":"",memory[i]);printf("],\\"writes\\":[");for(int i=0;i<count;i++)printf("%s[%u,%u]",i?",":"",writes[i][0],writes[i][1]);puts("]}");}return 0;}
'''
 rng=random.Random(seed^0xa5a5);expected=[];inputs=[];steps=0
 for i,words in enumerate(streams):
  for case in range(cases):
   registers=[rng.getrandbits(32) for _ in range(16)];registers[4]=RAM
   sr=rng.getrandbits(32);memory=[rng.getrandbits(32) for _ in range(16)]
   result,n=reference(words,registers,sr,memory);steps+=n;expected.append(result)
   inputs.append(' '.join(map(str,[i,*registers,sr,*memory])))
 with tempfile.TemporaryDirectory() as d:
  path=Path(d);(path/'fixture.c').write_text(source)
  build=subprocess.run(['clang','-std=c11','-O2','-fwrapv','-I',str(core/'include'),str(path/'fixture.c'),'-o',str(path/'fixture')],capture_output=True,text=True)
  if build.returncode:raise RuntimeError(build.stderr)
  run=subprocess.run([str(path/'fixture')],input='\n'.join(inputs)+'\n',capture_output=True,text=True,timeout=30,check=True)
  actual=[json.loads(line) for line in run.stdout.splitlines()]
 if len(actual)!=len(expected):raise ValidationMismatch('missing candidate result')
 for index,(want,got) in enumerate(zip(expected,actual)):
  if want!=got:
   raise ValidationMismatch(json.dumps({'seed':seed,'program':index//cases,'case':index%cases,'opcodes':[f'{w:04x}' for w in streams[index//cases]],'input':inputs[index],'expected':want,'actual':got}))
 return {'schemaVersion':1,'seed':seed,'programs':programs,'casesPerProgram':cases,'comparisons':len(expected),'referenceInstructions':steps,'mismatches':0,'opcodeCoverage':COVERAGE,'scope':'synthetic RAM-only integer/control-flow fixtures','compared':['16 integer registers','SR','PR','isolated RAM contents','ordered RAM writes'],'notCompared':['FPU','live dispatch PC','MMIO','interrupts','DMA','store queues','commercial game state'],'reference':'independent subset oracle; not Flycast interpreter','candidate':'actual pinned static translator output compiled at O2'}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--toolchain',required=True);p.add_argument('--programs',type=int,default=32);p.add_argument('--cases',type=int,default=128);p.add_argument('--seed',type=int,default=1);p.add_argument('--report');a=p.parse_args()
 if not 1<=a.programs<=256 or not 1<=a.cases<=1024:p.error('programs 1..256; cases 1..1024')
 result=validate(a.toolchain,a.programs,a.cases,a.seed);encoded=json.dumps(result,indent=2);print(encoded)
 if a.report:Path(a.report).write_text(encoded+'\n')
