"""A real loopback server rejects foreign origins/hosts and unauthenticated calls."""
import json,socket,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError

class DebugHTTPTests(unittest.TestCase):
 def test_auth_origin_host_and_content_type(self):
  with tempfile.TemporaryDirectory() as tmp:
   project=Path(tmp);(project/'port.json').write_text('{"disc":{"title":"Test"}}');(project/'.local/browser').mkdir(parents=True);(project/'.local/source-lock.json').write_text('{"tracks":[]}')
   with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
   process=subprocess.Popen([sys.executable,str(Path(__file__).resolve().parents[1]/'serve_browser.py'),'--project',str(project),'--port',str(port),'--workspace',str(project/'.local/workspace.json')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   try:
    base=f'http://127.0.0.1:{port}'
    for _ in range(100):
     try:
      with urlopen(base+'/debug/config',timeout=.2) as response:token=json.load(response)['token']
      break
     except OSError:time.sleep(.02)
    else:self.fail('Server did not start')
    def request(path,headers={},body=None):
     req=Request(base+path,headers=headers,data=body)
     with urlopen(req,timeout=2) as response:return json.load(response)
    for headers,code in [({},401),({'Authorization':'Bearer wrong'},401),({'Authorization':'Bearer '+token,'Origin':'https://evil.example'},403),({'Authorization':'Bearer '+token,'Host':'evil.example'},403)]:
     with self.assertRaises(HTTPError) as error:request('/debug/sessions',headers)
     self.assertEqual(error.exception.code,code)
    headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','Origin':base}
    # Current worker tools can open an older, Asyncify-only build. The served
    # selector contains this project's identity, never the unexpanded template.
    (project/'.local/browser/build.json').write_text(json.dumps({'wasmSHA256':'a'*64}))
    with urlopen(base+'/runtime-loader.js') as response:selector=response.read().decode()
    self.assertNotIn('/*PORT_RUNTIME_BUILDS*/',selector);self.assertIn('a'*64,selector);self.assertIn('"loader": "game.js"',selector)
    registered=request('/debug/register',headers,b'{"view":"workbench"}')
    self.assertIn('session_id',registered)
    self.assertEqual(len(request('/debug/sessions',headers)['sessions']),1)
    with self.assertRaises(HTTPError) as error:request('/debug/register',{'Authorization':'Bearer '+token,'Content-Type':'text/plain'},b'{}')
    self.assertEqual(error.exception.code,400)
    # VMU writes are authenticated, conditional and persistent on disk.
    from vmu import VmuStore
    with urlopen(base+'/vmu/a1.bin') as response:card=response.read();tag=response.headers['ETag']
    self.assertEqual(len(card),131072)
    write_headers={'Authorization':'Bearer '+token,'Content-Type':'application/octet-stream','If-Match':tag,'Origin':base}
    result=request('/vmu/a1/phase?block=10&phase=0',write_headers,b'V'*128)
    self.assertNotEqual(result['etag'],tag);self.assertEqual(VmuStore(project).load()[5120:5248],b'V'*128)
    with self.assertRaises(HTTPError) as error:request('/vmu/a1/phase?block=10&phase=0',write_headers,b'X'*128)
    self.assertEqual(error.exception.code,409);self.assertEqual(VmuStore(project).load()[5120:5248],b'V'*128)
    with self.assertRaises(HTTPError) as error:request('/vmu/a1/phase?block=256&phase=0',{**write_headers,'If-Match':result['etag']},b'X'*128)
    self.assertEqual(error.exception.code,400)
    with self.assertRaises(HTTPError) as error:request('/vmu/a1/phase?block=10&phase=0',{'Content-Type':'application/octet-stream','If-Match':tag},b'X'*128)
    self.assertEqual(error.exception.code,401)
    # Registry updates are picked up without restarting; discs and tokens stay scoped.
    from workspace import Workspace
    from artifacts import record
    track=project/'track.raw';track.write_bytes(b'AAA');(project/'.local/source-lock.json').write_text(json.dumps({'tracks':[{'path':str(track)}]}))
    other=project/'second';(other/'.local').mkdir(parents=True);(other/'port.json').write_text('{"disc":{"title":"Second"},"state":"needs-title-profile"}')
    second_track=other/'track.raw';second_track.write_bytes(b'BBB');(other/'.local/source-lock.json').write_text(json.dumps({'tracks':[{'path':str(second_track)}]}))
    Workspace(project/'.local/workspace.json').add(other,'second');receipt=record(other,'prepare')
    with urlopen(base+'/projects/second/vmu/a1.bin') as response:self.assertEqual(response.read()[5120:5248],bytes(128))
    catalog=request('/projects/second/workspace');self.assertEqual(len(catalog['projects']),2);self.assertEqual(catalog['selected']['id'],'second');self.assertFalse(catalog['selected']['browserReady'])
    for route,expected in [('/disc/0?offset=0&length=1',b'A'),('/projects/second/disc/0?offset=0&length=1',b'B')]:
     with urlopen(base+route) as response:self.assertEqual(response.read(),expected)
    with self.assertRaises(HTTPError) as error:request('/projects/second/debug/sessions',headers)
    self.assertEqual(error.exception.code,401)
    artifact='/projects/second/artifacts/'+receipt['id']
    self.assertEqual(request(artifact+'/receipt.json')['stage'],'prepare')
    with self.assertRaises(HTTPError):request(artifact+'/files/../../port.json')
    with urlopen(base+'/projects/second/') as response:self.assertIn(b'data-build-ready="false"',response.read())
   finally:process.terminate();process.wait(timeout=3)
