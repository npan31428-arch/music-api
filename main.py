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

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Apple Music Glass</title>
<style>
  /* ============================================================
     APPLE MUSIC GLASS THEME
     ============================================================ */
  :root {
    --apple-red: #FA233B;
    --apple-red-hover: #E32035;
    --glass-bg: rgba(255, 255, 255, 0.05);
    --glass-bg-hover: rgba(255, 255, 255, 0.1);
    --glass-border: rgba(255, 255, 255, 0.1);
    --text-main: #FFFFFF;
    --text-sec: #A1A1A6;
  }

  *{box-sizing:border-box; margin:0; padding:0; font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;}
  
  /* Dynamic Animated Background */
  body {
    background-color: #000;
    color: var(--text-main);
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    position: relative;
    z-index: 0;
  }

  /* Blurred colorful orbs for the glass effect to shine */
  .bg-orb {
    position: absolute;
    border-radius: 50%;
    filter: blur(80px);
    z-index: -1;
    opacity: 0.6;
    animation: float 10s infinite alternate ease-in-out;
  }
  .orb-1 { width: 400px; height: 400px; background: #FA233B; top: -100px; left: -100px; }
  .orb-2 { width: 500px; height: 500px; background: #5E5CE6; bottom: -150px; right: -100px; animation-delay: -5s; }
  .orb-3 { width: 300px; height: 300px; background: #FF9500; top: 40%; left: 40%; opacity: 0.3; }

  @keyframes float {
    0% { transform: translate(0, 0) scale(1); }
    100% { transform: translate(30px, 50px) scale(1.1); }
  }

  /* Glassmorphism Utility */
  .glass {
    background: var(--glass-bg);
    backdrop-filter: blur(25px);
    -webkit-backdrop-filter: blur(25px);
    border: 1px solid var(--glass-border);
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
  }

  /* Header */
  .header {
    margin: 15px; padding: 15px 25px; border-radius: 20px;
    display: flex; align-items: center; gap: 20px; z-index: 10;
  }
  .header h1 { font-size: 1.5rem; font-weight: 700; letter-spacing: -0.5px; display: flex; align-items: center; gap: 10px;}
  .header h1 span { color: var(--apple-red); }
  
  .search-box { flex: 1; display: flex; gap: 10px; max-width: 600px; margin-left: auto;}
  .search-box input {
    flex: 1; padding: 12px 20px; border-radius: 12px; border: 1px solid transparent;
    background: rgba(255, 255, 255, 0.1); color: white; outline: none; font-size: 1rem;
    transition: 0.3s;
  }
  .search-box input::placeholder { color: var(--text-sec); }
  .search-box input:focus { background: rgba(255, 255, 255, 0.15); border-color: rgba(255,255,255,0.3); }
  .search-box button {
    padding: 12px 25px; border-radius: 12px; border: none; background: var(--apple-red); 
    color: white; font-weight: 600; cursor: pointer; transition: 0.2s; font-size: 1rem;
  }
  .search-box button:hover { background: var(--apple-red-hover); transform: scale(1.02); }

  /* Main Layout */
  .main-content { flex: 1; display: flex; gap: 15px; padding: 0 15px 110px 15px; overflow: hidden; }
  
  .results-section {
    flex: 2; border-radius: 20px; padding: 20px; overflow-y: auto;
    display: flex; flex-direction: column; gap: 10px;
  }
  
  .sidebar {
    flex: 1; max-width: 380px; border-radius: 20px; display: flex; flex-direction: column;
  }

  /* Tabs */
  .tabs { display: flex; padding: 10px; gap: 10px; border-bottom: 1px solid var(--glass-border); }
  .tab {
    flex: 1; padding: 10px; border-radius: 10px; text-align: center; cursor: pointer;
    font-weight: 600; color: var(--text-sec); background: transparent; border: none; transition: 0.3s;
  }
  .tab.active { background: rgba(255,255,255,0.1); color: white; }
  .tab-content { flex: 1; overflow-y: auto; padding: 15px; display: none; }
  .tab-content.active { display: block; }

  /* Song Cards */
  .section-title { font-size: 1.2rem; font-weight: 700; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center;}
  .song-card {
    display: flex; align-items: center; gap: 15px; padding: 12px; border-radius: 16px;
    background: transparent; transition: 0.2s; border: 1px solid transparent;
  }
  .song-card:hover { background: rgba(255,255,255,0.05); border-color: var(--glass-border); }
  .song-card img { width: 60px; height: 60px; border-radius: 10px; object-fit: cover; box-shadow: 0 4px 15px rgba(0,0,0,0.4); }
  .song-info { flex: 1; min-width: 0; }
  .song-title { font-weight: 600; font-size: 1rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .song-meta { font-size: 0.85rem; color: var(--text-sec); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 4px;}
  
  /* Buttons */
  .actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 10px; }
  .btn {
    padding: 6px 14px; border-radius: 8px; border: none; cursor: pointer; font-size: 0.85rem;
    font-weight: 600; display: flex; align-items: center; gap: 6px; transition: 0.2s;
  }
  .btn-play { background: white; color: black; }
  .btn-play:hover { transform: scale(1.05); }
  .btn-outline { background: rgba(255,255,255,0.1); color: white; border: 1px solid transparent; }
  .btn-outline:hover { background: rgba(255,255,255,0.2); }
  .btn-fav { background: none; border: none; font-size: 1.3rem; cursor: pointer; transition: 0.2s; padding: 5px;}
  .btn-fav:hover { transform: scale(1.2); }
  
  .btn-dl {
    background: rgba(255,255,255,0.05); color: white; border: 1px solid rgba(255,255,255,0.2);
    font-size: 0.75rem; padding: 5px 10px; border-radius: 6px; cursor: pointer; font-weight: 600; transition: 0.2s;
  }
  .btn-dl:hover { background: var(--apple-red); border-color: var(--apple-red); }
  .btn-dl:disabled { opacity: 0.5; cursor: wait; }

  /* Floating Player Bar */
  .player-bar {
    position: fixed; bottom: 15px; left: 15px; right: 15px; height: 80px;
    border-radius: 20px; display: flex; align-items: center; justify-content: space-between;
    padding: 0 25px; z-index: 20;
  }
  
  .now-playing { display: flex; align-items: center; gap: 15px; width: 30%; }
  .now-playing img { width: 55px; height: 55px; border-radius: 10px; object-fit: cover; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
  
  .player-controls { display: flex; flex-direction: column; align-items: center; flex: 1; }
  .controls-btns { display: flex; gap: 25px; align-items: center; margin-bottom: 5px; }
  .controls-btns button { background: none; border: none; color: white; font-size: 1.4rem; cursor: pointer; transition: 0.2s; }
  .controls-btns button:hover { color: var(--apple-red); transform: scale(1.1); }
  .controls-btns .play-btn { font-size: 2.2rem; color: white; }
  
  .progress-container { width: 100%; max-width: 450px; display: flex; align-items: center; gap: 10px; font-size: 0.75rem; color: var(--text-sec); font-weight: 500;}
  .progress-bar { flex: 1; height: 6px; background: rgba(255,255,255,0.2); border-radius: 3px; cursor: pointer; position: relative; overflow: hidden;}
  .progress-fill { height: 100%; background: white; width: 0%; border-radius: 3px; transition: 0.1s; }
  
  .volume-control { width: 25%; display: flex; justify-content: flex-end; align-items: center; gap: 10px; }
  .volume-control input { width: 100px; accent-color: white; cursor: pointer; }

  /* Scrollbar */
  ::-webkit-scrollbar { width: 8px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.2); border-radius: 4px; }
  ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.4); }

  @media (max-width: 800px) {
    .header { flex-direction: column; align-items: stretch; padding: 15px; }
    .search-box { margin-left: 0; }
    .main-content { flex-direction: column; padding: 0 10px 100px 10px; }
    .sidebar { display: none; }
    .volume-control { display: none; }
    .now-playing { width: 40%; }
    .player-controls { width: 60%; }
    .player-bar { padding: 0 15px; bottom: 10px; left: 10px; right: 10px; }
  }
</style>
</head>
<body>

<!-- Background Orbs for Glass Effect -->
<div class="bg-orb orb-1"></div>
<div class="bg-orb orb-2"></div>
<div class="bg-orb orb-3"></div>

<div class="header glass">
  <h1><span></span> Music Glass</h1>
  <form class="search-box" onsubmit="doSearch(event)">
    <input id="q" placeholder="Search songs (e.g. Saree Se Tadi)..." autofocus>
    <button type="submit" id="searchBtn">Search</button>
  </form>
</div>

<div class="main-content">
  <div class="results-section glass">
    <div class="section-title" id="resultsTitle">Search Results</div>
    <div id="results"></div>
  </div>
  
  <div class="sidebar glass">
    <div class="tabs">
      <button class="tab active" onclick="switchTab('queue')" id="tab-queue">Up Next</button>
      <button class="tab" onclick="switchTab('fav')" id="tab-fav">Favorites ❤️</button>
    </div>
    
    <div class="tab-content active" id="content-queue">
      <div class="section-title">
        Queue <button class="btn btn-outline" onclick="clearQueue()">Clear</button>
      </div>
      <div id="queueList"></div>
    </div>
    
    <div class="tab-content" id="content-fav">
      <div class="section-title">My Favorites</div>
      <div id="favList"></div>
    </div>
  </div>
</div>

<div class="player-bar glass">
  <div class="now-playing">
    <img id="playerImg" src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='60' height='60'><rect width='60' height='60' fill='%23333'/><text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle' font-size='24' fill='%23888'>🎵</text></svg>" alt="Cover">
    <div class="song-info">
      <div class="song-title" id="playerTitle">Select a song</div>
      <div class="song-meta" id="playerArtist">-</div>
    </div>
    <button class="btn-fav" id="playerFavBtn" onclick="toggleFavCurrent()">🤍</button>
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

  <div class="volume-control">
    <span>🔊</span>
    <input type="range" id="volumeSlider" min="0" max="1" step="0.01" value="1" onchange="changeVolume(this.value)">
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

  function switchTab(tab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById('tab-' + tab).classList.add('active');
    document.getElementById('content-' + tab).classList.add('active');
  }

  async function doSearch(e) {
    e.preventDefault();
    const query = document.getElementById('q').value.trim();
    if (!query) return;
    
    document.getElementById('resultsTitle').innerText = 'Searching...';
    document.getElementById('results').innerHTML = '';
    document.getElementById('searchBtn').disabled = true;

    try {
      const res = await fetch('/api/search?song=' + encodeURIComponent(query));
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Error');
      
      searchResults = data.results || [];
      document.getElementById('resultsTitle').innerText = `Results (${data.total || searchResults.length})`;
      renderResults();
    } catch (err) {
      document.getElementById('resultsTitle').innerText = 'Error!';
      document.getElementById('results').innerHTML = `<p style="color:var(--apple-red)">${err.message}</p>`;
    } finally {
      document.getElementById('searchBtn').disabled = false;
    }
  }

  function renderResults() {
    const container = document.getElementById('results');
    container.innerHTML = searchResults.map((s, i) => generateSongCard(s, i, 'search')).join('');
  }

  function generateSongCard(s, index, source) {
    const isFav = favorites.some(f => f.id === s.id);
    const favIcon = isFav ? '❤️' : '🤍';
    
    const urls = s.download_urls || {};
    const artistName = s.artists ? s.artists.join(', ') : 'Unknown';
    
    let dlHtml = '';
    if(urls['320']) dlHtml += `<button onclick="downloadSong(this, '${urls['320']}', '${sanitizeText(s.title)}', '${sanitizeText(artistName)}', '${s.image}')" class="btn-dl">320k</button>`;
    if(urls['160']) dlHtml += `<button onclick="downloadSong(this, '${urls['160']}', '${sanitizeText(s.title)}', '${sanitizeText(artistName)}', '${s.image}')" class="btn-dl">160k</button>`;
    if(urls['96']) dlHtml += `<button onclick="downloadSong(this, '${urls['96']}', '${sanitizeText(s.title)}', '${sanitizeText(artistName)}', '${s.image}')" class="btn-dl">96k</button>`;

    let queueBtn = source === 'search' ? `<button class="btn btn-outline" onclick="addToQueue(${index})">+ Queue</button>` : 
                   `<button class="btn btn-outline" style="color:var(--apple-red)" onclick="removeFromQueue(${index})">Remove</button>`;

    return `
      <div class="song-card">
        <img src="${s.image || ''}" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'60\\' height=\\'60\\'><rect width=\\'60\\' height=\\'60\\' fill=\\'%23333\\'/></svg>'">
        <div class="song-info">
          <div class="song-title">${s.title}</div>
          <div class="song-meta">${s.subtitle || ''}</div>
          <div class="actions">
            <button class="btn btn-play" onclick="${source === 'search' ? `playFromSearch(${index})` : `playFromQueue(${index})`}">▶ Play</button>
            ${queueBtn}
            ${dlHtml}
          </div>
        </div>
        <button class="btn-fav" onclick="toggleFav(${index}, '${source}')">${favIcon}</button>
      </div>
    `;
  }

  function sanitizeText(text) {
    return text.replace(/'/g, "\\\\'").replace(/"/g, '&quot;');
  }

  function downloadSong(btn, url, title, artist, image) {
    const originalText = btn.innerText;
    btn.innerText = '⌛...';
    btn.disabled = true;
    
    const dlUrl = `/api/dl?url=${encodeURIComponent(url)}&title=${encodeURIComponent(title)}&artist=${encodeURIComponent(artist)}&image=${encodeURIComponent(image)}`;
    window.location.href = dlUrl; 
    
    setTimeout(() => {
      btn.innerText = originalText;
      btn.disabled = false;
    }, 4000);
  }

  function renderQueue() {
    const container = document.getElementById('queueList');
    if (queue.length === 0) {
      container.innerHTML = '<p style="color:var(--text-sec);text-align:center;margin-top:20px;">Queue is empty</p>';
      return;
    }
    container.innerHTML = queue.map((s, i) => generateSongCard(s, i, 'queue')).join('');
  }

  function addToQueue(index) {
    queue.push(searchResults[index]);
    renderQueue();
    if (!currentSong) playFromQueue(0);
  }

  function removeFromQueue(index) {
    queue.splice(index, 1);
    renderQueue();
    if (queue.length > 0 && !currentSong) playFromQueue(0);
  }

  function clearQueue() {
    queue = [];
    renderQueue();
  }

  function renderFavorites() {
    const container = document.getElementById('favList');
    if (favorites.length === 0) {
      container.innerHTML = '<p style="color:var(--text-sec);text-align:center;margin-top:20px;">No favorites yet</p>';
      return;
    }
    container.innerHTML = favorites.map((s, i) => `
      <div class="song-card">
        <img src="${s.image || ''}" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'60\\' height=\\'60\\'><rect width=\\'60\\' height=\\'60\\' fill=\\'%23333\\'/></svg>'">
        <div class="song-info">
          <div class="song-title">${s.title}</div>
          <div class="song-meta">${s.subtitle || ''}</div>
          <div class="actions">
            <button class="btn btn-play" onclick="playFav(${i})">▶ Play</button>
          </div>
        </div>
        <button class="btn-fav" onclick="removeFav(${i})">❤️</button>
      </div>
    `).join('');
  }

  function toggleFav(index, source) {
    let song = source === 'search' ? searchResults[index] : queue[index];
    const exists = favorites.findIndex(f => f.id === song.id);
    if (exists > -1) {
      favorites.splice(exists, 1);
    } else {
      favorites.push(song);
    }
    localStorage.setItem('musicFavs', JSON.stringify(favorites));
    renderResults();
    renderQueue();
    renderFavorites();
    updatePlayerFavIcon();
  }

  function toggleFavCurrent() {
    if(!currentSong) return;
    const exists = favorites.findIndex(f => f.id === currentSong.id);
    if (exists > -1) favorites.splice(exists, 1);
    else favorites.push(currentSong);
    localStorage.setItem('musicFavs', JSON.stringify(favorites));
    renderResults();
    renderQueue();
    renderFavorites();
    updatePlayerFavIcon();
  }

  function removeFav(index) {
    favorites.splice(index, 1);
    localStorage.setItem('musicFavs', JSON.stringify(favorites));
    renderFavorites();
    updatePlayerFavIcon();
  }

  function updatePlayerFavIcon() {
    if(!currentSong) {
      document.getElementById('playerFavBtn').innerText = '🤍';
      return;
    }
    const isFav = favorites.some(f => f.id === currentSong.id);
    document.getElementById('playerFavBtn').innerText = isFav ? '❤️' : '🤍';
  }

  function playFromSearch(index) {
    currentSong = searchResults[index];
    playSong(currentSong);
    if(!queue.find(q => q.id === currentSong.id)) {
      queue.push(currentSong);
      renderQueue();
    }
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
    document.getElementById('playerArtist').innerText = song.subtitle || '';
    updatePlayerFavIcon();
    
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
    if (idx > -1 && idx < queue.length - 1) {
      playFromQueue(idx + 1);
    }
  }

  function playPrev() {
    if(!currentSong) return;
    const idx = queue.findIndex(q => q.id === currentSong.id);
    if (idx > 0) {
      playFromQueue(idx - 1);
    }
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

  renderQueue();
  renderFavorites();
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
