"""Loopback-only multi-project workbench, immutable builds and source-disc chunks."""
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit,parse_qs,unquote
import argparse,html,json,secrets,threading,time
from debug_service import DebugBroker
from workspace import Workspace,DEFAULT
from vmu import VmuStore,VmuConflict,etag
from artifacts import ID,WEB_NAMES,read_json,list_artifacts


def serve(args):
    kit=Path(__file__).resolve().parent
    workspace=Workspace(getattr(args,'workspace',DEFAULT))
    default_project=Path(args.project).resolve()
    default=next((e['id'] for e in workspace.entries() if Path(e['path'])==default_project),None) or workspace.add(default_project)['id']
    contexts={};context_lock=threading.Lock()
    def context(identity):
        with context_lock:
            if identity not in contexts:
                project=workspace.resolve(identity);broker=DebugBroker(project)
                connection=project/'.local/debug-connection.json'
                connection.write_text(json.dumps({'token':broker.token,'url':f'http://127.0.0.1:{args.port}','basePath':'/projects/'+identity+'/'})+'\n');connection.chmod(0o600)
                contexts[identity]=(project,broker,VmuStore(project))
            return contexts[identity]
    class Handler(SimpleHTTPRequestHandler):
        def route(self):
            url=urlsplit(self.path);parts=unquote(url.path).split('/')
            self.identity=default;self.artifact=None;self.local_path=url.path
            if len(parts)>2 and parts[1]=='projects':
                self.identity=parts[2]
                if not ID.fullmatch(self.identity):raise ValueError('Invalid project id')
                if len(parts)==3:
                    self.send_response(302);self.send_header('Location',url.path+'/');self.end_headers();return False
                self.local_path='/'+'/'.join(parts[3:])
                if len(parts)>4 and parts[3]=='artifacts':
                    self.artifact=parts[4]
                    if not ID.fullmatch(self.artifact):raise ValueError('Invalid artifact id')
                    self.local_path='/'+'/'.join(parts[5:])
            self.project,self.broker,self.vmu=context(self.identity)
            self.root=self.project/'.local/browser'
            if self.artifact:
                folder=self.project/'.local/artifacts'/self.artifact
                self.receipt=read_json(folder/'artifact.json')
                if not self.receipt:raise KeyError('Unknown artifact')
                self.root=folder/'browser'
            self.query=url.query
            return True
        def log_message(self,format,*parts):
            if '/debug/' not in self.path and not self.path.endswith('/workspace'):super().log_message(format,*parts)
        def debug_guard(self,token=True):
            hosts=(f'127.0.0.1:{args.port}',f'localhost:{args.port}')
            if self.headers.get('Host') not in hosts or self.headers.get('Sec-Fetch-Site')=='cross-site':self.send_error(403);return False
            origin=self.headers.get('Origin')
            if origin and origin not in tuple('http://'+h for h in hosts):self.send_error(403);return False
            if token and not secrets.compare_digest(self.headers.get('Authorization',''),'Bearer '+self.broker.token):self.send_error(401);return False
            return True
        def json_reply(self,value,code=200):
            data=json.dumps(value).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def debug_get(self):
            if not self.debug_guard(self.local_path!='/debug/config'):return
            q=parse_qs(self.query);broker=self.broker
            if self.local_path=='/debug/config':result={'token':broker.token,'projectId':self.identity}
            elif self.local_path=='/debug/sessions':result={'sessions':broker.list_sessions()}
            elif self.local_path=='/debug/status':result=broker.status(q['session_id'][0]);result['projectId']=self.identity
            elif self.local_path=='/debug/events':result={'events':broker.events(q['session_id'][0],int(q.get('limit',['100'])[0]),int(q.get('after',['-1'])[0]))}
            else:self.send_error(404);return
            self.json_reply(result)
        def debug_post(self):
            if not self.debug_guard():return
            limit=12582912 if self.local_path=='/debug/complete' else 131072
            size=int(self.headers.get('Content-Length','0'))
            if self.headers.get('Content-Type','').split(';')[0]!='application/json' or not 0<size<=limit:raise ValueError('Invalid JSON request size or content type')
            data=json.loads(self.rfile.read(size));broker=self.broker
            if not isinstance(data,dict):raise ValueError('Expected an object')
            if self.local_path=='/debug/register':result=broker.register(data.get('view'))
            elif self.local_path=='/debug/poll':result=broker.poll(data['session_id'],data['state'],data['events'])
            elif self.local_path=='/debug/disconnect':broker.disconnect(data['session_id']);result={'accepted':True}
            elif self.local_path=='/debug/complete':broker.complete(data['session_id'],data['id'],data['result']);result={'accepted':True}
            elif self.local_path=='/debug/command':result=broker.command(data['session_id'],data['name'],data['args'])
            else:self.send_error(404);return
            self.json_reply(result)
        def do_POST(self):
            try:
                if not self.route():return
                if self.local_path=='/vmu/a1/phase':
                    if not self.debug_guard():return
                    if self.headers.get('Content-Type')!='application/octet-stream' or self.headers.get('Content-Length')!='128':raise ValueError('Expected one 128-byte VMU phase')
                    q=parse_qs(self.query);tag=self.vmu.write_phase(int(q['block'][0]),int(q['phase'][0]),self.rfile.read(128),self.headers.get('If-Match'))
                    self.json_reply({'etag':tag});return
                if self.local_path.startswith('/debug/'):self.debug_post();return
                if self.local_path!='/diagnostics':self.send_error(404);return
                if not self.debug_guard(False):return
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=49152:raise ValueError('Invalid diagnostic size')
                report=json.loads(self.rfile.read(size))
                if not isinstance(report,dict) or report.get('schemaVersion')!=1:raise ValueError('Invalid diagnostics')
                agent=str(report.get('userAgent',''))
                browser='safari' if 'Safari/' in agent and not any(s in agent for s in ('Chrome/','Chromium/','Edg/')) else 'other'
                (self.project/'.local'/f'browser-startup-{browser}.json').write_text(json.dumps(report,indent=2)+'\n')
                if report.get('reason') not in ('Runtime initialized','Starting worker runtime'):
                    (self.project/'.local'/f'browser-fault-{browser}-{time.time_ns()}.json').write_text(json.dumps(report,indent=2)+'\n')
                    for old in sorted((self.project/'.local').glob('browser-fault-*.json'))[:-10]:old.unlink()
                self.send_response(204);self.end_headers()
            except VmuConflict as error:self.json_reply({'error':str(error)},409)
            except TimeoutError as error:self.json_reply({'error':str(error)},408)
            except (ValueError,KeyError,TypeError,UnicodeError) as error:self.json_reply({'error':str(error)},400)
        def do_GET(self):
            try:
                if not self.route():return
                if self.local_path=='/vmu/a1.bin':
                    if not self.debug_guard(False):return
                    data=self.vmu.load();self.send_bytes(data,'application/octet-stream',{'ETag':etag(data)});return
                if self.local_path=='/vmu/status':
                    if not self.debug_guard(False):return
                    self.json_reply(self.vmu.status());return
                if self.local_path=='/workspace':
                    if not self.debug_guard(False):return
                    self.json_reply({'projects':workspace.list(),'selected':workspace.describe(self.identity),'artifacts':list_artifacts(self.project),'selectedArtifact':self.artifact});return
                if self.local_path.startswith('/debug/'):self.debug_get();return
                if self.local_path.startswith('/disc/'):
                    if not self.debug_guard(False):return
                    tracks=read_json(self.project/'.local/source-lock.json')['tracks'];index=int(self.local_path.removeprefix('/disc/'));q=parse_qs(self.query)
                    start=int(q['offset'][0]);length=int(q['length'][0])
                    if not 0<=index<len(tracks) or start<0 or not 1<=length<=1024*1024:raise ValueError('Invalid disc range')
                    with Path(tracks[index]['path']).open('rb') as f:f.seek(start);data=f.read(length)
                    self.send_response(200);self.send_header('Content-Type','application/octet-stream');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
                if self.artifact and self.local_path.startswith('/files/'):
                    if not self.debug_guard(False):return
                    name=self.local_path.removeprefix('/files/')
                    if name not in [f['name'] for f in self.receipt['files']]:self.send_error(404);return
                    target=(self.project/'.local/artifacts'/self.artifact/name).resolve()
                    if not target.is_relative_to((self.project/'.local/artifacts'/self.artifact).resolve()):self.send_error(404);return
                    self.download=True;self.send_file(target);return
                if self.artifact and self.local_path in ('/receipt.json','/output.log','/stage.json','/port.json'):
                    if not self.debug_guard(False):return
                    name='artifact.json' if self.local_path=='/receipt.json' else self.local_path[1:]
                    self.send_file(self.project/'.local/artifacts'/self.artifact/name);return
                name=self.local_path.lstrip('/') or 'index.html'
                target=(self.root/name).resolve()
                if not target.is_relative_to(self.root.resolve()):self.send_error(404);return
                if not self.artifact and name in WEB_NAMES-{'game.js','build.json'}:
                    # Current workspaces use current tools. Historical builds retain their tools.
                    target=kit/'runtime/web'/name
                if name in ('index.html','player.html') and target.is_file():
                    info=workspace.describe(self.identity);ready=self.receipt['runnable'] if self.artifact else info['browserReady']
                    data=target.read_text().replace('>Dreamcast game</strong>','>'+html.escape(info['title'])+'</strong>')
                    data=data.replace('<body ',f'<body data-project-id="{html.escape(self.identity,quote=True)}" data-build-ready="{str(ready).lower()}" ')
                    self.send_bytes(data.encode(),'text/html; charset=utf-8');return
                self.send_file(target)
            except (ValueError,KeyError,TypeError,UnicodeError,IndexError) as error:self.json_reply({'error':str(error)},400)
        def send_bytes(self,data,mime,headers=None):
            self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)));
            for key,value in (headers or {}).items():self.send_header(key,value)
            self.end_headers();self.wfile.write(data)
        def send_file(self,path):
            if not path.is_file():self.send_error(404);return
            # Stream build files rather than buffering large WASM downloads.
            self.send_response(200);self.send_header('Content-Type',self.guess_type(str(path)));
            if getattr(self,'download',False):self.send_header('Content-Disposition','attachment; filename="'+path.name+'"')
            self.send_header('Content-Length',str(path.stat().st_size));self.end_headers()
            with path.open('rb') as source:self.copyfile(source,self.wfile)
        def end_headers(self):
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');super().end_headers()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    context(default)
    print(f'Workbench: http://127.0.0.1:{args.port}/ — Projects: /projects/<id>/ — Player: /player.html',flush=True)
    server.serve_forever()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',required=True);p.add_argument('--port',type=int,default=4390);p.add_argument('--workspace',default=str(DEFAULT));serve(p.parse_args())
