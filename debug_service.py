"""Bounded local command broker shared by the browser and the stdio MCP server."""
import base64,copy,json,secrets,threading,time,uuid
from pathlib import Path

BUTTONS={'A':4,'B':2,'X':1024,'Y':512,'Start':8,'Up':16,'Down':32,'Left':64,'Right':128}
MODES={'normal':7,'opaque':1,'translucent':4,'no-depth':15}

def validate_command(name,args):
    fields={'start':set(),'pause':{'paused'},'press_button':{'button','duration_ms'},'drive':{'accelerator','brake','steer','duration_ms'},'render_mode':{'mode'},'capture_frame':set()}
    if name not in fields or not isinstance(args,dict) or set(args)!=fields[name]:raise ValueError('Unknown command or parameters')
    if name=='pause' and type(args['paused']) is not bool:raise ValueError('paused must be boolean')
    if name=='press_button' and args['button'] not in BUTTONS:raise ValueError('Unknown controller button')
    if 'duration_ms' in args and (type(args['duration_ms']) is not int or not 16<=args['duration_ms']<=5000):raise ValueError('duration_ms must be 16..5000')
    if name=='drive':
        for key,lo in [('accelerator',0),('brake',0),('steer',-1)]:
            if type(args[key]) not in (int,float) or not lo<=args[key]<=1:raise ValueError('Control values out of range')
    if name=='render_mode' and args['mode'] not in MODES:raise ValueError('Unknown render mode')
    return copy.deepcopy(args)

class DebugBroker:
    def __init__(self,project):
        self.root=Path(project)/'.local';self.root.mkdir(parents=True,exist_ok=True)
        self.token=secrets.token_urlsafe(32);self.lock=threading.Condition();self.sessions={};self.pending={}
        path=self.root/'debug-connection.json'
        path.write_text(json.dumps({'token':self.token})+'\n');path.chmod(0o600)
    def register(self,view):
        with self.lock:
            now=time.monotonic()
            for key in list(self.sessions):
                if now-self.sessions[key]['seen']>120 or self.sessions[key]['seen']==0:del self.sessions[key]
            if len(self.sessions)>=16:raise ValueError('Too many active browser sessions')
            identity=str(uuid.uuid4());self.sessions[identity]={'id':identity,'view':'player' if view=='player' else 'workbench','seen':now,'state':{},'events':[],'commands':[]};return {'session_id':identity}
    def poll(self,identity,state,events):
        if not isinstance(state,dict) or not isinstance(events,list) or len(events)>200:raise ValueError('Invalid browser report')
        with self.lock:
            session=self.sessions[identity];session['seen']=time.monotonic();session['state']=copy.deepcopy(state)
            for event in events:
                if isinstance(event,dict) and type(event.get('sequence')) is int and isinstance(event.get('message'),str):session['events'].append({'sequence':event['sequence'],'message':event['message'][:2000]})
            session['events']=session['events'][-2048:]
            for cid in list(session['commands']):
                if cid not in self.pending:session['commands'].remove(cid)
            commands=[]
            if session['commands']:
                cid=session['commands'].pop(0);item=self.pending.get(cid)
                if item and item['result'] is None:commands=[{'id':cid,'name':item['name'],'args':item['args']}]
            return {'commands':commands}
    def disconnect(self,identity):
        with self.lock:
            if identity not in self.sessions:return
            self.sessions[identity]['seen']=0
            for item in self.pending.values():
                if item['session']==identity and item['result'] is None:item['result']={'error':'Browser session closed'}
            self.lock.notify_all()
    def list_sessions(self):
        with self.lock:return [{'session_id':s['id'],'view':s['view'],'connected':time.monotonic()-s['seen']<10,'state':s['state'].get('state','idle')} for s in sorted(self.sessions.values(),key=lambda item:item['seen'],reverse=True)]
    def status(self,identity):
        with self.lock:
            s=self.sessions[identity];return {'session_id':identity,'view':s['view'],'connected':time.monotonic()-s['seen']<10,'age_seconds':round(time.monotonic()-s['seen'],2),**copy.deepcopy(s['state'])}
    def events(self,identity,limit,after=-1):
        if type(limit) is not int or not 1<=limit<=200:raise ValueError('limit must be 1..200')
        with self.lock:return copy.deepcopy([e for e in self.sessions[identity]['events'] if e['sequence']>after][-limit:])
    def command(self,identity,name,args,timeout=12):
        args=validate_command(name,args)
        with self.lock:
            s=self.sessions[identity]
            if time.monotonic()-s['seen']>10:raise ValueError('Browser session is disconnected')
            if sum(1 for p in self.pending.values() if p['session']==identity)>=4:raise ValueError('Session command queue is full')
            cid=str(uuid.uuid4());self.pending[cid]={'session':identity,'name':name,'args':args,'result':None};s['commands'].append(cid);end=time.monotonic()+timeout
            try:
                while self.pending[cid]['result'] is None:
                    remaining=end-time.monotonic()
                    if remaining<=0:raise TimeoutError('Browser did not acknowledge the command; it was not retried')
                    self.lock.wait(remaining)
                return copy.deepcopy(self.pending[cid]['result'])
            finally:self.pending.pop(cid,None)
    def complete(self,identity,cid,result):
        if not isinstance(result,dict):raise ValueError('Invalid command result')
        with self.lock:
            item=self.pending.get(cid)
            if not item or item['session']!=identity:raise ValueError('Expired or unrelated command')
            if item['result'] is not None:raise ValueError('Command already completed')
            if 'png_base64' in result:
                if item['name']!='capture_frame' or len(result['png_base64'])>12000000:raise ValueError('Unexpected capture')
                pixels=base64.b64decode(result.pop('png_base64'),validate=True)
                if not pixels.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Capture is not a PNG')
                folder=self.root/'debug-captures';folder.mkdir(exist_ok=True);path=folder/(cid+'.png');path.write_bytes(pixels);result['capture_path']=str(path.resolve())
            item['result']=copy.deepcopy(result);self.lock.notify_all()
