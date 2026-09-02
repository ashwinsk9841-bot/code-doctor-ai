"""
Visual atmosphere for Code Doctor AI.

Provides the dark/gold rain animation, the clickable Code Doctor buddy with
cursor-following eyes, and global theme CSS. The heavy lifting is client-side
HTML/CSS/JS; Python only injects the block and exposes a helper to open the
buddy's status panel.
"""

# ---------------------------------------------------------------------------
# Global theme CSS
# ---------------------------------------------------------------------------
THEME_CSS = """
:root{
  --cd-bg:#050507;
  --cd-bg-2:#0b0b10;
  --cd-panel:#0e0e15;
  --cd-gold:#d4af37;
  --cd-gold-2:#f5d061;
  --cd-text:#e8e6df;
  --cd-muted:#8a8794;
  --cd-line:#26262f;
}
html, body, .stApp{
  background:#050507 !important;
  color:var(--cd-text);
}
[data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stToolbar"]{
  background:transparent !important;
}
[data-testid="stHeader"]{background:rgba(5,5,7,0.5);}
.block-container{padding-top:1.2rem;padding-bottom:4rem;max-width:1200px;}
h1,h2,h3,h4{color:var(--cd-gold-2);letter-spacing:.3px;}
.stMarkdown{color:var(--cd-text);}
/* Cards / panels */
.cd-card{
  background:linear-gradient(160deg,#0e0e15 0%,#0a0a10 100%);
  border:1px solid var(--cd-line);
  border-radius:14px;
  padding:1.1rem 1.2rem;
  margin:.5rem 0;
  box-shadow:0 4px 18px rgba(0,0,0,.5);
}
.cd-glow{border:1px solid rgba(212,175,55,.35);box-shadow:0 0 22px rgba(212,175,55,.08);}
.cd-title{font-size:1.25rem;font-weight:700;color:var(--cd-gold-2);}
/* Buttons */
.stButton>button, .stDownloadButton>button{
  background:linear-gradient(180deg,#1a1a24,#12121a);
  color:var(--cd-gold-2);
  border:1px solid rgba(212,175,55,.4);
  border-radius:10px;
  font-weight:600;
  transition:.18s ease;
}
.stButton>button:hover{
  border-color:var(--cd-gold);
  box-shadow:0 0 16px rgba(212,175,55,.25);
  background:linear-gradient(180deg,#222230,#16161f);
}
.stButton>button[kind="primary"]{
  background:linear-gradient(180deg,var(--cd-gold-2),var(--cd-gold));
  color:#1a1200 !important;
  border:none;
}
/* Inputs */
.stTextInput input,.stTextArea textarea,.stSelectbox>div>div{
  background:#0b0b12 !important;
  border:1px solid var(--cd-line) !important;
  color:var(--cd-text) !important;
  border-radius:10px;
}
/* Metrics */
[data-testid="stMetricValue"]{color:var(--cd-gold-2);font-weight:700;}
[data-testid="stMetricLabel"]{color:var(--cd-muted);}
/* Tabs */
.stTabs [data-baseweb="tab"]{color:var(--cd-muted);}
.stTabs [aria-selected="true"]{color:var(--cd-gold-2);}
/* Expander */
.streamlit-expanderHeader{color:var(--cd-text);}
/* Code blocks */
.stCode,.stCode pre{
  background:#0a0a10 !important;
  border:1px solid var(--cd-line);
  border-radius:10px;
}
/* Sidebar */
[data-testid="stSidebar"]{background:#08080c;border-right:1px solid var(--cd-line);}
/* Scrollbars */
::-webkit-scrollbar{width:10px;height:10px;}
::-webkit-scrollbar-track{background:#07070a;}
::-webkit-scrollbar-thumb{background:#2a2a35;border-radius:6px;}
::-webkit-scrollbar-thumb:hover{background:#3a3a48;}

/* Buddy */
.cd-buddy-wrap{position:fixed;right:22px;bottom:22px;z-index:60;display:flex;flex-direction:column;align-items:center;cursor:pointer;user-select:none;-webkit-user-select:none;}
.cd-buddy{width:78px;height:78px;border-radius:50%;transition:transform .25s cubic-bezier(.2,.8,.3,1);}
.cd-buddy:hover{transform:scale(1.08) }
.cd-buddy.clicked{animation:cd-pulse .5s ease;}
@keyframes cd-pulse{0%{transform:scale(1)}30%{transform:scale(.92)}60%{transform:scale(1.06)}100%{transform:scale(1)}}
.cd-buddy-tip{color:#cfcbbf;font-size:.72rem;background:rgba(14,14,21,.85);border:1px solid var(--cd-line);border-radius:8px;padding:3px 8px;margin-top:6px;white-space:nowrap;opacity:0;transition:opacity .2s;}
.cd-buddy-wrap:hover .cd-buddy-tip{opacity:1;}

/* Assistant panel */
.cd-panel{
  position:fixed;right:22px;bottom:112px;width:300px;max-height:420px;z-index:70;
  background:#0c0c13;border:1px solid rgba(212,175,55,.35);border-radius:14px;
  padding:14px;box-shadow:0 10px 34px rgba(0,0,0,.6);
  transform:translateY(12px);opacity:0;pointer-events:none;transition:.22s ease;
  display:flex;flex-direction:column;font-size:.9rem;
}
.cd-panel.open{transform:none;opacity:1;pointer-events:auto;}
.cd-panel .cd-p-head{font-weight:700;color:var(--cd-gold-2);margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;}
.cd-panel .cd-p-close{background:none;border:none;color:var(--cd-muted);font-size:1.1rem;cursor:pointer;}
.cd-panel .cd-p-body{color:var(--cd-text);overflow-y:auto;line-height:1.5;}
.cd-panel .cd-p-foot{margin-top:10px;color:var(--cd-muted);font-size:.74rem;border-top:1px solid var(--cd-line);padding-top:6px;}

/* Code Doctor logo */ 
.cd-logo{font-size:1.9rem;font-weight:800;color:var(--cd-gold-2);letter-spacing:-.5px;}
.cd-logo span{color:var(--cd-muted);}

@media (prefers-reduced-motion: reduce){
  .cd-buddy,.cd-buddy:hover{transition:none;transform:none;}
  .cd-panel{transition:none;}
}
"""

# ---------------------------------------------------------------------------
# Rain + buddy + cursor eyes (client-side)
# ---------------------------------------------------------------------------
RAIN_JS = r"""
<script>
/* Code Doctor AI visual atmosphere */
(function(){
  var REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- RAIN CANVAS ---------- */
  var rainc = document.createElement('canvas');
  rainc.id='cd-rain';
  rainc.style.cssText='position:fixed;top:0;left:0;width:100vw;height:100vh;z-index:1;pointer-events:none;opacity:.55;';
  document.body.appendChild(rainc);
  var ctxR = rainc.getContext('2d');
  var DPR = window.devicePixelRatio||1;
  var W,H,drops,ndrops,cnt;
  function sizeRain(){
    W=rainc.width=Math.floor(window.innerWidth*DPR);
    H=rainc.height=Math.floor(window.innerHeight*DPR);
    ctxR.setTransform(DPR,0,0,DPR,0,0);
    ndrops=Math.min(140,Math.floor(window.innerWidth/11));
    drops=[];
    for(var i=0;i<ndrops;i++){drops.push({x:Math.random()*window.innerWidth,y:Math.random()*window.innerHeight,len:14+Math.random()*14,speed:0.55+Math.random()*0.75});}
    cnt=0;
  }
  function drawRain(){
    if(REDUCED){return;}
    ctxR.clearRect(0,0,window.innerWidth,window.innerHeight);
    ctxR.strokeStyle='rgba(212,175,55,0.5)';
    ctxR.lineWidth=1;
    ctxR.lineCap='round';
    for(var i=0;i<ndrops;i++){
      var d=drops[i];
      d.y+=d.speed;
      if(d.y>window.innerHeight+20){d.y=-20;d.x=Math.random()*window.innerWidth;}
      ctxR.beginPath();
      ctxR.moveTo(d.x,d.y);
      ctxR.lineTo(d.x-2+(d.x%7),d.y-d.len);
      ctxR.stroke();
    }
    cnt++;
    requestAnimationFrame(drawRain);
  }
  sizeRain();
  window.addEventListener('resize',sizeRain);
  if(!REDUCED){requestAnimationFrame(drawRain);}

  /* ---------- BUDDY + CURSOR EYES ---------- */
  var wrap=document.createElement('div');
  wrap.className='cd-buddy-wrap';
  wrap.innerHTML=
    '<svg class="cd-buddy" viewBox="0 0 100 100" aria-hidden="true">'+
      '<circle cx="50" cy="50" r="46" fill="#101018" stroke="#d4af37" stroke-width="2.5"/>'+
      '<circle cx="50" cy="50" r="44" fill="url(#cd-bg-g)" opacity="0.5"/>'+
      '<defs><radialGradient id="cd-bg-g" cx="50%" cy="30%" r="70%">'+
        '<stop offset="0%" stop-color="#222233"/><stop offset="100%" stop-color="#0a0a10"/>'+
      '</radialGradient></defs>'+
      '<path d="M50 20 a26 26 0 0 1 0 52" opacity="0" />'+
      '<rect x="24" y="40" width="19" height="24" rx="9" fill="#f5f0e0"/>'+
      '<rect x="57" y="40" width="19" height="24" rx="9" fill="#f5f0e0"/>'+
      '<circle class="cd-pupil" data-e="L" cx="33.5" cy="52" r="6.5" fill="#1a1a22"/>'+
      '<circle class="cd-pupil" data-e="R" cx="66.5" cy="52" r="6.5" fill="#1a1a22"/>'+
      '<circle cx="33.5" cy="54" r="2" fill="#fff"/><circle cx="66.5" cy="54" r="2" fill="#fff"/>'+
      '<path d="M38 72 Q50 82 62 72" stroke="#d4af37" stroke-width="2.6" fill="none" stroke-linecap="round"/>'+
      '<path d="M40 66 c3 2 5 2 8 0" stroke="#0a0a10" stroke-width="1.4" fill="none"/>'+
    '</svg>'+
    '<div class="cd-buddy-tip">Code Doctor — click me</div>'+
    '<div class="cd-panel" id="cd-panel">'+
      '<div class="cd-p-head"><span>🩺 Code Doctor AI</span><button class="cd-p-close" id="cd-close">✕</button></div>'+
      '<div class="cd-p-body" id="cd-p-body">Loading status…</div>'+
      '<div class="cd-p-foot">Client-side visual only. Nothing is tracked.</div>'+
    '</div>';
  document.body.appendChild(wrap);

  var pupils=[wrap.querySelector('[data-e="L"]'),wrap.querySelector('[data-e="R"]')];
  function moveEyes(){
    if(REDUCED){return;}
    var r=wrap.getBoundingClientRect();
    var cx=r.left+r.width/2, cy=r.top+r.height/2;
    var dx= (window.cursorX||cx) - cx, dy=(window.cursorY||cy) - cy;
    var ang=Math.atan2(dy,dx);
    var dist=Math.min(4.5,Math.hypot(dx,dy)*0.02);
    pupils.forEach(function(p){ p.setAttribute('transform','translate('+(Math.cos(ang)*dist)+','+(Math.sin(ang)*dist)+')'); });
    requestAnimationFrame(moveEyes);
  }
  window.addEventListener('mousemove',function(e){window.cursorX=e.clientX;window.cursorY=e.clientY;},false);
  if(!REDUCED){requestAnimationFrame(moveEyes);}

  /* Click reaction */
  wrap.addEventListener('click',function(e){
    if(e.target.id==='cd-close'){return;}
    var b=wrap.querySelector('.cd-buddy');
    b.classList.remove('clicked'); void b.offsetWidth; b.classList.add('clicked');
    var panel=document.getElementById('cd-panel');
    panel.classList.toggle('open');
  });
  document.getElementById('cd-close').addEventListener('click',function(e){
    e.stopPropagation();
    document.getElementById('cd-panel').classList.remove('open');
  });
})();
</script>
"""

# Python-side helper functions are in this module's functions below.


def inject_visuals(backend_status: str = "Ready. Paste a GitHub repository URL to begin.", status_kind: str = "ready"):
    """Return the HTML block to inject (rain + buddy + eyes + theme)."""
    panel_body = _buddy_panel_body(backend_status, status_kind)
    panel_js = "<script>window.__cdStatus=" + _js_str(panel_body) + ";</script>"
    html = (
        "<style>" + THEME_CSS + "</style>"
        + panel_js
        + RAIN_JS
        + "<script>try{var pb=document.getElementById('cd-p-body');if(pb)pb.textContent=window.__cdStatus;}catch(e){}</script>"
    )
    return html


def _buddy_panel_body(backend_status: str, status_kind: str) -> str:
    if status_kind == "scanning":
        return f"Scanning in progress… {backend_status}"
    if status_kind == "scan_complete":
        return f"Scan complete. {backend_status}"
    if status_kind == "error":
        return f"Something went wrong: {backend_status}"
    return backend_status


def _js_str(s: str) -> str:
    import json
    return json.dumps(s)
