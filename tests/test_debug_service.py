"""Command broker correctness and strict parameter boundaries; no game fixtures."""
import tempfile,threading,time,unittest
from pathlib import Path
from debug_service import DebugBroker,validate_command

class DebugBrokerTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.broker=DebugBroker(Path(self.temp.name));self.sid=self.broker.register('workbench')['session_id']
 def test_command_is_acknowledged_once_and_not_replayed(self):
  result=[];thread=threading.Thread(target=lambda:result.append(self.broker.command(self.sid,'press_button',{'button':'A','duration_ms':200})));thread.start()
  for _ in range(100):
   commands=self.broker.poll(self.sid,{'state':'running'},[])['commands']
   if commands:break
   time.sleep(.001)
  self.assertEqual(len(commands),1);self.assertEqual(self.broker.poll(self.sid,{},[])['commands'],[])
  self.broker.complete(self.sid,commands[0]['id'],{'accepted':True});thread.join(1);self.assertFalse(thread.is_alive());self.assertEqual(result,[{'accepted':True}])
 def test_unrelated_session_cannot_complete_command(self):
  errors=[]
  def run():
   try:self.broker.command(self.sid,'start',{},timeout=.05)
   except TimeoutError:errors.append(True)
  thread=threading.Thread(target=run);thread.start()
  for _ in range(100):
   commands=self.broker.poll(self.sid,{},[])['commands']
   if commands:break
   time.sleep(.001)
  other=self.broker.register('player')['session_id']
  with self.assertRaises(ValueError):self.broker.complete(other,commands[0]['id'],{})
  thread.join(1);self.assertTrue(errors)
  self.assertEqual(self.broker.poll(self.sid,{},[])['commands'],[])
 def test_events_are_bounded_and_tokens_private(self):
  for block in range(12):self.broker.poll(self.sid,{},[{'sequence':block*200+i,'message':'x'} for i in range(200)])
  self.assertEqual(len(self.broker.sessions[self.sid]['events']),2048)
  self.assertEqual(self.broker.events(self.sid,1)[0]['sequence'],2399)
  self.assertEqual([event['sequence'] for event in self.broker.events(self.sid,2,400)],[401,402])
  self.assertEqual((Path(self.temp.name)/'.local/debug-connection.json').stat().st_mode&0o777,0o600)
 def test_rejects_raw_code_unknown_fields_and_unbounded_input(self):
  for name,args in [('eval',{'code':'anything'}),('start',{'code':'x'}),('press_button',{'button':'A','duration_ms':6000}),('press_button',{'button':'Unknown','duration_ms':100}),('drive',{'accelerator':float('nan'),'brake':0,'steer':0,'duration_ms':200}),('pause',{'paused':1})]:
   with self.assertRaises(ValueError):validate_command(name,args)
  for action,index,name in [('rename',0,None),('copy',208,None),('rename',0,'../save'),('delete',False,None)]:
   with self.assertRaises(ValueError):validate_command('vmu_edit',{'action':action,'index':index,'name':name})
