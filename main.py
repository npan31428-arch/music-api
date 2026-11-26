import os
import io
import requests
from fastapi import FastAPI, Query, HTTPException, Response
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from mutagen.mp4 import MP4, MP4Cover

app = FastAPI(title="Pro Music API")

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

# NAYA ENDPOINT: Jadu yahan hoga (Thumbnail + Name Tagging)
@app.get("/api/dl")
def download_file(url: str, title: str, artist: str, image: str = ""):
    try:
        # 1. Audio Download karo
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        audio_io = io.BytesIO(r.content)

        # 2. Metadata (Tags) add karo
        try:
            audio = MP4(audio_io)
            audio["\xa9nam"] = title  # Title Tag
            audio["\xa9ART"] = artist # Artist Tag
            
            # Thumbnail add karo
            if image:
                try:
                    img_res = requests.get(image, timeout=10)
                    if img_res.status_code == 200:
                        audio["covr"] = [MP4Cover(img_res.content, imageformat=MP4Cover.FORMAT_JPEG)]
                except:
                    pass # Agar image download fail ho jaye toh gaana toh chalna chahiye
                    
            audio.save(audio_io)
            audio_io.seek(0)
        except Exception as e:
            print(f"Tagging failed (Raw file bhej rahe hain): {e}")
            audio_io.seek(0)

        # 3. Clean Filename banao
        safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c in ' -_']).rstrip()
        safe_artist = "".join([c for c in artist if c.isalpha() or c.isdigit() or c in ' -_']).rstrip()
        filename = f"{safe_title} - {safe_artist}.m4a"

        # 4. File Return karo
        return Response(
            content=audio_io.read(),
            media_type="audio/mp4",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# PRO PLAYER HTML/CSS/JS
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🎵 Pro Music Player</title>
<style>
  /* ============================================================
     THEME VARIABLES 
     ============================================================ */
  body.theme-default {
    --bg: #f6f2ed; --surface: #ffffff; --surface-hover: #f6efe9;
    --text: #1e1a17; --text-secondary: #5e5148; --border: #e3dbd3;
    --primary: #b45309; --primary-hover: #92400e; --primary-light: #fef3e8;
    --accent: #6b4c3b; --shadow: 0 6px 28px rgba(0, 0, 0, 0.08);
  }
  body.theme-rose {
    --bg: #fdf6f0; --surface: #fff; --surface-hover: #fce8e0;
    --text: #3d2a1f; --text-secondary: #7a5a4a; --border: #f0d5c8;
    --primary: #d45c7a; --primary-hover: #b84a66; --primary-light: #fce8e6;
    --accent: #a67c6b; --shadow: 0 6px 28px rgba(212, 92, 122, .15);
  }
  body.theme-ocean {
    --bg: #f0f7fc; --surface: #fff; --surface-hover: #e4f0fa;
    --text: #1a2e3f; --text-secondary: #4a6a7f; --border: #c8dce8;
    --primary: #2a7faa; --primary-hover: #1f648a; --primary-light: #dcecf5;
    --accent: #4a8fa7; --shadow: 0 6px 28px rgba(42, 127, 170, .15);
  }
  body.theme-sunset {
    --bg: #fef8f0; --surface: #fff; --surface-hover: #fef0e0;
    --text: #3d2a1a; --text-secondary: #7a5a3a; --border: #f0dcc8;
    --primary: #e07c2e; --primary-hover: #c46820; --primary-light: #fef0e0;
    --accent: #b08a60; --shadow: 0 6px 28px rgba(224, 124, 46, .2);
  }
  body.theme-forest {
    --bg: #f2f7f0; --surface: #fff; --surface-hover: #e6f0e0;
    --text: #1a2e1a; --text-secondary: #4a6a3a; --border: #c8dcc0;
    --primary: #3a7a4a; --primary-hover: #2e6438; --primary-light: #dcecd0;
    --accent: #6a8a5a; --shadow: 0 6px 28px rgba(58, 122, 74, .15);
  }
  body.theme-midnight {
    --bg: #121212; --surface: #1e1e1e; --surface-hover: #2a2a2a;
    --text: #f0ece6; --text-secondary: #b0a89c; --border: #3a3a3a;
    --primary: #c0846a; --primary-hover: #d49a80; --primary-light: #2a1e18;
    --accent: #a08070; --shadow: 0 6px 28px rgba(0, 0, 0, .5);
  }
  body.theme-blush {
    --bg: #fef6f9; --surface: #fff; --surface-hover: #fce8f0;
    --text: #3d2a30; --text-secondary: #7a5a66; --border: #f0d5e0;
    --primary: #d46a8a; --primary-hover: #b85474; --primary-light: #fce8ee;
    --accent: #a67a8a; --shadow: 0 6px 28px rgba(212, 106, 138, .18);
  }
  body.theme-lavender {
    --bg: #f8f4ff; --surface: #fff; --surface-hover: #f0e8ff;
    --text: #2d1f3d; --text-secondary: #6a5a7a; --border: #dcd0ec;
    --primary: #8a6ab8; --primary-hover: #7454a0; --primary-light: #ece4f8;
    --accent: #8a7a9a; --shadow: 0 6px 28px rgba(138, 106, 184, .15);
  }
  body.theme-starry {
    --bg: #0f0f1a; --surface: #1a1a2e; --surface-hover: #26263a;
    --text: #e8e0f0; --text-secondary: #a090b0; --border: #3a2a4a;
    --primary: #b08ad4; --primary-hover: #c4a0e8; --primary-light: #2a1a3a;
    --accent: #8a7aaa; --shadow: 0 6px 28px rgba(0, 0, 0, .6);
  }

  *{box-sizing:border-box; margin:0; padding:0; font-family:'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;}
  body{background:var(--bg); color:var(--text); height:100vh; display:flex; flex-direction:column; overflow:hidden; transition: background 0.3s, color 0.3s;}
  
  .header{padding:15px 20px; background:var(--surface); display:flex; flex-wrap:wrap; gap:15px; align-items:center; box-shadow:var(--shadow); z-index:10; border-bottom:1px solid var(--border); transition: background 0.3s;}
  .header h1{font-size:1.4rem; color:var(--primary); white-space:nowrap;}
  
  .search-box{flex:1; display:flex; gap:10px; min-width:250px;}
  .search-box input{flex:1; padding:10px 15px; border-radius:8px; border:1px solid var(--border); background:var(--bg); color:var(--text); outline:none; font-size:1rem;}
  .search-box input:focus{border-color:var(--primary);}
  .search-box button{padding:10px 20px; border-radius:8px; border:none; background:var(--primary); color:#fff; font-weight:bold; cursor:pointer; transition:0.2s;}
  .search-box button:hover{background:var(--primary-hover);}
  
  .theme-selector{padding:10px; border-radius:8px; border:1px solid var(--border); background:var(--surface); color:var(--text); outline:none; cursor:pointer; font-weight:bold;}
  
  .main-content{flex:1; display:flex; overflow:hidden; padding-bottom:90px;}
  .results-section{flex:2; padding:20px; overflow-y:auto;}
  .sidebar{flex:1; background:var(--surface); border-left:1px solid var(--border); display:flex; flex-direction:column; max-width:350px; transition:background 0.3s;}
  
  .tabs{display:flex; border-bottom:1px solid var(--border);}
  .tab{flex:1; padding:12px; text-align:center; cursor:pointer; font-weight:bold; color:var(--text-secondary); background:var(--surface-hover); border:none; transition:0.2s;}
  .tab.active{color:var(--primary); border-bottom:3px solid var(--primary); background:var(--surface);}
  .tab-content{flex:1; overflow-y:auto; padding:15px; display:none;}
  .tab-content.active{display:block;}
  
  .section-title{font-size:1.1rem; margin-bottom:15px; color:var(--text-secondary); font-weight:bold; display:flex; justify-content:space-between;}
  .song-card{display:flex; align-items:center; gap:12px; padding:10px; border-radius:8px; margin-bottom:10px; background:var(--surface); border:1px solid var(--border); transition:0.2s;}
  .song-card:hover{background:var(--surface-hover); transform:translateY(-1px); box-shadow:0 4px 10px rgba(0,0,0,0.05);}
  .song-card img{width:55px; height:55px; border-radius:6px; object-fit:cover;}
  .song-info{flex:1; min-width:0;}
  .song-title{font-weight:bold; font-size:0.95rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
  .song-meta{font-size:0.8rem; color:var(--text-secondary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-top:3px;}
  
  .actions{display:flex; gap:5px; align-items:center; flex-wrap:wrap; margin-top:6px;}
  .btn{padding:6px 12px; border-radius:6px; border:none; cursor:pointer; font-size:0.8rem; font-weight:bold; display:flex; align-items:center; gap:4px; transition:0.2s;}
  .btn-play{background:var(--primary); color:#fff;}
  .btn-play:hover{background:var(--primary-hover);}
  .btn-outline{background:transparent; border:1px solid var(--border); color:var(--text);}
  .btn-outline:hover{background:var(--surface-hover); border-color:var(--text-secondary);}
  .btn-fav{background:none; border:none; font-size:1.2rem; cursor:pointer; padding:5px;}
  
  /* Naye Download Buttons */
  .btn-dl{background:var(--primary-light); color:var(--primary); border:1px solid var(--primary); font-size:0.75rem; padding:4px 8px; border-radius:4px; cursor:pointer; font-weight:bold; transition:0.2s;}
  .btn-dl:hover{background:var(--primary); color:#fff;}
  .btn-dl:disabled{opacity:0.5; cursor:wait;}
  
  .player-bar{position:fixed; bottom:0; left:0; right:0; height:90px; background:var(--surface); display:flex; align-items:center; justify-content:space-between; padding:0 20px; box-shadow:0 -4px 15px rgba(0,0,0,0.1); border-top:1px solid var(--border); z-index:20; transition:background 0.3s;}
  .now-playing{display:flex; align-items:center; gap:12px; width:30%;}
  .now-playing img{width:55px; height:55px; border-radius:8px; object-fit:cover; box-shadow:var(--shadow);}
  .player-controls{display:flex; flex-direction:column; align-items:center; flex:1;}
  .controls-btns{display:flex; gap:15px; align-items:center; margin-bottom:8px;}
  .controls-btns button{background:none; border:none; color:var(--text); font-size:1.3rem; cursor:pointer; transition:0.2s;}
  .controls-btns button:hover{color:var(--primary);}
  .controls-btns .play-btn{font-size:2rem; color:var(--primary);}
  .progress-container{width:100%; max-width:400px; display:flex; align-items:center; gap:10px; font-size:0.8rem; color:var(--text-secondary);}
  .progress-bar{flex:1; height:6px; background:var(--border); border-radius:3px; cursor:pointer; position:relative;}
  .progress-fill{height:100%; background:var(--primary); width:0%; border-radius:3px; transition:0.1s;}
  .volume-control{width:20%; display:flex; justify-content:flex-end; align-items:center; gap:10px;}
  .volume-control input{width:80px; accent-color:var(--primary);}
  
  ::-webkit-scrollbar{width:6px;}
  ::-webkit-scrollbar-track{background:var(--bg);}
  ::-webkit-scrollbar-thumb{background:var(--border); border-radius:3px;}
  ::-webkit-scrollbar-thumb:hover{background:var(--primary);}
  
  @media (max-width: 800px) {
    .header{flex-direction:column; align-items:stretch;}
    .main-content{flex-direction:column;}
    .sidebar{display:none;}
    .volume-control{display:none;}
    .now-playing{width:40%;}
    .player-controls{width:60%;}
  }
</style>
</head>
<body class="theme-default">

<div class="header">
  <h1>🎵 Pro Music</h1>
  <form class="search-box" onsubmit="doSearch(event)">
    <input id="q" placeholder="Search songs (e.g. Saree Se Tadi)..." autofocus>
    <button type="submit" id="searchBtn">Search</button>
  </form>
  <select class="theme-selector" id="themePicker" onchange="changeTheme(this.value)">
    <option value="theme-default">Default</option>
    <option value="theme-rose">Rose</option>
    <option value="theme-ocean">Ocean</option>
    <option value="theme-sunset">Sunset</option>
    <option value="theme-forest">Forest</option>
    <option value="theme-midnight">Midnight</option>
    <option value="theme-blush">Blush</option>
    <option value="theme-lavender">Lavender</option>
    <option value="theme-starry">Starry</option>
  </select>
</div>

<div class="main-content">
  <div class="results-section">
    <div class="section-title" id="resultsTitle">Search Results</div>
    <div id="results"></div>
  </div>
  
  <div class="sidebar">
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

<div class="player-bar">
  <div class="now-playing">
    <img id="playerImg" src="https://via.placeholder.com/60?text=🎵" alt="Cover">
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

  const savedTheme = localStorage.getItem('musicTheme') || 'theme-default';
  document.body.className = savedTheme;
  document.getElementById('themePicker').value = savedTheme;

  function changeTheme(theme) {
    document.body.className = theme;
    localStorage.setItem('musicTheme', theme);
  }

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
      document.getElementById('results').innerHTML = `<p style="color:red">${err.message}</p>`;
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
    
    // Function banaya hai jo backend ko call karega tagging ke liye
    let dlHtml = '';
    if(urls['320']) dlHtml += `<button onclick="downloadSong(this, '${urls['320']}', '${sanitizeText(s.title)}', '${sanitizeText(artistName)}', '${s.image}')" class="btn-dl">320k</button>`;
    if(urls['160']) dlHtml += `<button onclick="downloadSong(this, '${urls['160']}', '${sanitizeText(s.title)}', '${sanitizeText(artistName)}', '${s.image}')" class="btn-dl">160k</button>`;
    if(urls['96']) dlHtml += `<button onclick="downloadSong(this, '${urls['96']}', '${sanitizeText(s.title)}', '${sanitizeText(artistName)}', '${s.image}')" class="btn-dl">96k</button>`;

    let queueBtn = source === 'search' ? `<button class="btn btn-outline" onclick="addToQueue(${index})">+ Queue</button>` : 
                   `<button class="btn btn-outline" style="color:red;border-color:red" onclick="removeFromQueue(${index})">Remove</button>`;

    return `
      <div class="song-card">
        <img src="${s.image || ''}" onerror="this.src='https://via.placeholder.com/60?text=🎵'">
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

  // JADU: Download Handler
  function downloadSong(btn, url, title, artist, image) {
    const originalText = btn.innerText;
    btn.innerText = '⌛...';
    btn.disabled = true;
    
    // Naya tab kholo backend proxy ke liye
    const dlUrl = `/api/dl?url=${encodeURIComponent(url)}&title=${encodeURIComponent(title)}&artist=${encodeURIComponent(artist)}&image=${encodeURIComponent(image)}`;
    window.location.href = dlUrl; 
    
    // 4 second baad button wapas normal kardo
    setTimeout(() => {
      btn.innerText = originalText;
      btn.disabled = false;
    }, 4000);
  }

  function renderQueue() {
    const container = document.getElementById('queueList');
    if (queue.length === 0) {
      container.innerHTML = '<p style="color:var(--text-secondary);text-align:center;margin-top:20px;">Queue is empty</p>';
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
      container.innerHTML = '<p style="color:var(--text-secondary);text-align:center;margin-top:20px;">No favorites yet</p>';
      return;
    }
    container.innerHTML = favorites.map((s, i) => `
      <div class="song-card">
        <img src="${s.image || ''}" onerror="this.src='https://via.placeholder.com/60?text=🎵'">
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
