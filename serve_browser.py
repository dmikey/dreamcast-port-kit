"""Loopback-only browser runtime and bounded, same-origin source-disc chunks."""
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
import argparse,json,secrets
from debug_service import DebugBroker

def serve(args):
    project=Path(args.project).resolve();root=project/'.local/browser'
    tracks=json.loads((project/'.local/source-lock.json').read_text())['tracks']
    broker=None
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self,format,*parts):
            if not self.path.startswith('/debug/'):super().log_message(format,*parts)
        def debug_guard(self,token=True):
            hosts=(f'127.0.0.1:{args.port}',f'localhost:{args.port}')
            if self.headers.get('Host') not in hosts or self.headers.get('Sec-Fetch-Site')=='cross-site':self.send_error(403);return False
            origin=self.headers.get('Origin')
            if origin and origin not in tuple('http://'+h for h in hosts):self.send_error(403);return False
            if token and not secrets.compare_digest(self.headers.get('Authorization',''),'Bearer '+broker.token):self.send_error(401);return False
            return True
        def json_reply(self,value,code=200):
            data=json.dumps(value).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def debug_get(self,url):
            if not self.debug_guard(url.path!='/debug/config'):return
            try:
                q=parse_qs(url.query)
                if url.path=='/debug/config':result={'token':broker.token}
                elif url.path=='/debug/sessions':result={'sessions':broker.list_sessions()}
                elif url.path=='/debug/status':result=broker.status(q['session_id'][0])
                elif url.path=='/debug/events':result={'events':broker.events(q['session_id'][0],int(q.get('limit',['100'])[0]),int(q.get('after',['-1'])[0]))}
                else:self.send_error(404);return
                self.json_reply(result)
            except (ValueError,KeyError,TypeError) as error:self.json_reply({'error':str(error)},400)
        def debug_post(self):
            if not self.debug_guard():return
            try:
                limit=12582912 if self.path=='/debug/complete' else 131072
                size=int(self.headers.get('Content-Length','0'))
                if self.headers.get('Content-Type','').split(';')[0]!='application/json' or not 0<size<=limit:raise ValueError('Invalid JSON request size or content type')
                data=json.loads(self.rfile.read(size))
                if not isinstance(data,dict):raise ValueError('Expected an object')
                if self.path=='/debug/register':result=broker.register(data.get('view'))
                elif self.path=='/debug/poll':result=broker.poll(data['session_id'],data['state'],data['events'])
                elif self.path=='/debug/disconnect':broker.disconnect(data['session_id']);result={'accepted':True}
                elif self.path=='/debug/complete':broker.complete(data['session_id'],data['id'],data['result']);result={'accepted':True}
                elif self.path=='/debug/command':result=broker.command(data['session_id'],data['name'],data['args'])
                else:self.send_error(404);return
                self.json_reply(result)
            except TimeoutError as error:self.json_reply({'error':str(error)},408)
            except (ValueError,KeyError,TypeError,UnicodeError) as error:self.json_reply({'error':str(error)},400)
        def do_POST(self):
            if self.path.startswith('/debug/'):self.debug_post();return
            if self.path!='/diagnostics':self.send_error(404);return
            origin=self.headers.get('Origin')
            if origin and origin not in (f'http://127.0.0.1:{args.port}',f'http://localhost:{args.port}'):
                self.send_error(403);return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=49152:raise ValueError()
                report=json.loads(self.rfile.read(size))
                if not isinstance(report,dict) or report.get('schemaVersion')!=1:raise ValueError()
                agent=str(report.get('userAgent',''))
                browser='safari' if 'Safari/' in agent and not any(s in agent for s in ('Chrome/','Chromium/','Edg/')) else 'other'
                # Bounded local diagnostics only; never served as public browser assets.
                destination=project/'.local'/f'browser-startup-{browser}.json'
                destination.write_text(json.dumps(report,indent=2)+'\n')
                self.send_response(204);self.end_headers()
            except (ValueError,TypeError,UnicodeError):self.send_error(400)
        def do_GET(self):
            url=urlsplit(self.path)
            if url.path.startswith('/debug/'):self.debug_get(url);return
            if url.path.startswith('/disc/'):
                try:
                    index=int(url.path.removeprefix('/disc/'));q=parse_qs(url.query)
                    start=int(q['offset'][0]);length=int(q['length'][0])
                    if not 0<=index<len(tracks) or start<0 or not 1<=length<=1024*1024:raise ValueError()
                    with Path(tracks[index]['path']).open('rb') as f:f.seek(start);data=f.read(length)
                    self.send_response(200);self.send_header('Content-Type','application/octet-stream');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
                except (ValueError,KeyError,IndexError):self.send_error(400)
            else:super().do_GET()
        def translate_path(self,path):
            relative=urlsplit(path).path.lstrip('/') or 'index.html'
            target=(root/relative).resolve()
            if not target.is_relative_to(root) or not target.is_file():return str(root/'__missing__')
            return str(target)
        def end_headers(self):
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');super().end_headers()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    broker=DebugBroker(project)
    connection=project/'.local/debug-connection.json'
    connection.write_text(json.dumps({'token':broker.token,'url':f'http://127.0.0.1:{args.port}'})+'\n');connection.chmod(0o600)
    print(f'Workbench: http://127.0.0.1:{args.port}/ — Player: /player.html',flush=True)
    server.serve_forever()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',required=True);p.add_argument('--port',type=int,default=4390);serve(p.parse_args())
