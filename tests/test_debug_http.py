"""A real loopback server rejects foreign origins/hosts and unauthenticated calls."""
import json,socket,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError

class DebugHTTPTests(unittest.TestCase):
 def test_auth_origin_host_and_content_type(self):
  with tempfile.TemporaryDirectory() as tmp:
   project=Path(tmp);(project/'.local/browser').mkdir(parents=True);(project/'.local/source-lock.json').write_text('{"tracks":[]}')
   with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
   process=subprocess.Popen([sys.executable,str(Path(__file__).resolve().parents[1]/'serve_browser.py'),'--project',str(project),'--port',str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
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
    registered=request('/debug/register',headers,b'{"view":"workbench"}')
    self.assertIn('session_id',registered)
    self.assertEqual(len(request('/debug/sessions',headers)['sessions']),1)
    with self.assertRaises(HTTPError) as error:request('/debug/register',{'Authorization':'Bearer '+token,'Content-Type':'text/plain'},b'{}')
    self.assertEqual(error.exception.code,400)
   finally:process.terminate();process.wait(timeout=3)
