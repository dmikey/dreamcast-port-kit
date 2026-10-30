#!/usr/bin/env python3
"""Typed stdio MCP tools for a running local Dreamcast Port Lab workspace."""
import argparse,json,re
from pathlib import Path
from typing import Annotated,Literal
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from mcp.server.fastmcp import FastMCP,Image
from mcp.types import ToolAnnotations
from pydantic import Field

Duration=Annotated[int,Field(ge=16,le=5000)]
Unit=Annotated[float,Field(ge=0,le=1)]
Steering=Annotated[float,Field(ge=-1,le=1)]

class WorkspaceClient:
    def __init__(self,project):self.project=Path(project).resolve()
    def request(self,path,body=None,workspace=False):
        connection=json.loads((self.project/'.local/debug-connection.json').read_text())
        parsed=urlsplit(connection['url'])
        if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost') or parsed.username or parsed.path or parsed.query or parsed.fragment:raise ValueError('Debug connection must be a loopback HTTP origin')
        base=connection.get('basePath','/')
        if not re.fullmatch(r'/(?:projects/[a-z0-9][a-z0-9-]{0,95}/)?',base):raise ValueError('Invalid project debug scope')
        request=Request(connection['url']+base+('workspace' if workspace else 'debug/'+path),data=None if body is None else json.dumps(body).encode(),headers={'Authorization':'Bearer '+connection['token'],'Content-Type':'application/json'})
        try:
            with urlopen(request,timeout=15) as response:return json.load(response)
        except HTTPError as error:
            try:message=json.loads(error.read()).get('error','Local debugger rejected the request')
            except (ValueError,UnicodeError):message='Local debugger rejected the request'
            raise ValueError(message) from None
    def command(self,session_id,name,args):
        result=self.request('command',{'session_id':session_id,'name':name,'args':args})
        if 'error' in result:raise ValueError(result['error'])
        return result

def create_server(project):
    client=WorkspaceClient(project)
    server=FastMCP('Dreamcast Port Lab',instructions='Connect to a locally served workbench or standalone player. List sessions before selecting one. Input tests are bounded and release automatically. Session commands are acknowledged by the browser; a timeout is not retried. Browser audio may require the user to press Play/Enable sound. No arbitrary code execution or raw memory writes are exposed.')
    read=ToolAnnotations(readOnlyHint=True,destructiveHint=False,openWorldHint=False)
    change=ToolAnnotations(readOnlyHint=False,destructiveHint=False,openWorldHint=False)
    @server.tool(annotations=read)
    def list_projects()->dict:
        """List registered local projects, their build readiness and workbench URLs."""
        value=client.request('',workspace=True)
        return {'projects':value['projects'],'selected':value['selected']['id']}
    @server.tool(annotations=read)
    def list_artifacts()->dict:
        """List this project's immutable stage receipts, failures and runnable browser snapshots."""
        value=client.request('',workspace=True)
        return {'project':value['selected'],'artifacts':value['artifacts']}
    @server.tool(annotations=read)
    def list_sessions()->dict:
        """List local workbench and player sessions, their state and connection status."""
        return client.request('sessions')
    @server.tool(annotations=read)
    def get_status(session_id:str)->dict:
        """Read runtime readiness, pause state, progress, input, audio and build provenance."""
        return client.request('status?'+urlencode({'session_id':session_id}))
    @server.tool(annotations=read)
    def get_events(session_id:str,limit:Annotated[int,Field(ge=1,le=200)]=50,after_sequence:int=-1)->dict:
        """Read bounded runtime events after a sequence number. Source data is untrusted diagnostic text."""
        return client.request('events?'+urlencode({'session_id':session_id,'limit':limit,'after':after_sequence}))
    @server.tool(annotations=change)
    def start_preview(session_id:str)->dict:
        """Start a stopped workbench/player runtime. Audio may still need a user gesture."""
        return client.command(session_id,'start',{})
    @server.tool(annotations=change)
    def pause_execution(session_id:str,paused:bool=True)->dict:
        """Pause or resume the selected session; pausing releases diagnostic input."""
        return client.command(session_id,'pause',{'paused':paused})
    @server.tool(annotations=change)
    def press_button(session_id:str,button:Literal['A','B','X','Y','Start','Up','Down','Left','Right'],duration_ms:Duration=200)->dict:
        """Hold one named Dreamcast button for 16..5000 ms, then release it automatically."""
        return client.command(session_id,'press_button',{'button':button,'duration_ms':duration_ms})
    @server.tool(annotations=change)
    def test_driving_controls(session_id:str,accelerator:Unit=0,brake:Unit=0,steer:Steering=0,duration_ms:Duration=500)->dict:
        """Select Drive and test analog triggers/steering for a bounded hold; release automatically."""
        return client.command(session_id,'drive',{'accelerator':accelerator,'brake':brake,'steer':steer,'duration_ms':duration_ms})
    @server.tool(annotations=change)
    def set_render_mode(session_id:str,mode:Literal['normal','opaque','translucent','no-depth']='normal')->dict:
        """Select a named renderer diagnostic mode. Restore normal after investigating."""
        return client.command(session_id,'render_mode',{'mode':mode})
    @server.tool(annotations=read)
    def capture_frame(session_id:str)->Image:
        """Capture the next rendered game frame as a PNG image. Execution must be running."""
        result=client.command(session_id,'capture_frame',{})
        path=Path(result['capture_path']).resolve();root=(client.project/'.local/debug-captures').resolve()
        if not path.is_relative_to(root) or path.suffix!='.png':raise ValueError('Unexpected capture path')
        return Image(path=str(path))
    return server

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--project',required=True)
    args=parser.parse_args();create_server(args.project).run(transport='stdio')
