'use strict';
const status=document.querySelector('#status'),log=document.querySelector('#log');
const lines=[];
function output(...parts){const text=parts.join(' ');lines.push(text);if(lines.length>350)lines.shift();log.textContent=lines.join('\n');log.scrollTop=log.scrollHeight;console.log(text);if(text.includes('[DISPATCH] unresolved')||text.includes('[UNIMPLEMENTED]'))status.textContent='Execution stopped: '+text;if(text.includes('entering title code'))status.textContent='Running original game code. Title screen and driving unverified.';}
var Module={canvas:document.querySelector('#canvas'),print:output,printErr:output,setStatus:text=>{if(text)status.textContent=text;},onAbort:reason=>{status.textContent='Execution stopped. See runtime output.';output('Runtime aborted:',reason);}};
document.querySelector('#start').addEventListener('click',()=>{document.querySelector('#start').disabled=true;status.textContent='Loading browser runtime…';const script=document.createElement('script');script.src='game.js';document.body.append(script);Module.canvas.focus();});

for(const button of document.querySelectorAll('[data-bit]')) {
 button.addEventListener('pointerdown',event=>{event.preventDefault();if(Module._port_button){button.setPointerCapture(event.pointerId);Module._port_button(Number(button.dataset.bit),1);}});
 button.addEventListener('click',()=>{if(Module._port_button){const bit=Number(button.dataset.bit);Module._port_button(bit,1);output('[INPUT] button '+bit);setTimeout(()=>Module._port_button(bit,0),200);}});
 for(const name of ['pointerup','pointercancel'])button.addEventListener(name,event=>{if(Module._port_button)Module._port_button(Number(button.dataset.bit),0);});
}
window.addEventListener('error',event=>{status.textContent='Execution stopped. See runtime output.';output(event.message);});
