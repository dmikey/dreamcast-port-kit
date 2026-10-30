#!/usr/bin/env python3
"""Local project registry. Discs and generated artifacts remain inside each project."""
import argparse,json,re
from pathlib import Path
from artifacts import ID,read_json,list_artifacts,record
DEFAULT=Path(__file__).resolve().parent/'.local/workspace.json'

class Workspace:
    def __init__(self,path=DEFAULT):self.path=Path(path).resolve()
    def entries(self):return read_json(self.path,{'schemaVersion':1,'projects':[]})['projects']
    def add(self,project,identity=None):
        project=Path(project).resolve();manifest=read_json(project/'port.json')
        if not manifest:raise ValueError('Import the disc first: project has no port.json')
        identity=identity or re.sub('[^a-z0-9]+','-',manifest['disc']['title'].lower()).strip('-')[:80]
        if not ID.fullmatch(identity):raise ValueError('Use a lowercase project id with letters, numbers and hyphens')
        entries=self.entries()
        for entry in entries:
            if entry['id']==identity and Path(entry['path'])!=project:raise ValueError('Project id already belongs to another directory')
            if Path(entry['path'])==project:
                if entry['id']!=identity:raise ValueError('Project directory already has another id')
                return entry
        entry={'id':identity,'path':str(project)};entries.append(entry);self.path.parent.mkdir(parents=True,exist_ok=True)
        pending=self.path.with_suffix('.tmp');pending.write_text(json.dumps({'schemaVersion':1,'projects':entries},indent=2)+'\n');pending.replace(self.path);return entry
    def resolve(self,identity):
        entry=next((e for e in self.entries() if e['id']==identity),None)
        if not entry:raise KeyError('Unknown project')
        return Path(entry['path']).resolve()
    def describe(self,identity):
        project=self.resolve(identity);manifest=read_json(project/'port.json',{});artifacts=list_artifacts(project)
        profile=read_json(project/'title-profile.json',{})
        required=['loadAddress','runtimeEntry','stackPointer','vectorBase','ramBytes']+(['irqEventAddress','irqVectorTableOffset'] if profile.get('irqMode')=='vector-table' else ['irqEntry','irqPushRegisters'])
        missing=[k for k in required if profile.get(k) is None] if not manifest.get('profileId') else []
        return {'id':identity,'title':manifest.get('disc',{}).get('title',identity),'product':manifest.get('disc',{}).get('product'),'state':manifest.get('state','unavailable'),'sourceSetSHA256':manifest.get('sourceSetSHA256'),'executableSHA256':manifest.get('executable',{}).get('sha256'),'evidence':manifest.get('evidence',{}),'missingProfileFields':missing,'url':'/projects/'+identity+'/','browserReady':(project/'.local/browser/game.js').is_file() and (project/'.local/browser/build.json').is_file(),'artifactCount':len(artifacts)}
    def list(self):return [self.describe(e['id']) for e in self.entries()]

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',default=str(DEFAULT));sub=parser.add_subparsers(dest='command',required=True)
    add=sub.add_parser('add');add.add_argument('--project',required=True);add.add_argument('--id')
    sub.add_parser('list')
    snap=sub.add_parser('snapshot');snap.add_argument('--project',required=True);snap.add_argument('--stage',choices=['prepare','translate','build','build-browser','run'],required=True)
    args=parser.parse_args();ws=Workspace(args.workspace)
    try:
        result=ws.add(args.project,args.id) if args.command=='add' else record(args.project,args.stage,message='Recorded existing output; runtime behavior is not newly verified.') if args.command=='snapshot' else ws.list()
        print(json.dumps(result,indent=2))
    except (OSError,ValueError,KeyError) as error:parser.exit(2,str(error)+'\n')
