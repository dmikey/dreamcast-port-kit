/* A page-owned intro: independent of game code and BIOS emulation. */
'use strict';
class PortBootIntro {
 constructor(stage){this.stage=stage;this.overlay=stage?.querySelector('.boot-intro');this.active=!!this.overlay;this.elapsed=false;this.runtimeReady=false;this.audio=null;}
 start(muted=false){
  if(!this.overlay)return;
  this.stage.dataset.booting='true';this.overlay.dataset.playing='true';
  const sound=this.stage.dataset.bootSound;
  if(sound&&typeof Audio!=='undefined'){
   this.audio=new Audio(sound);this.audio.volume=.65;this.audio.muted=muted;
   // Called directly from Start game so Safari can authorize playback.
   this.audio.play().catch(()=>{});
  }
  setTimeout(()=>{this.elapsed=true;this.finish();},8000);
 }
 ready(){this.runtimeReady=true;this.finish();}
 finish(){if(!this.elapsed||!this.runtimeReady||!this.overlay)return;this.active=false;this.stage.dataset.booting='false';this.overlay.hidden=true;if(this.audio){this.audio.pause();this.audio=null;}}
 fail(){if(!this.overlay)return;this.elapsed=true;this.runtimeReady=true;this.finish();}
}
