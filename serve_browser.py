"""Loopback-only browser runtime and bounded, same-origin source-disc chunks."""
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
import argparse,json

def serve(args):
    project=Path(args.project).resolve();root=project/'.local/browser'
    tracks=json.loads((project/'.local/source-lock.json').read_text())['tracks']
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            url=urlsplit(self.path)
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
    print(f'Browser game: http://127.0.0.1:{args.port}/',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',required=True);p.add_argument('--port',type=int,default=4390);serve(p.parse_args())
