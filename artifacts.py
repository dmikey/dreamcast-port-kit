"""Private, immutable stage receipts and runnable browser build snapshots."""
from datetime import datetime,timezone
import hashlib,json,re,shutil,uuid
from pathlib import Path

ID=re.compile(r'^[a-z0-9][a-z0-9-]{0,95}$')
WEB_NAMES={'index.html','player.html','workbench.js','projects.js','debug-bridge.js','browser.js','browser.css','browser-scheduler.js','runtime-bridge.js','runtime-worker.js','runtime-loader.js','vmu-format.js','vmu-storage.js','vmu-transport.js','vmu-ui.js','audio.js','audio-worklet.js','game.js','build.json'}
def read_json(path,default=None):
    try:return json.loads(Path(path).read_text())
    except FileNotFoundError:return default

def record(project,stage,status='succeeded',message='',log=None):
    project=Path(project).resolve();manifest=read_json(project/'port.json',{})
    identity=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]
    folder=project/'.local/artifacts'/identity;folder.mkdir(parents=True)
    receipt={'schemaVersion':1,'id':identity,'createdAt':datetime.now(timezone.utc).isoformat(),'stage':stage,'status':status,'title':manifest.get('disc',{}).get('title','Dreamcast project'),'sourceSetSHA256':manifest.get('sourceSetSHA256'),'executableSHA256':manifest.get('executable',{}).get('sha256'),'profileId':manifest.get('profileId'),'projectState':manifest.get('state'),'evidence':manifest.get('evidence',{}),'message':str(message),'files':[],'runnable':False}
    metadata={'prepare':'.local/disc-inventory.json','translate':'.local/generated/provenance.json','build':'.local/native/build.json','build-browser':'.local/browser/build.json','run':'.local/native/run-result.json'}
    if manifest:(folder/'port.json').write_text(json.dumps(manifest,indent=2)+'\n')
    if status=='succeeded' and stage in metadata and (project/metadata[stage]).is_file():shutil.copyfile(project/metadata[stage],folder/'stage.json')
    if log is not None:shutil.copyfile(log,folder/'output.log')
    if stage=='build' and status=='succeeded':
        source=project/'.local/native/game-headless';build=read_json(project/'.local/native/build.json',{})
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest()!=build.get('binarySHA256'):raise ValueError('Native snapshot needs its verified build binary')
        shutil.copyfile(source,folder/'game-headless');receipt['build']=build
    if stage=='build-browser' and status=='succeeded':
        source=project/'.local/browser';build=read_json(source/'build.json',{})
        loader=source/'game.js';wasm=source/('game-'+str(build.get('wasmSHA256',''))[:16]+'.wasm')
        if not build.get('wasmSHA256') or not loader.is_file() or not wasm.is_file():raise ValueError('Browser snapshot needs a complete content-addressed build')
        actual=hashlib.sha256(wasm.read_bytes()).hexdigest()
        if actual!=build['wasmSHA256']:raise ValueError('Browser build hash does not match its WASM')
        if wasm.name not in loader.read_text():raise ValueError('Browser loader does not reference the recorded WASM')
        if build.get('sourceSetSHA256')!=manifest.get('sourceSetSHA256'):raise ValueError('Browser build belongs to a different source disc')
        bundle_names={wasm.name}
        for kind,variant in build.get('variants',{}).items():
            if kind!='jspi' or variant.get('loader')!='game-jspi.js' or variant.get('suspension')!='jspi':raise ValueError('Unknown browser build variant')
            sha=variant.get('wasmSHA256','')
            if not re.fullmatch('[a-f0-9]{64}',sha):raise ValueError('Invalid variant WASM hash')
            binary=source/('game-'+sha[:16]+'.wasm');script=source/variant['loader']
            if not binary.is_file() or hashlib.sha256(binary.read_bytes()).hexdigest()!=sha:raise ValueError('Browser variant hash does not match its WASM')
            if not script.is_file() or binary.name not in script.read_text():raise ValueError('Browser variant loader does not reference its WASM')
            bundle_names|={binary.name,script.name}
        dest=folder/'browser';dest.mkdir()
        for name in sorted(WEB_NAMES|bundle_names):
            if (source/name).is_file():shutil.copyfile(source/name,dest/name)
        receipt['build']=build;receipt['runnable']=True
    for path in sorted(p for p in folder.rglob('*') if p.is_file()):
        receipt['files'].append({'name':str(path.relative_to(folder)),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (folder/'artifact.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

def list_artifacts(project):
    root=Path(project)/'.local/artifacts'
    return sorted((read_json(p) for p in root.glob('*/artifact.json')),key=lambda r:r['createdAt'],reverse=True)
