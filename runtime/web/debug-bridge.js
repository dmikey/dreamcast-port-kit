/* Versioned local debug transport. Typed tools never evaluate browser code. */
'use strict';
const portDebugBridge={token:null,session:null,lastSequence:-1,busy:false,frameWaiter:null,
 async request(path,body){const response=await fetch('debug/'+path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json',...(this.token?{Authorization:'Bearer '+this.token}:{})},...(body?{body:JSON.stringify(body)}:{})});if(!response.ok)throw new Error('Debug connection unavailable');return response.json();},
 async connect(){try{this.token=(await this.request('config')).token;this.session=(await this.request('register',{view:document.body.dataset.player==='true'?'player':'workbench'})).session_id;this.indicate('Connected');}catch{this.indicate('Offline');}},
 indicate(text){const node=document.getElementById('mcp-status');if(node)node.textContent=text;},
 frame(bytes){if(!this.frameWaiter)return false;const deliver=this.frameWaiter;this.frameWaiter=null;deliver(bytes);return true;},
 async tick(){if(this.busy)return;this.busy=true;try{if(!this.session){await this.connect();return;}if(typeof portDebugRuntime==='undefined')return;const events=portDebugRuntime.events(this.lastSequence,40);const reply=await this.request('poll',{session_id:this.session,state:portDebugRuntime.status(),events});if(events.length)this.lastSequence=events.at(-1).sequence;for(const cmd of reply.commands){let result;try{result=await portDebugRuntime.command(cmd.name,cmd.args);if(result?.frame){const frame=result.frame;delete result.frame;let binary='';const bytes=new Uint8Array(frame);for(let start=0;start<bytes.length;start+=16384)binary+=String.fromCharCode(...bytes.subarray(start,start+16384));result.png_base64=btoa(binary);}}catch(error){result={error:error.message||String(error)};}await this.request('complete',{session_id:this.session,id:cmd.id,result});}}catch{this.indicate('Reconnecting');this.session=null;this.lastSequence=-1;}finally{this.busy=false;}}
};
setInterval(()=>portDebugBridge.tick(),500);
portDebugBridge.connect();

window.addEventListener('pagehide',()=>{if(portDebugBridge.session)fetch('debug/disconnect',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json',Authorization:'Bearer '+portDebugBridge.token},body:JSON.stringify({session_id:portDebugBridge.session})}).catch(()=>{});});
