"""Immutable build history, honest evidence and project identity boundaries."""
import hashlib,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from artifacts import record,list_artifacts
from workspace import Workspace

class ArtifactsTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.project=self.root/'one';self.project.mkdir()
  self.manifest={'disc':{'title':'First game'},'sourceSetSHA256':'disc-one','profileId':None,'executable':{'path':'.local/extracted/game.bin','sha256':hashlib.sha256(b'fixture').hexdigest()},'state':'needs-title-profile','evidence':{'discRead':True,'browserPlayable':False}}
  (self.project/'port.json').write_text(json.dumps(self.manifest))
  executable=self.project/'.local/extracted/game.bin';executable.parent.mkdir(parents=True);executable.write_bytes(b'fixture')
 def build(self,data=b'original complete WASM',source='disc-one'):
  web=self.project/'.local/browser';web.mkdir(parents=True,exist_ok=True);sha=hashlib.sha256(data).hexdigest();name='game-'+sha[:16]+'.wasm'
  (web/name).write_bytes(data);(web/'game.js').write_text('fetch("'+name+'")');(web/'browser.css').write_text('original css');(web/'build.json').write_text(json.dumps({'wasmSHA256':sha,'sourceSetSHA256':source}));return web,name
 def test_snapshots_retain_old_bytes_and_never_claim_playability(self):
  web,name=self.build();first=record(self.project,'build-browser');folder=self.project/'.local/artifacts'/first['id']
  (web/'browser.css').write_text('new css');self.build(b'new WASM');second=record(self.project,'build-browser')
  self.assertNotEqual(first['id'],second['id']);self.assertEqual((folder/'browser'/name).read_bytes(),b'original complete WASM');self.assertEqual((folder/'browser/browser.css').read_text(),'original css')
  self.assertTrue(first['runnable']);self.assertFalse(first['evidence']['browserPlayable']);self.assertEqual(len(list_artifacts(self.project)),2)
 def test_mismatched_wasm_or_disc_cannot_be_saved_as_runnable(self):
  web,name=self.build();(web/name).write_bytes(b'corrupt')
  with self.assertRaisesRegex(ValueError,'hash'):record(self.project,'build-browser')
  self.build(source='other-disc')
  with self.assertRaisesRegex(ValueError,'different source'):record(self.project,'build-browser')
  self.assertEqual(list_artifacts(self.project),[])
 def test_failed_stage_cannot_adopt_previous_build(self):
  self.build();receipt=record(self.project,'build-browser','failed','Missing title profile')
  self.assertFalse(receipt['runnable']);self.assertNotIn('build',receipt);self.assertNotIn('stage.json',[f['name'] for f in receipt['files']]);self.assertIn('Missing title profile',receipt['message'])
 def test_registry_rejects_alias_collisions_and_reports_missing_fields(self):
  ws=Workspace(self.root/'workspace.json');ws.add(self.project,'first');self.assertEqual(ws.resolve('first'),self.project.resolve())
  other=self.root/'other';other.mkdir();(other/'port.json').write_text(json.dumps(self.manifest))
  with self.assertRaises(ValueError):ws.add(other,'first')
  with self.assertRaises(ValueError):ws.add(self.project,'../escape')
  info=ws.describe('first');self.assertFalse(info['browserReady']);self.assertIn('irqEntry',info['missingProfileFields']);self.assertNotIn('path',info)
 def test_cli_failure_is_visible_in_history(self):
  result=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'port.py'),'build-browser','--project',str(self.project),'--toolchain',str(self.root/'missing'),'--emsdk',str(self.root/'missing')],capture_output=True,text=True)
  self.assertEqual(result.returncode,2);receipts=list_artifacts(self.project);self.assertEqual(len(receipts),1);self.assertEqual(receipts[0]['status'],'failed');self.assertIn('output.log',[f['name'] for f in receipts[0]['files']])
