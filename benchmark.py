#!/usr/bin/env python3
"""Summarize local diagnostic exports; never treat unmatched scenes as a speedup."""
import argparse,json,re
from pathlib import Path

RENDER=re.compile(r'frames=(\d+) submit_avg_us=(\d+) submit_max_us=(\d+)')
FRAME=re.compile(r'\[FRAME\] (\d+) rendered')
def summarize(report):
    windows=[];previous=None;first_frame=None;last_frame=None;stops=[]
    for event in report.get('events',[]):
        message=event.get('message','');time=event.get('timeMs')
        if not isinstance(time,(float,int)):continue
        match=RENDER.search(message) if event.get('kind')=='RENDER' else None
        if match:
            frames,average,maximum=map(int,match.groups())
            duration=re.search(r"window_us=(\d+)",message)
            uploads=re.search(r"tex_uploads=(\d+)",message)
            gpu=re.search(r"tex_gpu_bytes=(\d+)",message)
            if previous is not None and time>previous:
                windows.append({'frames':frames,'seconds':int(duration[1])/1000000 if duration else (time-previous)/1000,'submitAverageUs':average,'submitMaxUs':maximum,'textureUploads':int(uploads[1]) if uploads else None,'gpuBytes':int(gpu[1]) if gpu else None})
            previous=time
        match=FRAME.search(message)
        if match:
            item=(time,int(match[1]));first_frame=first_frame or item;last_frame=item
        if 'unresolved call' in message or '[WATCHDOG]' in message:stops.append(message)
    seconds=sum(w['seconds'] for w in windows);frames=sum(w['frames'] for w in windows)
    interval=None
    if first_frame and last_frame and last_frame[0]>first_frame[0]:interval=(last_frame[1]-first_frame[1])*1000/(last_frame[0]-first_frame[0])
    return {'wasmSHA256':(report.get('build') or {}).get('wasmSHA256'),'optimization':(report.get('build') or {}).get('optimization'),'execution':report.get('execution'),'renderWindows':len(windows),'renderWindowSeconds':round(seconds,3),'submittedFramesPerSecond':round(frames/seconds,2) if seconds else None,'frameEventIntervalFPS':round(interval,2) if interval is not None else None,'submitAverageUs':round(sum(w['frames']*w['submitAverageUs'] for w in windows)/frames) if frames else None,'submitMaxUs':max((w['submitMaxUs'] for w in windows),default=None),'textureUploads':sum(w['textureUploads'] for w in windows if w['textureUploads'] is not None) if any(w['textureUploads'] is not None for w in windows) else None,'textureGpuBytesMax':max((w['gpuBytes'] for w in windows if w['gpuBytes'] is not None),default=None),'eventsDropped':report.get('eventsDropped',0),'audio':report.get('audio'),'executionStops':stops,'limits':'Submitted frames and CPU submission timings, not GPU completion or displayed frames. Static screens may submit fewer frames. Unmatched scenes/devices are not a comparative benchmark.'}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('diagnostics',type=Path,nargs='+');args=parser.parse_args()
    for path in args.diagnostics:
        print(json.dumps({'report':path.name,**summarize(json.loads(path.read_text()))},indent=2))
if __name__=='__main__':main()
