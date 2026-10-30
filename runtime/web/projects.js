/* Project metadata and immutable artifacts; never inserts disc text as HTML. */
'use strict';
const projectUI={
 node(tag,text,className){const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text);if(className)n.className=className;return n;},
 async refresh(){
  const status=document.getElementById('project-artifact-status');
  try{
   const response=await fetch('workspace');if(!response.ok)throw Error('Project service unavailable');const data=await response.json();this.data=data;
   const select=document.getElementById('project-select');select.replaceChildren();
   for(const p of data.projects){const option=this.node('option',p.title);option.value=p.url;option.selected=p.id===data.selected.id;select.append(option);}
   const p=data.selected;status.textContent=p.state.replaceAll('-',' ')+' · '+data.artifacts.length+' artifact'+(data.artifacts.length===1?'':'s');
   document.getElementById('game-title').textContent=p.title;
   const evidence=document.getElementById('project-evidence');evidence.replaceChildren();
   for(const [name,key] of [['Imported','discRead'],['Translated','translated'],['Compiled','compiled'],['Menu','bootedToMenu'],['Playable','browserPlayable']]){const badge=this.node('span',(p.evidence[key]?'✓ ':'○ ')+name);badge.dataset.verified=String(!!p.evidence[key]);evidence.append(badge);}
   const noBuild=document.body.dataset.buildReady==='false';document.getElementById('project-empty').hidden=!noBuild;
   if(noBuild){document.getElementById('start').hidden=true;document.getElementById('open-player').hidden=true;document.getElementById('session-label').textContent='Not built';document.getElementById('project-next-stage').textContent=p.missingProfileFields.length?'This executable needs a verified title profile before it can be built. Import details and attempted stages are available in Artifacts.':'Run the browser build stage to create a playable artifact.';}
   const list=document.getElementById('artifact-list');list.replaceChildren();
   if(!data.artifacts.length)list.append(this.node('p','No saved artifacts yet. Each CLI import, translation, build or run records a receipt here.','tool-note'));
   for(const a of data.artifacts){
    const base=p.url+'artifacts/'+encodeURIComponent(a.id)+'/',card=this.node('article',undefined,'artifact-card');card.dataset.status=a.status;
    const head=this.node('div',undefined,'artifact-heading');head.append(this.node('strong',({'prepare':'Disc import','translate':'Translation','build':'Native build','build-browser':'Browser build','run':'Runtime test'})[a.stage]||a.stage),this.node('span',a.status,'artifact-status'));card.append(head);
    const date=this.node('time',new Date(a.createdAt).toLocaleString());date.dateTime=a.createdAt;card.append(date,this.node('p',a.id,'artifact-id'));
    if(data.selectedArtifact===a.id)card.append(this.node('span','Viewing this build','artifact-selected'));
    if(a.build)card.append(this.node('p',(a.build.optimization||a.build.target||'Build')+(a.build.wasmSHA256?' · '+a.build.wasmSHA256.slice(0,12):''),'tool-note'));
    card.append(this.node('p',a.message,'artifact-message'));
    const actions=this.node('div',undefined,'artifact-actions');
    const receipt=this.node('a','Receipt ↗');receipt.href=base+'receipt.json';receipt.target='_blank';receipt.rel='noopener';actions.append(receipt);
    if(a.runnable){const open=this.node('a','Open build ↗');open.href=base;open.target='_blank';open.rel='noopener';actions.append(open);}
    const log=a.files.find(f=>f.name==='output.log');if(log){const link=this.node('a','Output log ↗');link.href=base+'output.log';link.target='_blank';link.rel='noopener';actions.append(link);}
    card.append(actions);
    const files=this.node('details'),summary=this.node('summary',a.files.length+' files · '+this.bytes(a.files.reduce((n,f)=>n+f.bytes,0)));files.append(summary);
    for(const file of a.files){const row=this.node('a',file.name+' · '+this.bytes(file.bytes),'artifact-file');row.href=base+'files/'+file.name.split('/').map(encodeURIComponent).join('/');row.title='SHA256 '+file.sha256;row.download='';files.append(row);}
    card.append(files);list.append(card);
   }
  }catch(error){status.textContent=error.message;const select=document.getElementById('project-select');select.replaceChildren(this.node('option','Projects unavailable'));}
 },
 bytes(n){return n>=1048576?(n/1048576).toFixed(1)+' MB':n>=1024?(n/1024).toFixed(1)+' KB':n+' B';}
};
document.getElementById('project-select').addEventListener('change',event=>{location.href=event.target.value;});
document.getElementById('refresh-artifacts').addEventListener('click',()=>projectUI.refresh());
document.getElementById('show-artifacts').addEventListener('click',()=>document.getElementById('tab-artifacts').click());
projectUI.refresh();
