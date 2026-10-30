'use strict';
const portVmuUI={
 card:null,files:[],selected:null,refreshTimer:null,
 event(data){
  if(data.kind==='vmu-lcd'){
   const bytes=new Uint8Array(data.bytes);if(bytes.length!==192)return;
   const canvas=document.getElementById('vmu-lcd'),ctx=canvas.getContext('2d');
   ctx.fillStyle='#a7b993';ctx.fillRect(0,0,48,32);ctx.fillStyle='#26382b';
   // Controller-view rows run bottom to top. Keep decoded columns left to right.
   for(let y=0;y<32;y++)for(let x=0;x<48;x++)if(bytes[y*6+5-(x>>3)]&(1<<(x&7)))ctx.fillRect(x,31-y,1,1);
  }else{
   document.getElementById('vmu-message').textContent=data.error||data.message;document.getElementById('vmu-message').dataset.error=String(!!data.error);
   if(data.saved&&this.refreshTimer===null)this.refreshTimer=setTimeout(()=>{this.refreshTimer=null;this.refresh();},400);
  }
 },
 active(){return ['loading','running','paused'].includes(document.body.dataset.runtime);},
 guard(){if(this.active())throw Error('Stop the game before changing saves. Use “Stop game to manage saves”.');},
 state(){const active=this.active();for(const button of document.querySelectorAll('[data-vmu-edit]'))button.disabled=active;document.getElementById('vmu-stop').hidden=!active;},
 message(text,error=false){const node=document.getElementById('vmu-manager-message');node.textContent=text;node.dataset.error=String(error);},
 async run(action){try{await action();}catch(error){this.message(error.message,true);}},
 download(bytes,name){const url=URL.createObjectURL(new Blob([bytes],{type:'application/octet-stream'})),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);},
 async status(){const card=await portVmuStorage.read(),info=portVmuFormat.inspect(card.bytes);return {storage:'browser-indexeddb',project:card.id,cardName:card.name,revision:card.revision,updatedAt:card.updatedAt,...info,files:info.files.map(({hex,...file})=>file)};},
 async refresh(){
  try{
   this.card=await portVmuStorage.read();const info=portVmuFormat.inspect(this.card.bytes);this.files=info.files;
   document.getElementById('vmu-free').textContent=info.formatted?String(info.freeBlocks):'Unformatted';document.getElementById('vmu-revision').textContent=String(this.card.revision);document.getElementById('vmu-card-name').value=this.card.name;
   const list=document.getElementById('vmu-files');list.replaceChildren();
   if(!info.files.length)list.textContent=info.error||'No saves on this card.';
   for(const file of info.files){const button=document.createElement('button');button.type='button';button.className='vmu-file';button.textContent=file.name+' · '+file.blocks+' blocks';button.setAttribute('aria-pressed',String(file.index===this.selected));button.addEventListener('click',()=>this.select(file.index));list.append(button);}
   const history=await portVmuStorage.history(),select=document.getElementById('vmu-history');select.replaceChildren();
   if(!history.length){const option=document.createElement('option');option.value='';option.textContent='No previous versions';select.append(option);}
   for(const backup of history){const option=document.createElement('option');option.value=backup.id;option.textContent='Rev '+backup.revision+' · '+backup.reason+' · '+new Date(backup.updatedAt).toLocaleString();select.append(option);}
   this.select(this.selected);this.state();this.message(info.error||'Browser card ready. '+info.files.length+' saved file'+(info.files.length===1?'':'s')+'.',!!info.error);
  }catch(error){this.message(error.message,true);}
 },
 select(index){
  const file=this.files.find(f=>f.index===index);this.selected=file?.index??null;const detail=document.getElementById('vmu-file-detail');detail.hidden=!file;if(!file)return;
  document.getElementById('vmu-filename').value=file.name;
  const info=document.getElementById('vmu-file-info');info.replaceChildren();
  for(const [label,value] of [['Type',file.type],['Size',file.bytes+' bytes'],['Description',file.description||'—'],['Details',file.detail||'—'],['Application',file.application||'—'],['Copy flag',file.protected?'Protected':'Allowed'],['Blocks',file.allocation.join(', ')]]){const row=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;row.append(dt,dd);info.append(row);}
  const words=file.hex.split(' '),lines=[];for(let i=0;i<words.length;i+=16)lines.push(i.toString(16).padStart(4,'0')+'  '+words.slice(i,i+16).join(' '));document.getElementById('vmu-hex').textContent=lines.join('\n');
  for(const button of document.querySelectorAll('.vmu-file'))button.setAttribute('aria-pressed',String(button.textContent.startsWith(file.name+' · ')));
 },
 async edit(action,index=this.selected,name){this.guard();if(!this.card)await this.refresh();await portVmuStorage.edit(action,index,name,this.card.revision);await this.refresh();this.message(action==='delete'?'Save deleted. Restore its previous card in Recovery.':action==='copy'?'Save copied.':'Save renamed.');return this.status();},
 async build(){try{const response=await fetch('build.json');if(!response.ok)return;const info=await response.json();document.getElementById('vmu-build-note').textContent=info.features?.vmu?'A1 storage, LCD and clock. VMU buzzer and standalone VMU games are not implemented.':'This build predates VMU support. Rebuild to connect A1.';}catch{}}
};
document.getElementById('tab-vmu').addEventListener('click',()=>{portVmuUI.refresh();portVmuUI.build();});
document.getElementById('vmu-refresh').addEventListener('click',()=>portVmuUI.refresh());
document.getElementById('vmu-stop').addEventListener('click',()=>{sessionStorage.setItem('portlab-vmu-manage','1');location.reload();});
document.getElementById('vmu-card-rename').addEventListener('click',()=>portVmuUI.run(async()=>{portVmuUI.guard();await portVmuStorage.rename(document.getElementById('vmu-card-name').value,portVmuUI.card.revision);await portVmuUI.refresh();}));
document.getElementById('vmu-export').addEventListener('click',()=>portVmuUI.run(async()=>{const card=await portVmuStorage.read();portVmuUI.download(card.bytes,'vmu-a1.bin');}));
document.getElementById('vmu-import').addEventListener('click',()=>document.getElementById('vmu-import-file').click());
document.getElementById('vmu-import-file').addEventListener('change',event=>portVmuUI.run(async()=>{portVmuUI.guard();const file=event.target.files[0];if(!file)return;await portVmuStorage.replace(new Uint8Array(await file.arrayBuffer()),portVmuUI.card.revision);event.target.value='';await portVmuUI.refresh();portVmuUI.message('Card imported. The previous card is in Recovery.');}));
for(const action of ['rename','copy','delete'])document.getElementById('vmu-file-'+action).addEventListener('click',()=>portVmuUI.run(()=>portVmuUI.edit(action,portVmuUI.selected,action==='rename'?document.getElementById('vmu-filename').value:undefined)));
document.getElementById('vmu-file-export').addEventListener('click',()=>portVmuUI.run(async()=>{const card=await portVmuStorage.read(),file=portVmuUI.files.find(f=>f.index===portVmuUI.selected);if(file)portVmuUI.download(portVmuFormat.exportFile(card.bytes,file.index),file.name+'.vms');}));
document.getElementById('vmu-restore').addEventListener('click',()=>portVmuUI.run(async()=>{portVmuUI.guard();await portVmuStorage.restore(document.getElementById('vmu-history').value,portVmuUI.card.revision);await portVmuUI.refresh();portVmuUI.message('Previous card restored. The replaced card is also in Recovery.');}));
document.getElementById('vmu-clear').addEventListener('click',()=>portVmuUI.run(async()=>{portVmuUI.guard();await portVmuStorage.clear(portVmuUI.card.revision);portVmuUI.selected=null;await portVmuUI.refresh();portVmuUI.message('Card cleared. Restore its previous contents in Recovery.');}));
const vmuContext=document.getElementById('vmu-lcd').getContext('2d');vmuContext.fillStyle='#a7b993';vmuContext.fillRect(0,0,48,32);
if(typeof sessionStorage!=='undefined'&&sessionStorage.getItem('portlab-vmu-manage')){sessionStorage.removeItem('portlab-vmu-manage');document.getElementById('tab-vmu').click();}
