import os
import requests
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Music API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPSTREAM = "https://music-downoader-api.froxtdevil.workers.dev/search"


@app.get("/api/search")
def search(song: str = Query(..., description="Song name")):
    try:
        r = requests.get(UPSTREAM, params={"song": song}, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream error: {e}")


@app.get("/api/download")
def download(song: str, index: int = 0, quality: str = "320"):
    data = search(song)
    results = data.get("results", [])
    if not results:
        raise HTTPException(status_code=404, detail="No results")
    if index < 0 or index >= len(results):
        raise HTTPException(status_code=404, detail="Index out of range")
    urls = results[index].get("download_urls", {}) or {}
    url = urls.get(quality) or results[index].get("download_url")
    if not url:
        raise HTTPException(status_code=404, detail="Download URL not found")
    return RedirectResponse(url)


HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🎵 Music Search</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:system-ui,sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);min-height:100vh;padding:20px;color:#333}
  .container{max-width:800px;margin:0 auto}
  h1{color:#fff;text-align:center;margin-bottom:20px;font-size:2em}
  .search-box{display:flex;gap:10px;margin-bottom:20px}
  input{flex:1;padding:14px;border-radius:8px;border:none;font-size:16px}
  button{padding:14px 24px;border-radius:8px;border:none;background:#ff6b6b;color:#fff;font-size:16px;font-weight:bold;cursor:pointer}
  button:hover{background:#ee5a52}
  button:disabled{opacity:.5;cursor:not-allowed}
  .result{background:#fff;border-radius:10px;padding:15px;margin-bottom:12px;display:flex;gap:15px;box-shadow:0 2px 10px rgba(0,0,0,.1)}
  .result img{width:80px;height:80px;border-radius:8px;object-fit:cover;flex-shrink:0}
  .info{flex:1;min-width:0}
  .title{font-weight:bold;margin-bottom:4px}
  .meta{font-size:13px;color:#666;margin-bottom:8px}
  .actions{display:flex;gap:6px;flex-wrap:wrap}
  .actions a{padding:6px 12px;background:#667eea;color:#fff;text-decoration:none;border-radius:6px;font-size:12px;font-weight:bold}
  .actions a:hover{background:#5568d3}
  .actions a.q320{background:#2ecc71}
  .actions a.q320:hover{background:#27ae60}
  .status{color:#fff;text-align:center;padding:20px}
  .error{color:#fff;background:rgba(255,0,0,.4);padding:10px;border-radius:8px;margin-bottom:15px}
</style>
</head>
<body>
<div class="container">
  <h1>🎵 Music Search & Download</h1>
  <form class="search-box" onsubmit="doSearch(event)">
    <input id="q" placeholder="Song name (e.g. Saree Se Tadi)" autofocus>
    <button type="submit" id="btn">Search</button>
  </form>
  <div id="status"></div>
  <div id="results"></div>
</div>
<script>
const $=id=>document.getElementById(id);
async function doSearch(e){
  e.preventDefault();
  const q=$('q').value.trim();
  if(!q)return;
  $('btn').disabled=true;
  $('status').innerHTML='<div class="status">Searching...</div>';
  $('results').innerHTML='';
  try{
    const r=await fetch('/api/search?song='+encodeURIComponent(q));
    const data=await r.json();
    if(!r.ok)throw new Error(data.detail||'Error');
    render(data,q);
  }catch(err){
    $('status').innerHTML='<div class="error">❌ '+err.message+'</div>';
  }finally{
    $('btn').disabled=false;
  }
}
function render(data,query){
  const results=data.results||[];
  $('status').innerHTML='';
  if(results.length===0){
    $('status').innerHTML='<div class="status">No results found</div>';
    return;
  }
  $('status').innerHTML='<div class="status">Found '+(data.total||results.length)+' songs</div>';
  $('results').innerHTML=results.map((s,i)=>{
    const urls=s.download_urls||{};
    const dl=q=>'/api/download?song='+encodeURIComponent(query)+'&index='+i+'&quality='+q;
    const actions=[];
    if(urls['320'])actions.push('<a href="'+dl('320')+'" class="q320">⬇ 320kbps</a>');
    if(urls['160'])actions.push('<a href="'+dl('160')+'">⬇ 160kbps</a>');
    if(urls['96'])actions.push('<a href="'+dl('96')+'">⬇ 96kbps</a>');
    return '<div class="result">'+
      '<img src="'+(s.image||'')+'" onerror="this.style.display=\\'none\\'">'+
      '<div class="info">'+
        '<div class="title">'+esc(s.title)+'</div>'+
        '<div class="meta">'+esc(s.subtitle||'')+'</div>'+
        '<div class="meta">'+esc(s.language||'')+' • '+(s.year||'')+' • ⏱ '+(s.duration||'')+'</div>'+
        '<div class="actions">'+actions.join('')+'</div>'+
      '</div></div>';
  }).join('');
}
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def home():
    return HTML_PAGE


@app.get("/health")
def health():
    return {"status": "ok"}
