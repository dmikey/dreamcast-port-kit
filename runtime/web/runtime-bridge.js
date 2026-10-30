/* DOM stays responsive while WebAssembly and OffscreenCanvas run in a worker. */
class PortWorkerRuntime {
 constructor(canvas,callbacks){this.canvas=canvas;this.callbacks=callbacks;this.worker=null;this.ready=false;this.bits=0;this.values=[0,0,0,0,0];this.lastSent='';}
 start(){
  if(this.worker)return;
  if(typeof Worker==='undefined'||typeof this.canvas.transferControlToOffscreen!=='function')throw new Error('This build requires Web Workers and WebGL OffscreenCanvas (Safari 17 or newer).');
  this.worker=new Worker('runtime-worker.js');
  this.worker.onmessage=event=>{const data=event.data;
   if(data.kind==='ready'){this.ready=true;this.callbacks.ready();this.flush(true);}
   else if(data.kind==='input-applied'){this.canvas.dataset.inputApplied=String(data.bits);if(data.bits)this.canvas.dataset.lastPressed=String(data.bits);}
   else if(data.kind==='logs'){for(const line of data.lines)this.callbacks.log(line);}
   else if(data.kind==='audio')this.callbacks.audio(data.samples);
   else if(data.kind==='error')this.callbacks.error(data.message);
  };
  this.worker.onerror=event=>this.callbacks.error(event.message||'Worker failed to load.');
  this.worker.onmessageerror=()=>this.callbacks.error('A worker message could not be decoded.');
  const canvas=this.canvas.transferControlToOffscreen();this.worker.postMessage({kind:'start',canvas},[canvas]);
 }
 button(bit,pressed){this.bits=pressed?this.bits|bit:this.bits&~bit;}
 axes(left,right,x,y){this.values=[this.bits,left,right,x,y];this.flush();}
 flush(force=false){const signature=this.values.join(',');if(!this.ready||(!force&&signature===this.lastSent))return;this.lastSent=signature;this.worker.postMessage({kind:'input',values:this.values.slice()});}
 capture(){if(this.worker&&this.ready)this.worker.postMessage({kind:'capture-render'});}
}
