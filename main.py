import os
import io
import requests
from fastapi import FastAPI, Query, HTTPException, Response
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from mutagen.mp4 import MP4, MP4Cover

app = FastAPI(title="Apple Music Glass API")

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

@app.get("/api/dl")
def download_file(url: str, title: str, artist: str, image: str = ""):
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        audio_io = io.BytesIO(r.content)

        try:
            audio = MP4(audio_io)
            audio["\xa9nam"] = title
            audio["\xa9ART"] = artist
            
            if image:
                try:
                    img_res = requests.get(image, timeout=10)
                    if img_res.status_code == 200:
                        audio["covr"] = [MP4Cover(img_res.content, imageformat=MP4Cover.FORMAT_JPEG)]
                except: pass
                    
            audio.save(audio_io)
            audio_io.seek(0)
        except Exception as e:
            print(f"Tagging failed: {e}")
            audio_io.seek(0)

        safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c in ' -_']).rstrip()
        safe_artist = "".join([c for c in artist if c.isalpha() or c.isdigit() or c in ' -_']).rstrip()
        filename = f"{safe_title} - {safe_artist}.m4a"

        return Response(
            content=audio_io.read(),
            media_type="audio/mp4",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# APPLE MUSIC DESKTOP UI (Matching Image)
# ==========================================
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Apple Music Glass</title>
<style>
  :root {
    --apple-red: #FA233B;
    --apple-red-hover: #E32035;
    --glass-bg: rgba(255, 255, 255, 0.05);
    --glass-hover: rgba(255, 255, 255, 0.1);
    --glass-border: rgba(255, 255, 255, 0.08);
    --text-main: #FFFFFF;
    --text-sec: #A1A1A6;
    --sidebar-width: 250px;
    --player-height: 90px;
  }

  *{box-sizing:border-box; margin:0; padding:0; font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;}
  
  body {
    background-color: #000;
    color: var(--text-main);
    height: 100vh;
    display: flex;
    overflow: hidden;
    position: relative;
  }

  /* Background Orbs for Glass */
  .bg-orb { position: absolute; border-radius: 50%; filter: blur(100px); z-index: 0; opacity: 0.4; animation: float 15s infinite alternate ease-in-out; }
  .orb-1 { width: 500px; height: 500px; background: #FA233B; top: -150px; left: -150px; }
  .orb-2 { width: 600px; height: 600px; background: #5E5CE6; bottom: -200px; right: -100px; animation-delay: -5s; }
  .orb-3 { width: 400px; height: 400px; background: #FF9500; top: 30%; left: 40%; opacity: 0.2; }
  @keyframes float { 0% { transform: translate(0, 0) scale(1); } 100% { transform: translate(40px, 60px) scale(1.1); } }

  .glass {
    background: var(--glass-bg);
    backdrop-filter: blur(25px);
    -webkit-backdrop-filter: blur(25px);
    border: 1px solid var(--glass-border);
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.4);
  }

  /* ========== SIDEBAR ========== */
  .sidebar {
    width: var(--sidebar-width);
    height: 100%;
    padding: 30px 20px;
    display: flex; flex-direction: column; gap: 30px;
    border-right: 1px solid var(--glass-border);
    z-index: 10;
  }
  
  .logo { font-size: 1.8rem; font-weight: 800; display: flex; align-items: center; gap: 10px; letter-spacing: -0.5px;}
  .logo span { color: var(--apple-red); font-size: 2rem; }
  
  .nav-menu { display: flex; flex-direction: column; gap: 10px; }
  .nav-item {
    display: flex; align-items: center; gap: 15px; padding: 12px 15px; border-radius: 10px;
    color: var(--text-main); text-decoration: none; font-weight: 600; font-size: 1rem;
    cursor: pointer; transition: 0.2s; opacity: 0.7;
  }
  .nav-item:hover, .nav-item.active { background: rgba(255,255,255,0.1); opacity: 1; }
  .nav-item.active { background: rgba(255,255,255,0.15); }
  
  /* ========== MAIN CONTENT ========== */
  .main-wrapper {
    flex: 1; height: 100%; display: flex; flex-direction: column;
    overflow: hidden; z-index: 10;
  }

  /* Top Search Bar */
  .top-bar { padding: 20px 40px; display: flex; justify-content: center; align-items: center;}
  .search-box {
    width: 100%; max-width: 600px; position: relative; display: flex; align-items: center;
  }
  .search-box input {
    width: 100%; padding: 14px 20px 14px 45px; border-radius: 12px; border: none;
    background: rgba(255, 255, 255, 0.15); color: white; font-size: 1rem; outline: none;
    transition: 0.3s; backdrop-filter: blur(10px);
  }
  .search-box input::placeholder { color: var(--text-sec); }
  .search-box input:focus { background: rgba(255, 255, 255, 0.25); }
  .search-icon { position: absolute; left: 15px; color: var(--text-sec); font-size: 1.2rem; }

  /* Content Area */
  .content-scroll { flex: 1; overflow-y: auto; padding: 0 40px 120px 40px; }

  .section-title { font-size: 1.4rem; font-weight: 700; margin: 30px 0 20px 0; }

  /* Discover Grid (Matching Image Layout) */
  .grid-layout {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 15px;
  }
  
  .song-card {
    display: flex; align-items: center; gap: 15px; padding: 10px; border-radius: 10px;
    background: transparent; transition: 0.2s; cursor: pointer; position: relative;
  }
  .song-card:hover { background: rgba(255,255,255,0.08); }
  .song-card img { width: 55px; height: 55px; border-radius: 6px; object-fit: cover; }
  
  .song-info { flex: 1; min-width: 0; }
  .song-title { font-weight: 600; font-size: 0.95rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .song-artist { font-size: 0.8rem; color: var(--text-sec); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 4px;}
  
  .card-actions { display: flex; gap: 5px; align-items: center; opacity: 0; transition: 0.2s; }
  .song-card:hover .card-actions { opacity: 1; }
  
  .btn-icon {
    background: none; border: none; color: white; font-size: 1.1rem; cursor: pointer;
    padding: 5px; border-radius: 5px; transition: 0.2s;
  }
  .btn-icon:hover { background: rgba(255,255,255,0.2); }
  .btn-play { color: var(--apple-red); font-size: 1.5rem; margin-right: 5px;}
  .btn-play:hover { color: var(--apple-red-hover); transform: scale(1.1); background: none; }

  /* Queue / Favorites Sidebar (Hidden by default on mobile) */
  .side-panel {
    width: 350px; height: 100%; border-left: 1px solid var(--glass-border);
    display: flex; flex-direction: column; z-index: 10;
    transition: 0.3s; transform: translateX(100%); position: absolute; right: 0; top: 0; bottom: var(--player-height);
  }
  .side-panel.open { transform: translateX(0); position: relative; }
  .panel-header { padding: 20px; font-weight: bold; display: flex; justify-content: space-between; border-bottom: 1px solid var(--glass-border);}
  .panel-content { flex: 1; overflow-y: auto; padding: 10px; }

  /* ========== PLAYER BAR ========== */
  .player-bar {
    position: fixed; bottom: 0; left: 0; right: 0; height: var(--player-height);
    display: flex; align-items: center; justify-content: space-between; padding: 0 20px;
    border-top: 1px solid var(--glass-border); z-index: 50;
  }
  
  .now-playing { display: flex; align-items: center; gap: 15px; width: 30%; }
  .now-playing img { width: 60px; height: 60px; border-radius: 8px; object-fit: cover; }
  .now-playing .info { display: flex; flex-direction: column; }
  
  .player-controls { display: flex; flex-direction: column; align-items: center; width: 40%; }
  .controls-btns { display: flex; align-items: center; gap: 20px; margin-bottom: 8px; }
  .controls-btns button { background: none; border: none; color: white; font-size: 1.2rem; cursor: pointer; transition: 0.2s; }
  .controls-btns button:hover { color: var(--apple-red); }
  .controls-btns .play-btn { font-size: 2rem; color: white; margin: 0 10px;}
  
  .progress-container { width: 100%; display: flex; align-items: center; gap: 10px; font-size: 0.75rem; color: var(--text-sec); }
  .progress-bar { flex: 1; height: 4px; background: rgba(255,255,255,0.2); border-radius: 2px; cursor: pointer; position: relative;}
  .progress-fill { height: 100%; background: white; width: 0%; border-radius: 2px; }
  
  .player-options { width: 30%; display: flex; justify-content: flex-end; align-items: center; gap: 15px; }
  .volume-control { display: flex; align-items: center; gap: 8px; }
  .volume-control input { width: 100px; accent-color: white; }

  /* Download Popup Menu */
  .dl-menu {
    position: absolute; background: #222; border: 1px solid #444; border-radius: 8px;
    padding: 5px; display: none; flex-direction: column; gap: 2px; z-index: 100; box-shadow: 0 5px 15px rgba(0,0,0,0.5);
  }
  .dl-menu.show { display: flex; }
  .dl-menu button {
    background: none; border: none; color: white; padding: 8px 15px; text-align: left;
    border-radius: 4px; cursor: pointer; font-size: 0.85rem;
  }
  .dl-menu button:hover { background: var(--apple-red); }

  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.2); border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.4); }

  @media (max-width: 900px) {
    .sidebar { width: 80px; padding: 20px 10px; align-items: center; }
    .logo span { font-size: 1.8rem; }
    .logo text { display: none; }
    .nav-item span { display: none; }
    .nav-item { justify-content: center; padding: 15px; }
    .content-scroll { padding: 0 20px 120px 20px; }
    .now-playing { width: 40%; }
    .now-playing .info { display: none; }
    .player-controls { width: 60%; }
    .player-options { display: none; }
  }
</style>
</head>
<body>

<div class="bg-orb orb-1"></div>
<div class="bg-orb orb-2"></div>
<div class="bg-orb orb-3"></div>

<!-- Sidebar -->
<div class="sidebar glass">
  <div class="logo"><span></span> Music</div>
  <div class="nav-menu">
    <div class="nav-item active" onclick="showHome()"><span>🏠</span> <text>Home</text></div>
    <div class="nav-item" onclick="showFavs()"><span>❤️</span> <text>Favorites</text></div>
    <div class="nav-item" onclick="togglePanel()"><span>📋</span> <text>Queue</text></div>
  </div>
</div>

<!-- Main Wrapper -->
<div class="main-wrapper">
  <div class="top-bar">
    <form class="search-box" onsubmit="doSearch(event)">
      <span class="search-icon">🔍</span>
      <input id="q" placeholder="Songs, Playlists, Album or Artist" autocomplete="off">
    </form>
  </div>

  <div class="content-scroll" id="content-area">
    
    <!-- Discover Section (Trending Songs) -->
    <div id="home-view">
      <div class="section-title">Discover</div>
      <div class="grid-layout" id="discover-grid">
        <!-- Populated by JS on load -->
      </div>
      
      <div class="section-title">Trending community playlists</div>
      <div class="grid-layout" id="trending-grid">
         <!-- Populated by JS on load -->
      </div>
    </div>

    <!-- Search Results View -->
    <div id="search-view" style="display:none;">
      <div class="section-title">Search Results</div>
      <div class="grid-layout" id="search-grid"></div>
    </div>
    
    <!-- Favorites View -->
    <div id="favs-view" style="display:none;">
      <div class="section-title">Your Favorites</div>
      <div class="grid-layout" id="favs-grid"></div>
    </div>

  </div>
</div>

<!-- Side Panel for Queue -->
<div class="side-panel glass" id="queue-panel">
  <div class="panel-header">
    <span>Up Next</span>
    <button class="btn-icon" onclick="togglePanel()">✖</button>
  </div>
  <div class="panel-content" id="queue-list">
    <!-- Queue items render here -->
  </div>
</div>

<!-- Player Bar -->
<div class="player-bar glass">
  <div class="now-playing">
    <img id="playerImg" src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='60' height='60'><rect width='60' height='60' fill='%23222'/><text x='50%' y='55%' dominant-baseline='middle' text-anchor='middle' font-size='24' fill='%23666'>🎵</text></svg>">
    <div class="info">
      <div class="song-title" id="playerTitle" style="font-size:0.95rem;">Not Playing</div>
      <div class="song-artist" id="playerArtist">-</div>
    </div>
    <button class="btn-icon" id="playerFavBtn" onclick="toggleFavCurrent()" style="margin-left:10px;">🤍</button>
  </div>
  
  <div class="player-controls">
    <div class="controls-btns">
      <button onclick="playPrev()">⏮️</button>
      <button class="play-btn" id="playPauseBtn" onclick="togglePlay()">▶️</button>
      <button onclick="playNext()">⏭️</button>
    </div>
    <div class="progress-container">
      <span id="currTime">0:00</span>
      <div class="progress-bar" onclick="seekAudio(event)">
        <div class="progress-fill" id="progressFill"></div>
      </div>
      <span id="totalTime">0:00</span>
    </div>
  </div>

  <div class="player-options">
    <div class="volume-control">
      <span>🔊</span>
      <input type="range" id="volumeSlider" min="0" max="1" step="0.01" value="1" onchange="changeVolume(this.value)">
    </div>
  </div>
</div>

<audio id="audioPlayer"></audio>

<script>
  let searchResults = [];
  let queue = [];
  let favorites = JSON.parse(localStorage.getItem('musicFavs')) || [];
  let currentSong = null;
  let isPlaying = false;
  const audio = document.getElementById('audioPlayer');

  // ==========================================
  // INITIAL LOAD (Auto Suggestions on App Open)
  // ==========================================
  window.onload = async () => {
    loadHomepageData();
  };

  async function loadHomepageData() {
    // College Girls / Trending Search Keywords
    const trendingQueries = [
       "Top Bollywood Hits", "Arijit Singh Best Songs", "Trending Reels Songs", 
       "Shreya Ghoshal Hits", "Punjabi Top 50", "English Pop Hits"
    ];
    
    const discoverGrid = document.getElementById('discover-grid');
    const trendingGrid = document.getElementById('trending-grid');
    
    // Skeleton Loading
    const skeleton = `<div class="song-card"><div style="width:55px;height:55px;background:rgba(255,255,255,0.1);border-radius:6px;"></div><div class="song-info"><div style="width:80%;height:12px;background:rgba(255,255,255,0.1);margin-bottom:8px;border-radius:4px;"></div><div style="width:50%;height:10px;background:rgba(255,255,255,0.1);border-radius:4px;"></div></div></div>`;
    discoverGrid.innerHTML = skeleton.repeat(8);
    trendingGrid.innerHTML = skeleton.repeat(8);

    try {
      // Fetch multiple categories to make the homepage look full
      const reqs = trendingQueries.map(q => fetch(`/api/search?song=${encodeURIComponent(q)}`).then(res => res.json()));
      const responses = await Promise.all(reqs);
      
      let allSongs = [];
      responses.forEach(data => {
        if(data.results) allSongs = allSongs.concat(data.results);
      });

      // Shuffle and slice for variety
      allSongs = allSongs.sort(() => 0.5 - Math.random());
      
      let discoverSongs = allSongs.slice(0, 8);
      let trendingSongs = allSongs.slice(8, 16);

      renderGrid(discoverGrid, discoverSongs, 'discover');
      renderGrid(trendingGrid, trendingSongs, 'trending');
      
      // Store in global array so play works
      searchResults = allSongs;
      
    } catch(e) {
      discoverGrid.innerHTML = '<p style="color:var(--text-sec)">Failed to load suggestions. Please search manually.</p>';
      trendingGrid.innerHTML = '';
    }
  }

  function showHome() {
    document.getElementById('home-view').style.display = 'block';
    document.getElementById('search-view').style.display = 'none';
    document.getElementById('favs-view').style.display = 'none';
    updateActiveNav(0);
  }

  function showFavs() {
    document.getElementById('home-view').style.display = 'none';
    document.getElementById('search-view').style.display = 'none';
    document.getElementById('favs-view').style.display = 'block';
    updateActiveNav(1);
    renderFavorites();
  }

  function updateActiveNav(index) {
    document.querySelectorAll('.nav-item').forEach((el, i) => {
      if(i === index) el.classList.add('active');
      else el.classList.remove('active');
    });
  }

  function togglePanel() {
    document.getElementById('queue-panel').classList.toggle('open');
    updateActiveNav(2);
  }

  // ==========================================
  // SEARCH
  // ==========================================
  async function doSearch(e) {
    e.preventDefault();
    const query = document.getElementById('q').value.trim();
    if (!query) return;

    document.getElementById('home-view').style.display = 'none';
    document.getElementById('favs-view').style.display = 'none';
    document.getElementById('search-view').style.display = 'block';
    
    const grid = document.getElementById('search-grid');
    grid.innerHTML = '<p>Searching...</p>';

    try {
      const res = await fetch('/api/search?song=' + encodeURIComponent(query));
      const data = await res.json();
      searchResults = data.results || [];
      renderGrid(grid, searchResults, 'search');
    } catch (err) {
      grid.innerHTML = `<p style="color:var(--apple-red)">${err.message}</p>`;
    }
  }

  // ==========================================
  // RENDER UI
  // ==========================================
  function renderGrid(container, songs, context) {
    if(songs.length === 0) {
      container.innerHTML = '<p style="color:var(--text-sec)">No songs found.</p>';
      return;
    }
    container.innerHTML = songs.map((s, i) => generateCard(s, i, context)).join('');
  }

  function generateCard(s, index, context) {
    const isFav = favorites.some(f => f.id === s.id);
    const favIcon = isFav ? '❤️' : '🤍';
    const artistName = s.artists ? s.artists[0] : 'Unknown Artist';
    
    // Download links hidden in a menu
    const urls = s.download_urls || {};
    let dlOptions = '';
    if(urls['320']) dlOptions += `<button onclick="downloadSong(event, '${urls['320']}', '${sanitizeText(s.title)}', '${sanitizeText(artistName)}', '${s.image}')">Download 320kbps</button>`;
    if(urls['160']) dlOptions += `<button onclick="downloadSong(event, '${urls['160']}', '${sanitizeText(s.title)}', '${sanitizeText(artistName)}', '${s.image}')">Download 160kbps</button>`;

    // Use global index for playing
    const globalIndex = searchResults.findIndex(x => x.id === s.id);

    return `
      <div class="song-card" onmouseleave="hideAllMenus()">
        <img src="${s.image || ''}" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'60\\' height=\\'60\\'><rect width=\\'60\\' height=\\'60\\' fill=\\'%23222\\'/></svg>'">
        <div class="song-info" onclick="playSongByIndex(${globalIndex})">
          <div class="song-title">${s.title}</div>
          <div class="song-artist">${s.subtitle || artistName}</div>
        </div>
        
        <div class="card-actions">
          <button class="btn-icon btn-play" onclick="playSongByIndex(${globalIndex})">▶</button>
          <button class="btn-icon" onclick="addToQueueById('${s.id}')" title="Add to Queue">+</button>
          
          <div style="position:relative;">
            <button class="btn-icon" onclick="toggleDlMenu(event)">⬇</button>
            <div class="dl-menu">
               ${dlOptions}
               <button onclick="addToQueueById('${s.id}')">Add to Queue</button>
            </div>
          </div>
          
          <button class="btn-icon" onclick="toggleFavById('${s.id}')">${favIcon}</button>
        </div>
      </div>
    `;
  }

  function toggleDlMenu(e) {
    e.stopPropagation();
    hideAllMenus();
    const menu = e.currentTarget.nextElementSibling;
    menu.classList.toggle('show');
  }

  function hideAllMenus() {
    document.querySelectorAll('.dl-menu').forEach(m => m.classList.remove('show'));
  }

  function sanitizeText(text) {
    return text.replace(/'/g, "\\\\'").replace(/"/g, '&quot;');
  }

  function downloadSong(e, url, title, artist, image) {
    e.stopPropagation();
    const btn = e.target;
    const originalText = btn.innerText;
    btn.innerText = 'Downloading...';
    btn.disabled = true;
    
    const dlUrl = `/api/dl?url=${encodeURIComponent(url)}&title=${encodeURIComponent(title)}&artist=${encodeURIComponent(artist)}&image=${encodeURIComponent(image)}`;
    window.location.href = dlUrl; 
    
    setTimeout(() => {
      btn.innerText = originalText;
      btn.disabled = false;
      hideAllMenus();
    }, 4000);
  }

  // ==========================================
  // FAVORITES & QUEUE LOGIC
  // ==========================================
  function toggleFavById(id) {
    const song = searchResults.find(s => s.id === id) || queue.find(s => s.id === id) || favorites.find(s => s.id === id);
    if(!song) return;
    const exists = favorites.findIndex(f => f.id === id);
    
    if (exists > -1) favorites.splice(exists, 1);
    else favorites.push(song);
    
    localStorage.setItem('musicFavs', JSON.stringify(favorites));
    
    // Rerender current view based on active tab
    if(document.getElementById('home-view').style.display !== 'none') loadHomepageData();
    else if(document.getElementById('search-view').style.display !== 'none') renderGrid(document.getElementById('search-grid'), searchResults, 'search');
    else if(document.getElementById('favs-view').style.display !== 'none') renderFavorites();
    
    renderQueue();
    updatePlayerFavIcon();
  }

  function toggleFavCurrent() {
    if(!currentSong) return;
    toggleFavById(currentSong.id);
  }

  function renderFavorites() {
    const grid = document.getElementById('favs-grid');
    if(favorites.length === 0) {
      grid.innerHTML = '<p style="color:var(--text-sec)">No favorites yet.</p>';
      return;
    }
    grid.innerHTML = favorites.map((s, i) => generateCard(s, i, 'fav')).join('');
  }

  function addToQueueById(id) {
    const song = searchResults.find(s => s.id === id);
    if(!song) return;
    if(queue.find(q => q.id === id)) return; // Already in queue
    
    queue.push(song);
    renderQueue();
    if(!currentSong) playSongByIndex(searchResults.findIndex(s => s.id === id));
  }

  function renderQueue() {
    const list = document.getElementById('queue-list');
    if(queue.length === 0) {
      list.innerHTML = '<p style="color:var(--text-sec);text-align:center;margin-top:20px;">Queue is empty</p>';
      return;
    }
    list.innerHTML = queue.map((s, i) => `
      <div class="song-card" style="${currentSong && currentSong.id === s.id ? 'border:1px solid var(--apple-red)' : ''}">
        <img src="${s.image}" style="width:45px;height:45px;">
        <div class="song-info" onclick="playQueueIndex(${i})">
           <div class="song-title">${s.title}</div>
           <div class="song-artist">${s.subtitle || ''}</div>
        </div>
        <button class="btn-icon" onclick="removeFromQueue(${i})">✖</button>
      </div>
    `).join('');
  }

  function removeFromQueue(i) {
    queue.splice(i, 1);
    renderQueue();
  }

  // ==========================================
  // AUDIO PLAYER LOGIC
  // ==========================================
  function playSongByIndex(index) {
    const song = searchResults[index];
    if(!song) return;
    currentSong = song;
    loadAndPlay(song);
    if(!queue.find(q => q.id === song.id)) {
      queue.push(song);
      renderQueue();
    }
  }

  function playQueueIndex(index) {
    currentSong = queue[index];
    loadAndPlay(currentSong);
  }

  function loadAndPlay(song) {
    document.getElementById('playerImg').src = song.image || '';
    document.getElementById('playerTitle').innerText = song.title;
    document.getElementById('playerArtist').innerText = song.subtitle || '';
    updatePlayerFavIcon();
    renderQueue();
    
    const url = song.download_urls['320'] || song.download_url;
    audio.src = url;
    audio.play().then(() => {
      isPlaying = true;
      document.getElementById('playPauseBtn').innerText = '⏸️';
    }).catch(e => console.log("Playback failed:", e));
  }

  function togglePlay() {
    if (!audio.src) return;
    if (isPlaying) {
      audio.pause();
      document.getElementById('playPauseBtn').innerText = '▶️';
    } else {
      audio.play();
      document.getElementById('playPauseBtn').innerText = '⏸️';
    }
    isPlaying = !isPlaying;
  }

  function playNext() {
    if(!currentSong) return;
    const idx = queue.findIndex(q => q.id === currentSong.id);
    if (idx > -1 && idx < queue.length - 1) playQueueIndex(idx + 1);
  }

  function playPrev() {
    if(!currentSong) return;
    const idx = queue.findIndex(q => q.id === currentSong.id);
    if (idx > 0) playQueueIndex(idx - 1);
  }

  function updatePlayerFavIcon() {
    if(!currentSong) return;
    const isFav = favorites.some(f => f.id === currentSong.id);
    document.getElementById('playerFavBtn').innerText = isFav ? '❤️' : '🤍';
  }

  audio.addEventListener('timeupdate', () => {
    const curr = audio.currentTime;
    const dur = audio.duration || 0;
    if (dur > 0) {
      document.getElementById('progressFill').style.width = (curr / dur) * 100 + '%';
      document.getElementById('currTime').innerText = formatTime(curr);
      document.getElementById('totalTime').innerText = formatTime(dur);
    }
  });

  audio.addEventListener('ended', () => { playNext(); });

  function seekAudio(e) {
    const bar = e.currentTarget;
    const percent = e.offsetX / bar.offsetWidth;
    if (audio.duration) audio.currentTime = percent * audio.duration;
  }

  function changeVolume(val) { audio.volume = val; }

  function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  }

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
