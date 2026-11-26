import os
import io
import requests
from fastapi import FastAPI, Query, HTTPException, Response
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from mutagen.mp4 import MP4, MP4Cover

app = FastAPI(title="Chill Music API")

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
        except: pass

        safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c in ' -_']).rstrip()
        safe_artist = "".join([c for c in artist if c.isalpha() or c.isdigit() or c in ' -_']).rstrip()
        filename = f"{safe_title} - {safe_artist}.m4a"

        return Response(content=audio_io.read(), media_type="audio/mp4", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Chill Ratna</title>
<style>
  :root {
    --apple-red: #FA233B;
    --glass-bg: rgba(20, 20, 25, 0.7);
    --glass-border: rgba(255, 255, 255, 0.08);
    --text-main: #FFFFFF;
    --text-sec: #A1A1A6;
    --sidebar-width: 260px;
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

  /* Animated Background */
  .bg-orb { position: absolute; border-radius: 50%; filter: blur(100px); z-index: -1; opacity: 0.4; animation: float 10s infinite alternate ease-in-out; }
  .orb-1 { width: 500px; height: 500px; background: #FA233B; top: -150px; left: -150px; }
  .orb-2 { width: 600px; height: 600px; background: #5E5CE6; bottom: -200px; right: -100px; animation-delay: -5s; }
  @keyframes float { 0% { transform: translate(0, 0); } 100% { transform: translate(50px, 50px); } }

  .glass { background: var(--glass-bg); backdrop-filter: blur(30px); -webkit-backdrop-filter: blur(30px); border: 1px solid var(--glass-border); }

  /* --- SIDEBAR --- */
  .sidebar {
    width: var(--sidebar-width); height: 100%; padding: 25px 15px;
    display: flex; flex-direction: column; gap: 10px; border-right: 1px solid var(--glass-border);
    z-index: 10; background: rgba(0,0,0,0.8); backdrop-filter: blur(20px);
  }
  .brand { font-size: 1.8rem; font-weight: 800; letter-spacing: -1px; margin-bottom: 30px; padding-left: 10px; display: flex; align-items: center; gap: 10px;}
  .brand span { color: var(--apple-red); }
  
  .nav-item {
    display: flex; align-items: center; gap: 15px; padding: 12px 15px;
    border-radius: 10px; cursor: pointer; color: var(--text-sec); font-weight: 600; font-size: 1rem; transition: 0.2s;
  }
  .nav-item:hover, .nav-item.active { background: rgba(255,255,255,0.1); color: white; }
  
  /* --- MAIN CONTENT --- */
  .main-view {
    flex: 1; height: 100%; overflow-y: auto; padding: 20px 40px 120px 40px; position: relative;
  }
  
  .top-bar { display: flex; justify-content: center; margin-bottom: 40px; margin-top: 10px;}
  .search-container {
    display: flex; align-items: center; background: rgba(255,255,255,0.08);
    border-radius: 30px; padding: 12px 25px; width: 100%; max-width: 600px; border: 1px solid transparent; transition: 0.3s;
  }
  .search-container:focus-within { border-color: rgba(255,255,255,0.3); background: rgba(255,255,255,0.12); }
  .search-container input { flex: 1; background: transparent; border: none; color: white; font-size: 1rem; outline: none; margin-left: 10px;}
  .search-container input::placeholder { color: var(--text-sec); }

  .section-header { font-size: 1.5rem; font-weight: 700; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;}
  
  /* Grid Layouts */
  .songs-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 15px; margin-bottom: 40px;}
  .playlists-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 20px; }
  
  /* Song Cards */
  .song-card {
    display: flex; align-items: center; gap: 15px; padding: 10px; border-radius: 12px;
    transition: 0.2s; cursor: pointer; border: 1px solid transparent; position: relative;
  }
  .song-card:hover { background: rgba(255,255,255,0.08); border-color: rgba(255,255,255,0.1); }
  .song-card img { width: 60px; height: 60px; border-radius: 8px; object-fit: cover; }
  .song-info { flex: 1; min-width: 0; }
  .song-title { font-weight: 600; font-size: 1rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .song-meta { font-size: 0.85rem; color: var(--text-sec); margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
  
  /* Hover Actions */
  .song-actions { display: flex; gap: 8px; opacity: 0; transition: 0.2s; position: absolute; right: 10px; background: linear-gradient(90deg, transparent, #1a1a1a 30%); padding-left: 20px;}
  .song-card:hover .song-actions { opacity: 1; }
  .icon-btn { background: white; color: black; border: none; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 1rem; transition: 0.2s;}
  .icon-btn:hover { transform: scale(1.1); }
  .icon-btn.dl { background: rgba(255,255,255,0.2); color: white; border-radius: 8px; width: auto; padding: 0 10px; font-size: 0.8rem; font-weight: bold;}

  /* Playlist Cards */
  .playlist-card { cursor: pointer; transition: 0.2s; }
  .playlist-card:hover { transform: translateY(-5px); }
  .playlist-card img { width: 100%; aspect-ratio: 1; object-fit: cover; border-radius: 12px; margin-bottom: 10px; box-shadow: 0 10px 20px rgba(0,0,0,0.5); }
  .playlist-title { font-weight: 600; font-size: 1rem; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
  .playlist-desc { font-size: 0.85rem; color: var(--text-sec); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}

  /* --- BOTTOM PLAYER BAR --- */
  .player-bar {
    position: fixed; bottom: 0; left: 0; right: 0; height: var(--player-height);
    background: rgba(15, 15, 20, 0.85); backdrop-filter: blur(40px); -webkit-backdrop-filter: blur(40px);
    border-top: 1px solid var(--glass-border); display: flex; align-items: center; justify-content: space-between;
    padding: 0 25px; z-index: 100;
  }
  
  .player-left { display: flex; align-items: center; gap: 15px; width: 30%; min-width: 200px;}
  .player-left img { width: 55px; height: 55px; border-radius: 8px; object-fit: cover; }
  .player-info { min-width: 0; }
  .player-title { font-size: 0.95rem; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .player-artist { font-size: 0.8rem; color: var(--text-sec); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 2px;}
  
  .player-center { display: flex; flex-direction: column; align-items: center; flex: 1; max-width: 600px;}
  .player-controls { display: flex; gap: 25px; align-items: center; margin-bottom: 8px; }
  .ctrl-btn { background: none; border: none; color: var(--text-sec); font-size: 1.2rem; cursor: pointer; transition: 0.2s; display: flex; align-items: center; justify-content: center;}
  .ctrl-btn:hover { color: white; }
  .play-btn { font-size: 2rem; color: white; background: white; color: black; width: 45px; height: 45px; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
  
  .progress-wrap { width: 100%; display: flex; align-items: center; gap: 10px; font-size: 0.75rem; color: var(--text-sec); }
  .progress-bar { flex: 1; height: 4px; background: rgba(255,255,255,0.15); border-radius: 2px; cursor: pointer; position: relative; }
  .progress-fill { height: 100%; background: white; width: 0%; border-radius: 2px; transition: 0.1s; }
  
  .player-right { width: 30%; display: flex; justify-content: flex-end; align-items: center; gap: 15px; }
  .volume-slider { width: 100px; accent-color: white; }
  
  /* Custom Scrollbar */
  ::-webkit-scrollbar { width: 8px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.2); border-radius: 4px; }
  ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.4); }
  
  .loading-spinner { text-align: center; color: var(--text-sec); padding: 40px; font-size: 1.2rem;}

  @media (max-width: 800px) {
    .sidebar { display: none; }
    .main-view { padding: 20px 15px 120px 15px; }
    .player-left { width: 40%; }
    .player-center { max-width: 40%; }
    .player-right { display: none; }
  }
</style>
</head>
<body>

<!-- Background Orbs -->
<div class="bg-orb orb-1"></div>
<div class="bg-orb orb-2"></div>

<!-- SIDEBAR -->
<div class="sidebar">
  <div class="brand"><span>🎧</span> Chill Ratna</div>
  
  <div class="nav-item active" onclick="loadHome()">
    <span>🏠</span> Home
  </div>
  <div class="nav-item" onclick="switchView('favorites')">
    <span>❤️</span> Favorites
  </div>
  <div class="nav-item" onclick="switchView('queue')">
    <span>⏭️</span> My Queue
  </div>
</div>

<!-- MAIN VIEW -->
<div class="main-view" id="mainView">
  
  <div class="top-bar">
    <div class="search-container glass">
      <span>🔍</span>
      <input id="q" placeholder="Songs, Playlists, Album or Artist" onkeypress="if(event.key === 'Enter') doSearch()">
    </div>
  </div>

  <div id="dynamicContent">
    <!-- Content will be injected here -->
  </div>

</div>

<!-- PLAYER BAR -->
<div class="player-bar">
  <div class="player-left">
    <img id="playerImg" src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='55' height='55'><rect width='55' height='55' fill='%23222'/></svg>">
    <div class="player-info">
      <div class="player-title" id="playerTitle">Select a song</div>
      <div class="player-artist" id="playerArtist">-</div>
    </div>
    <button class="ctrl-btn" id="playerFavBtn" onclick="toggleFavCurrent()" style="margin-left:10px;">🤍</button>
  </div>
  
  <div class="player-center">
    <div class="player-controls">
      <button class="ctrl-btn" onclick="playPrev()">⏮</button>
      <button class="ctrl-btn play-btn" id="playPauseBtn" onclick="togglePlay()">▶</button>
      <button class="ctrl-btn" onclick="playNext()">⏭</button>
    </div>
    <div class="progress-wrap">
      <span id="currTime">0:00</span>
      <div class="progress-bar" onclick="seekAudio(event)">
        <div class="progress-fill" id="progressFill"></div>
      </div>
      <span id="totalTime">0:00</span>
    </div>
  </div>

  <div class="player-right">
    <span>🔊</span>
    <input type="range" class="volume-slider" id="volumeSlider" min="0" max="1" step="0.01" value="1" onchange="changeVolume(this.value)">
  </div>
</div>

<audio id="audioPlayer"></audio>

<script>
  let searchResults = [];
  let queue = [];
  let favorites = JSON.parse(localStorage.getItem('chillFavs')) || [];
  let currentSong = null;
  let isPlaying = false;
  let currentView = 'home';
  const audio = document.getElementById('audioPlayer');
  const mainView = document.getElementById('dynamicContent');

  // INITIAL LOAD (Jadu: Blank homepage fix)
  window.onload = () => {
    // Default search to populate the homepage
    document.getElementById('q').value = "Himesh Reshammiya";
    doSearch(true); 
  };

  // --- NAVIGATION & VIEWS ---
  function setActiveNav(index) {
    document.querySelectorAll('.nav-item').forEach((el, i) => {
      if(i === index) el.classList.add('active');
      else el.classList.remove('active');
    });
  }

  function loadHome() {
    setActiveNav(0);
    if(searchResults.length > 0) renderHomeGrid();
    else doSearch(true);
  }

  function switchView(view) {
    currentView = view;
    mainView.innerHTML = '';
    if(view === 'favorites') {
      setActiveNav(1);
      renderView('My Favorites', favorites, 'fav');
    } else if(view === 'queue') {
      setActiveNav(2);
      renderView('Up Next in Queue', queue, 'queue');
    }
  }

  // --- SEARCH & RENDERING ---
  async function doSearch(isDefault = false) {
    const query = document.getElementById('q').value.trim();
    if (!query) return;
    
    if(!isDefault) setActiveNav(0);
    mainView.innerHTML = '<div class="loading-spinner">Loading...</div>';

    try {
      const res = await fetch('/api/search?song=' + encodeURIComponent(query));
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Error');
      
      searchResults = data.results || [];
      currentView = 'home';
      renderHomeGrid();
    } catch (err) {
      mainView.innerHTML = `<div class="loading-spinner" style="color:var(--apple-red)">Error: ${err.message}</div>`;
    }
  }

  function renderHomeGrid() {
    if(searchResults.length === 0) return;

    let html = `
      <div class="section-header">Discover</div>
      <div class="songs-grid">
        ${searchResults.slice(0, 12).map((s, i) => generateSongCard(s, i, 'search')).join('')}
      </div>

      <div class="section-header">Trending Playlists</div>
      <div class="playlists-grid">
        ${searchResults.slice(12, 20).map((s, i) => `
          <div class="playlist-card" onclick="playFromSearch(${i+12})">
            <img src="${s.image}" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'200\\' height=\\'200\\'><rect width=\\'200\\' height=\\'200\\' fill=\\'%23222\\'/></svg>'">
            <div class="playlist-title">${s.title}</div>
            <div class="playlist-desc">${s.artists ? s.artists[0] : 'Various Artists'}</div>
          </div>
        `).join('')}
      </div>
    `;
    mainView.innerHTML = html;
  }

  function renderView(title, list, type) {
    if(list.length === 0) {
      mainView.innerHTML = `<div class="section-header">${title}</div><div class="loading-spinner">No songs here yet.</div>`;
      return;
    }
    mainView.innerHTML = `
      <div class="section-header">${title}</div>
      <div class="songs-grid">
        ${list.map((s, i) => generateSongCard(s, i, type)).join('')}
      </div>
    `;
  }

  function generateSongCard(s, index, source) {
    const isFav = favorites.some(f => f.id === s.id);
    const favIcon = isFav ? '❤️' : '🤍';
    const urls = s.download_urls || {};
    const artistName = s.artists ? s.artists.join(', ') : 'Unknown';
    
    // Download Buttons
    let dlHtml = '';
    if(urls['320']) dlHtml += `<button onclick="event.stopPropagation(); downloadSong(this, '${urls['320']}', '${sanitizeText(s.title)}', '${sanitizeText(artistName)}', '${s.image}')" class="icon-btn dl">320k</button>`;
    
    // Play Function logic based on source
    let playAction = `playFromSearch(${index})`;
    if(source === 'fav') playAction = `playFav(${index})`;
    if(source === 'queue') playAction = `playFromQueue(${index})`;

    return `
      <div class="song-card" onclick="${playAction}">
        <img src="${s.image || ''}" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'60\\' height=\\'60\\'><rect width=\\'60\\' height=\\'60\\' fill=\\'%23222\\'/></svg>'">
        <div class="song-info">
          <div class="song-title">${s.title}</div>
          <div class="song-meta">${s.artists ? s.artists[0] : 'Unknown'}</div>
        </div>
        <div class="song-actions">
          ${dlHtml}
          <button onclick="event.stopPropagation(); toggleFav(${index}, '${source}')" class="icon-btn" style="background:transparent">${favIcon}</button>
        </div>
      </div>
    `;
  }

  // --- QUEUE & FAVORITES ---
  function addToQueue(index) {
    queue.push(searchResults[index]);
    if(currentView === 'queue') renderView('Up Next in Queue', queue, 'queue');
  }

  function toggleFav(index, source) {
    let song = source === 'search' ? searchResults[index] : (source === 'queue' ? queue[index] : favorites[index]);
    const exists = favorites.findIndex(f => f.id === song.id);
    if (exists > -1) {
      favorites.splice(exists, 1);
    } else {
      favorites.push(song);
    }
    localStorage.setItem('chillFavs', JSON.stringify(favorites));
    
    // Refresh current view
    if(currentView === 'home') renderHomeGrid();
    else if(currentView === 'favorites') renderView('My Favorites', favorites, 'fav');
    else if(currentView === 'queue') renderView('Up Next in Queue', queue, 'queue');
    
    updatePlayerFavIcon();
  }

  function toggleFavCurrent() {
    if(!currentSong) return;
    const exists = favorites.findIndex(f => f.id === currentSong.id);
    if (exists > -1) favorites.splice(exists, 1);
    else favorites.push(currentSong);
    localStorage.setItem('chillFavs', JSON.stringify(favorites));
    updatePlayerFavIcon();
    if(currentView === 'favorites') renderView('My Favorites', favorites, 'fav');
  }

  function updatePlayerFavIcon() {
    if(!currentSong) { document.getElementById('playerFavBtn').innerText = '🤍'; return; }
    const isFav = favorites.some(f => f.id === currentSong.id);
    document.getElementById('playerFavBtn').innerText = isFav ? '❤️' : '🤍';
  }

  // --- DOWNLOAD ---
  function sanitizeText(text) {
    return text.replace(/'/g, "\\\\'").replace(/"/g, '&quot;');
  }

  function downloadSong(btn, url, title, artist, image) {
    const originalText = btn.innerText;
    btn.innerText = '⌛';
    btn.disabled = true;
    const dlUrl = `/api/dl?url=${encodeURIComponent(url)}&title=${encodeURIComponent(title)}&artist=${encodeURIComponent(artist)}&image=${encodeURIComponent(image)}`;
    window.location.href = dlUrl; 
    setTimeout(() => { btn.innerText = originalText; btn.disabled = false; }, 4000);
  }

  // --- PLAYER LOGIC ---
  function playFromSearch(index) {
    currentSong = searchResults[index];
    playSong(currentSong);
    addToQueue(index); // Auto add to queue
  }

  function playFromQueue(index) {
    currentSong = queue[index];
    playSong(currentSong);
  }

  function playFav(index) {
    currentSong = favorites[index];
    playSong(currentSong);
  }

  function playSong(song) {
    document.getElementById('playerImg').src = song.image || '';
    document.getElementById('playerTitle').innerText = song.title;
    document.getElementById('playerArtist').innerText = song.artists ? song.artists[0] : '-';
    updatePlayerFavIcon();
    
    const url = song.download_urls['320'] || song.download_url;
    audio.src = url;
    audio.play().then(() => {
      isPlaying = true;
      document.getElementById('playPauseBtn').innerText = '⏸';
    }).catch(e => console.log("Playback failed:", e));
  }

  function togglePlay() {
    if (!audio.src) return;
    if (isPlaying) {
      audio.pause();
      document.getElementById('playPauseBtn').innerText = '▶';
    } else {
      audio.play();
      document.getElementById('playPauseBtn').innerText = '⏸';
    }
    isPlaying = !isPlaying;
  }

  function playNext() {
    if(!currentSong) return;
    const idx = queue.findIndex(q => q.id === currentSong.id);
    if (idx > -1 && idx < queue.length - 1) playFromQueue(idx + 1);
  }

  function playPrev() {
    if(!currentSong) return;
    const idx = queue.findIndex(q => q.id === currentSong.id);
    if (idx > 0) playFromQueue(idx - 1);
  }

  // --- AUDIO EVENTS ---
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
